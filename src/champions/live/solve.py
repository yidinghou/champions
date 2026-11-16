"""The live page's "Solve" button: the board as entered -> a 2-turn recommendation from the solver.

The page sends what /api/scout gets (mine, foes, weather, tailwind, trick_room) plus the benches (mine_bench,
foe_bench: same entry shape), so switches can be searched. The engine can't play every move, ability or item, so
anything it doesn't model is dropped before the search and reported in "unmodeled". Foes use the usual build (or the
moves you've seen) with no hidden-set belief: one guess per foe. See issue #27.
"""
from __future__ import annotations

import os
import threading
from concurrent.futures.process import BrokenProcessPool

from ..engine import teams
from ..engine.actions import Move, Switch
from ..engine.effects_table import is_supported_ability, is_supported_move
from ..engine.handlers.field import TRICK_ROOM_TURNS
from ..engine.items import is_supported_item
from ..engine.resolve import resolve
from ..engine.state import STAT_KEYS
from ..solver import search
from . import scout
from .scout import BadBoard, SIDES

BUDGET = 7.0
WORKERS = min(10, os.cpu_count() or 1)
MAX_LINES = 5
FALLBACK_MOVE = "protect"
_lock = threading.Lock()          # one solve at a time: it uses every core


def warm():
    """Start the worker processes now (about 0.3s each) so the first solve doesn't pay for it."""
    if WORKERS > 1:
        search.get_pool(WORKERS)


def _supported(spec, dropped):
    """Remove what the engine can't play. Records each removal under the species name."""
    spec = dict(spec)
    name = spec["species"]
    moves = list(spec.get("moves", []))
    keep = [m for m in moves if is_supported_move(m)]
    for m in moves:
        if m not in keep:
            dropped.append({"mon": name, "kind": "move", "id": m})
    spec["moves"] = keep or [FALLBACK_MOVE]
    ab = teams.key(spec.get("ability") or scout.species_data()[name]["abilities"][0])
    if not is_supported_ability(ab):
        dropped.append({"mon": name, "kind": "ability", "id": ab})
    item = spec.get("item")
    if item and not is_supported_item(teams.key(item)):
        dropped.append({"mon": name, "kind": "item", "id": item})
        spec["item"] = None
    return spec


def _entries(req, key):
    v = req.get(key) or []
    if not isinstance(v, list) or not all(isinstance(e, dict) for e in v):
        raise BadBoard(f"{key} is a list of Pokémon entries")
    return v


def build(req, team):
    """(battle, placed, dropped). Actives first, then the bench; fainted actives count as bench."""
    dropped = []
    sides, counts, placed_entries = [], [], []
    for word in SIDES:
        act = [e for e in _entries(req, "mine" if word == "me" else "foes")]
        bench = _entries(req, "mine_bench" if word == "me" else "foe_bench")
        live = [e for e in act if (e.get("hp", 1) or 0) > 0]
        order = live + [e for e in act if e not in live] + bench
        if not live:
            raise BadBoard("put at least one Pokémon on each side" if word == "foe" else "put one of yours on the field")
        if len(live) > 2 or len(order) > 6:
            raise BadBoard("two on the field per side, six in all")
        sides.append([_supported(scout._entry_spec(word, e, team), dropped) for e in order])
        counts.append(len(live))
        placed_entries.append(order)
    try:
        b = teams.build_battle(sides, 0, "doubles")
    except (KeyError, ValueError) as e:
        raise BadBoard(f"can't build that board: {e}") from e
    placed = []
    for si, (word, entries) in enumerate(zip(SIDES, placed_entries)):
        b.sides[si].active = list(range(counts[si])) + [None] * (2 - counts[si])
        for i, entry in enumerate(entries):
            mon = b.sides[si].team[i]
            mon._entry_name = entry["name"]
            mon.stages = {k: 0 for k in STAT_KEYS}
            scout._apply_state(mon, entry)
            if i < counts[si]:
                placed.append((word, i, mon))
    return b, placed, dropped


def _field(b, placed, req):
    for w in req.get("tailwind") or []:
        if w not in SIDES:
            raise BadBoard("tailwind is a list of 'me' / 'foe'")
        b.sides[SIDES.index(w)].conditions["tailwind"] = 4
    if req.get("trick_room"):
        b.arena["trick_room"] = TRICK_ROOM_TURNS
    weather, _ = scout._weather(b, placed, req.get("weather"))
    if weather:
        b.arena["weather"], b.arena["weather_turns"] = weather, 5


def _targets(b, side, c, data):
    """Names of the Pokémon a move hits: its chosen target, or every foe (and ally) a spread move reaches."""
    kind = data["target"]
    foes = [m for _, m in b.sides[1 - side].alive_active()]
    ally = [m for _, m in b.sides[side].alive_active() if m is not b.sides[side].mon_at(c.slot)]
    if kind in ("normal", "any"):
        t = b.mon(*c.target) if getattr(c, "target", None) else None
        return [t] if t is not None else []
    if kind == "allAdjacentFoes":
        return foes
    if kind == "allAdjacent":
        return foes + ally
    return []


def _action(b, side, c):
    """One slot's choice as the page can show it."""
    mon = b.sides[side].mon_at(c.slot)
    out = {"mon": scout._name(mon), "slot": c.slot}
    if isinstance(c, Switch):
        out.update(kind="switch", to=scout._name(b.sides[side].team[c.to]))
    else:
        data = teams.moves_data()[c.move]
        targets = _targets(b, side, c, data)
        foe = b.mon(*c.target) if getattr(c, "target", None) else None
        out.update(kind="move", move=c.move, mega=bool(c.mega), target=scout._name(foe) if foe else None,
                   type=str(data["type"]).lower(), targets=[scout._name(t) for t in targets])
    return out


def _view(b, side, combo):
    return [_action(b, side, c) for c in combo]


CELL_BUCKETS = {"damage_roll": 1}


def _cell(b, row, col):
    """The board after one turn of row (ours) against col (theirs): per Pokémon shown, how likely it is down and its HP range.
    A slot that switches shows the Pokémon coming in. Their two come first, then ours."""
    outs = resolve(b, list(row) + list(col), buckets=CELL_BUCKETS, min_prob=0.02)
    total = sum(p for p, _ in outs) or 1.0
    slots, kos = [], {"foe": 0.0, "me": 0.0}
    for side, word, combo in ((1, "foe", col), (0, "me", row)):
        for c in sorted(combo, key=lambda c: c.slot):
            idx = c.to if isinstance(c, Switch) else b.sides[side].active[c.slot]
            shown = b.sides[side].team[idx]
            ko, lo, hi, status = 0.0, 1.0, 0.0, {}
            for p, o in outs:
                m = o.sides[side].team[idx]
                if m.hp <= 0:
                    ko += p / total
                else:
                    f = m.hp / m.max_hp
                    lo, hi = min(lo, f), max(hi, f)
                    status[m.status] = status.get(m.status, 0.0) + p / total
            if ko >= 0.999:
                lo = hi = 0.0
            top = max(status.items(), key=lambda kv: kv[1], default=(None, 0))
            slots.append({"side": word, "name": scout._name(shown), "incoming": isinstance(c, Switch),
                          "ko": round(ko, 3), "lo": round(lo, 3), "hi": round(hi, 3),
                          "status": top[0] if top[0] and top[1] >= 0.5 else None})
            kos[word] += ko
    return {"slots": slots, "you_ko": round(kos["foe"], 3), "they_ko": round(kos["me"], 3)}


def solve_live(req, team, budget=BUDGET):
    if not isinstance(req, dict):
        raise BadBoard("body must be a JSON object")
    b, placed, dropped = build(req, team)
    _field(b, placed, req)
    with _lock:
        try:
            try:
                r = search.solve_budget(b, budget=budget, workers=WORKERS)
            except BrokenProcessPool:                       # a worker died: the next solve gets a fresh pool; this one runs alone
                r = search.solve_budget(b, budget=budget, workers=1)
        except search.SearchTimeout as e:
            raise BadBoard("the solver ran out of time on that board") from e
    n, m = len(r.rows), len(r.cols)
    vs_foe = [sum(r.col_mix[j] * r.matrix[i][j] for j in range(m) if r.matrix[i][j] is not None) for i in range(n)]
    worst = [min(((v, j) for j, v in enumerate(r.matrix[i]) if v is not None), default=(0.0, 0)) for i in range(n)]
    order = sorted(range(n), key=lambda i: (-r.row_mix[i], -vs_foe[i]))[:MAX_LINES]
    replies = sorted(range(m), key=lambda j: -r.col_mix[j])[:3]
    return {"value": r.value, "label": r.label, "seconds": round(r.stats.seconds, 2),
            "lines": [{"p": round(r.row_mix[i], 3), "value": round(vs_foe[i], 3), "actions": _view(b, 0, r.row_actions[i])}
                      for i in order],
            "foe_replies": [{"p": round(r.col_mix[j], 3), "actions": _view(b, 1, r.col_actions[j])} for j in replies if r.col_mix[j] > 0.005],
            "cells": [[_cell(b, ra, ca) for ca in r.col_actions] for ra in r.row_actions],
            "row_vs": [round(v, 3) for v in vs_foe], "row_worst": [round(w, 3) for w, _ in worst],
            "row_worst_col": [j for _, j in worst],
            "best": max(range(n), key=lambda i: vs_foe[i]), "safe": max(range(n), key=lambda i: worst[i][0]),
            "rows": [_view(b, 0, a) for a in r.row_actions], "cols": [_view(b, 1, a) for a in r.col_actions],
            "matrix": [[None if v is None else round(v, 3) for v in row] for row in r.matrix],
            "row_mix": [round(x, 3) for x in r.row_mix], "col_mix": [round(y, 3) for y in r.col_mix],
            "unmodeled": dropped}
