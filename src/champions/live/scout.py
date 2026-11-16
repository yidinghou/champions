"""What the live page asks the server: Speed order and damage ranges for the board as entered.

No rules live here. A board entry is turned into an engine Mon (`engine/teams.build_mon`), Speed is the engine's own
`turn.speed`, and damage is `calc.damage.damage` over the 16 rolls. A foe's build is the most common one in the
MunchStats snapshot unless the page says otherwise.
"""
from __future__ import annotations

import json
from functools import lru_cache
from itertools import product

from ..calc.damage import ROLLS, damage
from ..engine import teams
from ..engine.arena import SPEED_ABILITIES
from ..engine.items import item_name
from ..engine.pretty import move_name
from ..engine.state import STAT_KEYS
from ..engine.turn import move_priority, speed
from ..sources import common

SIDES = ("me", "foe")
WEATHER = ("sun", "rain", "sand", "snow")
SETTERS = {"drought": "sun", "drizzle": "rain", "sandstream": "sand", "snowwarning": "snow"}
SPREAD = {"allAdjacent", "allAdjacentFoes"}
STATUSES = ("par", "brn", "psn", "tox", "slp", "frz")
WATCH_OHKO, WATCH_2HKO = 0.1, 0.4        # what "Watch out" lists: at least this share of rolls
MAX_SEEN = 4
OVERRIDES = {"me": ("item",), "foe": ("item", "ability", "nature", "sp")}   # what a board entry may change


class BadBoard(ValueError):
    """The request can't be played; the message goes back as a 400."""


@lru_cache(maxsize=None)
def species_data():
    return teams._species()


@lru_cache(maxsize=None)
def learnsets():
    from pathlib import Path
    p = Path(teams.DATA) / "learnsets.json"
    return json.loads(p.read_text())["learnsets"]


@lru_cache(maxsize=None)
def usage():
    snap = common.load("munchstats", "doubles")
    return snap["pokemon"] if snap else {}


def _top(pcts, ok=lambda _: True):
    return [(n, p) for n, p in sorted(pcts.items(), key=lambda kv: -kv[1]) if ok(n)]


def foe_spec(name):
    """The usual build for a species: its commonest ability, item, nature, spread and moves."""
    if name not in species_data():
        raise BadBoard(f"unknown Pokémon: {name}")
    sp = species_data()[name]
    e = usage().get(common.key(name), {})
    moves_ok = set(learnsets().get(sp["species"], learnsets().get(name, [])))
    abil = {teams.key(a) for a in sp["abilities"] + [sp.get("hidden_ability") or ""]}
    spec = {"species": name, "ability": sp["abilities"][0]}
    ab = _top(e.get("abilities", {}), lambda a: teams.key(a) in abil)
    if ab:
        spec["ability"] = teams.key(ab[0][0])
    items = _top(e.get("items", {}))
    if items:
        spec["item"] = teams.key(items[0][0])
    nat = _top(e.get("natures", {}), lambda n: n.lower() in _natures())
    if nat:
        spec["nature"] = nat[0][0].lower()
    spreads = _top(e.get("spreads", {}))
    if spreads:
        spec["sp"] = dict(zip(teams.SP_ORDER, map(int, spreads[0][0].split("/"))))
    mv = teams.moves_data()
    spec["moves"] = [m for m in (teams.key(n) for n, _ in _top(e.get("moves", {}))) if m in mv and m in moves_ok][:4]
    return spec


def usage_moves(name, limit=8):
    """[{id, pct}] for a species, commonest first (only moves the game data knows)."""
    mv = teams.moves_data()
    e = usage().get(common.key(name), {})
    return [{"id": teams.key(n), "pct": p} for n, p in _top(e.get("moves", {})) if teams.key(n) in mv][:limit]


@lru_cache(maxsize=None)
def _natures():
    from ..stats import _UP_DOWN, NEUTRAL
    return set(_UP_DOWN) | set(NEUTRAL)


def speed_range(spec):
    """(lowest, highest) base Speed stat for a species: 0 SP with a Speed-lowering nature to 32 SP with a raising one."""
    base = species_data()[spec["species"]]["stats"]
    from ..stats import level50
    lo = level50(base, "brave", {})["speed"]
    hi = level50(base, "jolly", {"speed": 32})["speed"]
    return lo, hi


def _entry_spec(side, entry, team):
    name = entry.get("name")
    if not isinstance(name, str) or not name:
        raise BadBoard("every Pokémon needs a name")
    if side == "me":
        base = next((s for s in team if s["species"] == name), None)
        if base is None:
            raise BadBoard(f"{name} is not on your team")
        spec = dict(base)
    else:
        spec = foe_spec(name)
        if entry.get("seen"):
            seen = [teams.key(m) for m in entry["seen"][:MAX_SEEN]]
            bad = [m for m in seen if m not in teams.moves_data()]
            if bad:
                raise BadBoard(f"unknown move: {bad[0]}")
            spec["moves"] = seen + [m for m in spec.get("moves", []) if m not in seen][:MAX_SEEN - len(seen)]
    for k in OVERRIDES[side]:
        if entry.get(k) is not None:
            spec[k] = entry[k]
    return spec


def _apply_state(mon, entry):
    hp = entry.get("hp", 1)
    if not isinstance(hp, (int, float)) or not 0 <= hp <= 1:
        raise BadBoard("hp is a number from 0 to 1")
    mon.hp = 0 if hp == 0 else max(1, round(mon.max_hp * hp))
    status = entry.get("status")
    if status is not None:
        if status not in STATUSES:
            raise BadBoard(f"unknown status: {status}")
        mon.status = status
    for k, v in (entry.get("boosts") or {}).items():
        if k not in STAT_KEYS or not isinstance(v, int) or not -6 <= v <= 6:
            raise BadBoard(f"boosts are -6..6 on {', '.join(STAT_KEYS)}")
        mon.stages[k] = v


def build_board(mine, foes, team):
    """Engine battle with your side first (doubles). Returns (battle, [(side_word, slot, mon), ...])."""
    if not 1 <= len(mine) <= 2 or len(foes) > 2:
        raise BadBoard("put 1 or 2 Pokémon on your side and at most 2 on theirs")
    specs = [[_entry_spec("me", e, team) for e in mine], [_entry_spec("foe", e, team) for e in foes]]
    if not specs[1]:
        specs[1] = []
    try:
        b = teams.build_battle(specs, 0, "doubles")
    except (KeyError, ValueError) as e:
        raise BadBoard(f"can't build that board: {e}") from e
    placed = []
    for si, (word, entries) in enumerate(zip(SIDES, (mine, foes))):
        for slot, entry in enumerate(entries):
            mon = b.sides[si].team[slot]
            _apply_state(mon, entry)
            placed.append((word, slot, mon))
    return b, placed


def _weather(b, placed, asked):
    """(weather, why). Auto: the slowest living setter's weather wins, as the slower one enters last."""
    if asked in WEATHER:
        return asked, "set by hand"
    if asked == "none":
        return None, "set by hand"
    if asked not in (None, "auto"):
        raise BadBoard(f"unknown weather: {asked}")
    setters = [m for _, _, m in placed if m.ability in SETTERS and not m.fainted]
    if not setters:
        return None, None
    m = min(setters, key=lambda m: speed(b, m))
    return SETTERS[m.ability], m.ability


def _rolls(a, d, move, weather, spread):
    return [damage(a, d, move, roll=r, spread=spread, weather=weather, doubles=True) for r in ROLLS]


def _hit(a, d, mid, weather):
    """The calc for one attacker, move and target: percent range and the chance to OHKO and 2HKO."""
    move = teams.moves_data()[mid]
    spread = move["target"] in SPREAD
    rolls = _rolls(a, d, move, weather, spread)
    if not rolls[-1]:
        return {"lo": 0.0, "hi": 0.0, "immune": True, "ohko": 0.0, "two": 0.0}
    hp = d.hp
    n = len(rolls)
    two = sum(1 for x, y in product(rolls, rolls) if x + y >= hp) / (n * n)
    return {"lo": round(rolls[0] / d.max_hp, 4), "hi": round(rolls[-1] / d.max_hp, 4), "immune": False,
            "ohko": sum(1 for r in rolls if r >= hp) / n, "two": two}


def _ko(h):
    if h["ohko"] >= 1:
        return "OHKO", "sure"
    if h["ohko"] > 0:
        return "OHKO", "likely" if h["ohko"] >= 0.5 else "possible"
    if h["two"] >= 1:
        return "2HKO", "sure"
    if h["two"] > 0:
        return "2HKO", "likely" if h["two"] >= 0.5 else "possible"
    return None, None


def _ref(word, mon):
    return {"side": word, "name": mon.species}


def scout(req, team):
    """req: {mine, foes, weather, tailwind, trick_room}. Returns the order, the calc and Watch out."""
    if not isinstance(req, dict):
        raise BadBoard("body must be a JSON object")
    mine, foes = req.get("mine") or [], req.get("foes") or []
    b, placed = build_board(mine, foes, team)
    for w in req.get("tailwind") or []:
        if w not in SIDES:
            raise BadBoard("tailwind is a list of 'me' / 'foe'")
        b.sides[SIDES.index(w)].conditions["tailwind"] = 4
    b.arena["trick_room"] = bool(req.get("trick_room"))
    weather, source = _weather(b, placed, req.get("weather"))
    if weather:
        b.arena["weather"] = weather
    alive = [(w, s, m) for w, s, m in placed if not m.fainted]

    order = []
    for word, slot, m in alive:
        lo = hi = speed(b, m)
        if word == "foe":
            slo, shi = speed_range({"species": m.species})
            for stat, which in ((slo, "lo"), (shi, "hi")):
                c = m.clone()
                c.stats["spe"] = stat
                if which == "lo":
                    lo = speed(b, c)
                else:
                    hi = speed(b, c)
        order.append({"side": word, "slot": slot, "name": m.species, "lo": lo, "hi": hi, "now": speed(b, m)})
    order.sort(key=lambda o: o["now"], reverse=not b.arena["trick_room"])

    calc, threats = [], []
    mv = teams.moves_data()
    for aw, _, a in alive:
        for tw, _, d in alive:
            if tw == aw:
                continue
            row = []
            for mid in a.moves:
                if mv[mid]["category"] == "Status" or not mv[mid]["base_power"]:
                    continue
                h = _hit(a, d, mid, weather)
                ko, chance = _ko(h)
                calc.append({"mon": _ref(aw, a), "move": mid, "target": _ref(tw, d), "lo": h["lo"], "hi": h["hi"],
                             "immune": h["immune"], "ko": ko, "chance": chance})
                if aw == "foe" and (h["ohko"] >= WATCH_OHKO or h["two"] >= WATCH_2HKO):
                    row.append({"move": mid, "priority": move_priority(b, a, mid), "lo": h["lo"], "hi": h["hi"],
                                "ko": ko, "chance": chance})
            for r in row:
                threats.append({"foe": _ref(aw, a), "target": _ref(tw, d), **r})

    return {"weather": weather, "weather_source": source, "trick_room": b.arena["trick_room"], "order": order,
            "calc": calc, "threats": threats,
            "speed_abilities": [{"foe": _ref(w, m), "ability": m.ability}
                                for w, _, m in alive if m.ability in SPEED_ABILITIES.values()],
            "board": [board_card(w, s, m, mine[s] if w == "me" else foes[s]) for w, s, m in placed]}


def board_card(word, slot, m, entry):
    """What the card needs from the engine: label, max HP, the stats (before stages) and the moves it may show."""
    mvs = teams.moves_data()
    card = {"side": word, "slot": slot, "name": m.species, "hp": entry.get("hp", 1), "max_hp": m.max_hp,
            "stats": {k: v for k, v in m.stats.items() if k != "hp"}, "types": m.types, "ability": m.ability,
            "item": m.item, "item_name": item_name(m.item) if m.item else None,
            "moves": [{"id": i, "name": move_name(i), "type": mvs[i]["type"], "category": mvs[i]["category"],
                       "pp": mvs[i]["pp"]} for i in m.moves if i in mvs]}
    if word == "foe":
        card["usage"] = usage_moves(m.species)
    return card


def team_view(team):
    """Your team as the page shows it."""
    out = []
    for spec in team:
        m = teams.build_mon(spec)
        out.append({"name": m.species, "label": move_name(m.species), "item": m.item, "ability": m.ability,
                    "max_hp": m.max_hp, "stats": {k: v for k, v in m.stats.items() if k != "hp"}, "types": m.types,
                    "nature": m.nature, "sp": m.sp, "moves": [{"id": i, "name": move_name(i)} for i in m.moves]})
    return out
