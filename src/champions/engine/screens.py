"""Side conditions: Reflect, Light Screen, Aurora Veil and Tailwind. State in `battle.sides[i].conditions`
as name -> turns left (the turn it was set counts, and it ends at the end of its last turn).

Reflect and Light Screen last 5 turns (8 with Light Clay), Aurora Veil 5 (8) and only starts in snow, Tailwind 4.
A screen cuts damage by 1/2 (singles) or 2732/4096 (doubles) unless the hit is a crit; Aurora Veil covers both
categories, and several screens never stack. Brick Break and Psychic Fangs remove them. Numbers are Showdown's
gen 9 values; Champions may differ (flagged `verify` in the catalogue).
"""
from __future__ import annotations

SIDE_CONDITIONS = ("reflect", "lightscreen", "auroraveil", "tailwind")      # also the end-of-turn order
DURATION = {"reflect": 5, "lightscreen": 5, "auroraveil": 5, "tailwind": 4}
CLAY = ("reflect", "lightscreen", "auroraveil")
SCREENS = CLAY
CATEGORY = {"reflect": "Physical", "lightscreen": "Special"}     # Aurora Veil covers both
SIDE_WORDS = {"reflect": "Reflect", "lightscreen": "Light Screen", "auroraveil": "Aurora Veil", "tailwind": "Tailwind"}


def active_screens(battle, side):
    """Names of the screens up on `side`, as a tuple (what the calc is given)."""
    c = battle.sides[side].conditions
    return tuple(n for n in SCREENS if c.get(n))


def set_condition(battle, side, name, setter=None, cause=None):
    """Put `name` on `side`. Returns the reason it failed ("already_up", "no_snow") or None on success."""
    conds = battle.sides[side].conditions
    if conds.get(name):
        return "already_up"
    if name == "auroraveil" and battle.arena.get("weather") != "snow":
        return "no_snow"
    n = 8 if name in CLAY and setter is not None and setter.item == "lightclay" else DURATION[name]
    conds[name] = n
    battle.log_event("field", effect="side", which=name, side=side, start=True, turns=n,
                     mon=setter.ref if setter else None, cause=cause)
    return None


def remove_condition(battle, side, name, cause):
    if battle.sides[side].conditions.pop(name, None) is not None:
        battle.log_event("field", effect="side", which=name, side=side, end=True, cause=cause)
        return True
    return False


def tick(battle):
    """End of turn: count each condition down and end it at zero."""
    for side in range(len(battle.sides)):
        conds = battle.sides[side].conditions
        for name in SIDE_CONDITIONS:
            left = conds.get(name)
            if not left:
                continue
            if left - 1 > 0:
                conds[name] = left - 1
            else:
                remove_condition(battle, side, name, "expired")
