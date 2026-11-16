"""Play a replay, capture the battle state after every event, and write a single HTML file."""
from __future__ import annotations

import base64
import json
from pathlib import Path

from ..actions import from_dict
from ..game import play_turn, start
from ..items import item_name
from ..pretty import HIDDEN_VOLATILES, _describe, mon_name, move_name
from ..replay import load_replay
from ..screens import SIDE_WORDS

HERE = Path(__file__).resolve().parent
ICONS = Path(__file__).resolve().parents[4] / "sources" / "icons"
# Events shown as steps. rng rolls and per-hit bookkeeping are kept only as raw detail on the step before.
QUIET = {"hit", "rng", "turn", "start"}
OUTCOME_KINDS = {"hit", "protected", "immune", "missed", "blocked"}
SPREAD_TARGETS = {"allAdjacent", "allAdjacentFoes"}


def _mon(m, on_field, slot):
    vols = {k: (v if isinstance(v, (int, float, str, bool)) else True) for k, v in m.volatiles.items()
            if k not in HIDDEN_VOLATILES}
    return {"ref": m.ref, "species": m.species, "types": list(m.types), "ability": m.ability,
            "item": m.item, "item_name": item_name(m.item) if m.item else None,
            "moves": [{"id": mv, "name": move_name(mv), "pp": m.pp.get(mv)} for mv in m.moves],
            "hp": m.hp, "max_hp": m.max_hp, "status": m.status, "stages": {k: v for k, v in m.stages.items() if v},
            "volatiles": vols, "mega": m.mega, "fainted": m.fainted, "slot": slot if on_field else None,
            "stats": {k: v for k, v in m.stats.items() if k != "hp"}}


def snapshot(b):
    sides = []
    for s in b.sides:
        slots = {i: n for n, i in enumerate(s.active) if i is not None}
        sides.append({"active": list(s.active),
                      "team": [_mon(m, i in slots, slots.get(i)) for i, m in enumerate(s.team)],
                      "conditions": {SIDE_WORDS.get(k, k): (v if isinstance(v, (int, float, bool, str)) else True)
                                     for k, v in s.conditions.items()},
                      "mega_used": s.mega_used})
    arena = {k: v for k, v in b.arena.items() if k not in ("moved", "pending")}
    return {"turn": b.turn, "sides": sides, "arena": arena, "winner": b.winner}


def moves_data():
    d = json.loads((Path(__file__).resolve().parents[2] / "data" / "moves.json").read_text())
    return d["moves"]


def build_frames(replay):
    """Return {frames, final, ...}. A frame = {turn, kind, text, data, raw, state}; the first is the starting board.

    State is read from the live battle right after each event is logged, by wrapping Battle.log_event
    for the duration of the game.
    """
    from ..state import Battle
    frames, pending_raw, holder = [], [], {}
    moves = moves_data()
    gs = {"g": 0, "kind": {0: "start"}, "mega_wait": False}   # action groups: a move and everything it causes
    cur = {}      # the latest move frame; later events for the same move name its targets and outcomes
    original = Battle.log_event

    def tap(self, kind, **data):
        original(self, kind, **data)
        if not self.record:
            return
        e = self.log[-1]
        raw = {"turn": e.turn, "kind": e.kind, "data": e.data}
        if kind in OUTCOME_KINDS and cur and data.get("move") == cur["data"]["move"] and data.get("mon"):
            t = cur["targets"]
            if not any(x["mon"] == data["mon"] and x["outcome"] == kind for x in t):
                t.append({"mon": data["mon"], "outcome": kind})
        if kind == "start":
            text = "Battle start"
        elif kind == "move":
            text = f"{mon_name(data['mon'])} used {move_name(data['move'])}!"
        elif kind in QUIET or (kind == "hit" and data.get("spread")):
            text = None
        else:
            text = _describe(e)
        if text is None:
            pending_raw.append(raw)
            return
        frame = {"turn": e.turn, "kind": kind, "text": text, "data": data, "group": gs["g"],
                 "raw": pending_raw[:] + [raw], "state": snapshot(self)}
        if kind == "move":
            mv = moves.get(data["move"], {})
            frame.update(targets=[], mtype=(mv.get("type") or "").lower(), category=(mv.get("category") or "").lower(),
                         spread=mv.get("target") in SPREAD_TARGETS)
            cur.clear()
            cur.update(frame)          # shares the same data/targets objects
        frames.append(frame)
        pending_raw.clear()

    from .. import game as game_mod, mega as mega_mod
    originals = {"run_action": game_mod.run_action, "run_residuals": game_mod.run_residuals,
                 "request_replacements": game_mod.request_replacements, "evolve": mega_mod.evolve}

    def new_group(kind):
        gs["g"] += 1
        gs["kind"][gs["g"]] = kind

    def run_action(*a, **k):
        if gs["mega_wait"]:
            gs["mega_wait"] = False            # a Mega Evolution and the move after it are one action
        else:
            new_group("action")
        return originals["run_action"](*a, **k)

    def evolve(*a, **k):
        new_group("action")
        gs["mega_wait"] = True
        return originals["evolve"](*a, **k)

    def run_residuals(*a, **k):
        new_group("residual")
        return originals["run_residuals"](*a, **k)

    def request_replacements(*a, **k):
        new_group("replace")
        return originals["request_replacements"](*a, **k)

    game_mod.run_action, game_mod.run_residuals = run_action, run_residuals
    game_mod.request_replacements, mega_mod.evolve = request_replacements, evolve
    Battle.log_event = tap
    try:
        b = start(replay["teams"], replay["seed"], replay["format"])
        for n, choices in enumerate(replay["turns"], 1):
            play_turn(b, [from_dict(c) for c in choices])
            end = snapshot(b)
            if not frames or {**frames[-1]["state"], "turn": 0} != {**end, "turn": 0}:   # silent end-of-turn changes
                frames.append({"turn": n, "kind": "turn_end", "text": f"End of turn {n}", "data": {}, "group": gs["g"],
                               "raw": pending_raw[:], "state": end})
                pending_raw.clear()
    finally:
        Battle.log_event = original
        game_mod.run_action, game_mod.run_residuals = originals["run_action"], originals["run_residuals"]
        game_mod.request_replacements, mega_mod.evolve = originals["request_replacements"], originals["evolve"]
    return {"format": replay["format"], "seed": replay["seed"], "frames": frames, "final": snapshot(b),
            "group_kinds": {str(k): v for k, v in gs["kind"].items()}}


def _icon(species):
    for name in (species, species.split("-")[0]):
        p = ICONS / f"{name}.png"
        if p.exists():
            return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
    return None


def render_html(replay, title="Replay"):
    data = build_frames(replay)
    species = {m["species"] for f in data["frames"][:1] for s in f["state"]["sides"] for m in s["team"]}
    species |= {m["species"] for f in data["frames"] for s in f["state"]["sides"] for m in s["team"]}
    data["icons"] = {sp: _icon(sp) for sp in sorted(species)}
    html = (HERE / "viewer.html").read_text()
    return html.replace("__TITLE__", title).replace("__DATA__", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))


def write_html(replay_path, out=None):
    replay = load_replay(replay_path)
    out = Path(out) if out else Path(replay_path).with_suffix(".html")
    out.write_text(render_html(replay, Path(replay_path).stem))
    return out
