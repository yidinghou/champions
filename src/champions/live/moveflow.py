"""What a move does, as the live page's click-through flow needs it: who it targets, whether it can miss, and its
after-effects split into `auto` (certain, so the page applies them) and `ask` (a chance, so the page asks).

Read from moves.json's `short_desc` prose, whose phrasings are regular, plus the engine's own effects table for field
changes and Protect. Anything not recognised is left out; the page always offers a manual status row for those.
"""
from __future__ import annotations

import re
from functools import lru_cache

from ..engine import teams
from ..engine.effects_table import MOVES as ENGINE_FX

STATS = {"attack": "atk", "defense": "def", "sp. atk": "spa", "sp. def": "spd", "speed": "spe", "atk": "atk", "def": "def", "spa": "spa", "spd": "spd",
         "accuracy": "acc", "evasiveness": "eva"}
STATUS_WORDS = (("badly poison", "tox"), ("poison", "psn"), ("paraly", "par"), ("burn", "brn"), ("freez", "frz"),
                ("sleep", "slp"), ("asleep", "slp"))
# which target types can't get a status (the page looks these up; it holds no other status rule)
STATUS_IMMUNE = {"brn": ["fire"], "par": ["electric"], "psn": ["poison", "steel"], "tox": ["poison", "steel"],
                 "frz": ["ice"], "slp": []}
NO_TARGET = {"self", "allySide", "foeSide", "all", "allyTeam"}
SPREAD = {"allAdjacentFoes": "foes", "allAdjacent": "all"}
WHO = {"user": "user", "target": "target", "foe(s)": "target", "foes": "target"}


def _stats(text):
    out = {}
    for part in re.split(r"\s+and\s+|,\s*", text.strip()):
        k = STATS.get(part.strip().lower())
        if k:
            out[k] = True
    return list(out)


def _status_in(s):
    s = s.lower()
    if "confus" in s:
        return "confusion"
    if "flinch" in s:
        return "flinch"
    for word, code in STATUS_WORDS:
        if word in s:
            return code
    return None


def _sentence(s, auto, ask, out):
    m = re.match(r"^(\d+)% chance to (lower|raise) the (user|target|foe\(s\))(?:'s)? (.+?) by (\d)", s)
    if m:
        n = int(m[5]) * (1 if m[2] == "raise" else -1)
        ask.append({"chance": int(m[1]), "kind": "stat", "who": WHO[m[3]], "stats": {k: n for k in _stats(m[4])}})
        return
    m = re.match(r"^(Lowers|Raises) (?:the )?(user|target|foe\(s\))'s (.+?) by (\d)", s)
    if m:
        n = int(m[4]) * (1 if m[1] == "Raises" else -1)
        auto.append({"kind": "stat", "who": WHO[m[2]], "stats": {k: n for k in _stats(m[3])}})
        return
    m = re.match(r"^(?:Has )?(\d+)% recoil", s) or re.match(r"^Has (\d+)% recoil", s)
    if m:
        out["recoil"] = [int(m[1]), 100]
        return
    m = re.match(r"^Has (\d+)/(\d+) recoil", s)
    if m:
        out["recoil"] = [int(m[1]), int(m[2])]
        return
    m = re.match(r"^User recovers (\d+)% of the damage dealt", s)
    if m:
        out["drain"] = [int(m[1]), 100]
        return
    m = re.match(r"^Heals (?:the user by )?(\d+)% (?:of its max )?HP", s)
    if m:
        out["heal"] = [int(m[1]), 100]
        return
    if re.search(r"User switches( out)?\b", s):
        out["pivot"] = True
        return
    m = re.search(r"(\d+)% (?:chance to )?(?:make the (?:target|foe\(s\)) )?(burn|paralyze|poison|badly poison|freeze|confuse|confusion|flinch)", s, re.I)
    if m and "adjacent" not in s and "stat rise" not in s:
        kind = _status_in(m[2])
        if kind:
            ask.append({"chance": int(m[1]), "kind": "flinch" if kind == "flinch" else "confusion" if kind == "confusion" else "status",
                        **({} if kind in ("flinch", "confusion") else {"status": kind})})
            return
    m = re.match(r"^(Paralyzes|Burns|Poisons|Badly poisons|Freezes|Causes the target to fall asleep|Puts the target to sleep|Confuses|Causes the target to become confused)", s)
    if m:
        kind = _status_in(m[1]) or ("slp" if "sleep" in m[1] else None)
        auto.append({"kind": "confusion"} if kind == "confusion" else {"kind": "status", "status": kind})
        return
    if re.search(r"100% flinch chance", s):
        auto.append({"kind": "flinch"})


@lru_cache(maxsize=None)
def flow(move_id):
    m = teams.moves_data()[move_id]
    auto, ask, out = [], [], {}
    for s in re.split(r"(?<=\.)\s+", m["short_desc"].replace("Sp. Atk", "SpA").replace("Sp. Def", "SpD")):
        _sentence(s, auto, ask, out)
    eng = ENGINE_FX.get(move_id, {})
    if eng.get("trick_room"):
        auto.append({"kind": "field", "what": "trick_room"})
    if eng.get("side_condition") == "tailwind":
        auto.append({"kind": "field", "what": "tailwind"})
    if eng.get("weather"):
        auto.append({"kind": "field", "what": "weather", "value": eng["weather"]})
    if eng.get("protect") is not None or "Prevents moves from affecting the user" in m["short_desc"]:
        auto.append({"kind": "protect"})
    for a in [a for a in ask if a["chance"] >= 100]:       # a sure effect is applied, not asked
        ask.remove(a)
        auto.append({k: v for k, v in a.items() if k != "chance"})
    auto = [a for a in auto if not (a["kind"] == "stat" and not a["stats"])]
    ask = [a for a in ask if not (a["kind"] == "stat" and not a["stats"])]
    t = m["target"]
    return {"acc": None if m["accuracy"] is True else m["accuracy"],
            "target": "none" if t in NO_TARGET else SPREAD.get(t, "one"),
            "ally_only": t in ("adjacentAlly", "allies"), "category": m["category"],
            "powder": "powder" in m.get("flags", []), "auto": auto, "ask": ask, **out}
