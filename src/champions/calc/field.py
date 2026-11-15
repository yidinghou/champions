"""Weather and terrain facts the damage calc needs. Pure functions: no engine imports.

Weather is one of SUN, RAIN, SAND, SNOW (or None); terrain one of ELECTRIC, GRASSY, MISTY, PSYCHIC (or None).
The numbers are Showdown's gen 9 values; Champions may differ (flagged `verify` in the catalogue).
"""
from __future__ import annotations

WEATHERS = ("sun", "rain", "sand", "snow")
TERRAINS = ("electric", "grassy", "misty", "psychic")
TERRAIN_BOOST = 5325          # x1.3 in 4096ths: Electric, Grassy and Psychic terrain boost their type (and Sand Force)
TERRAIN_BOOSTED_TYPE = {"electric": "Electric", "grassy": "Grass", "psychic": "Psychic"}
GRASSY_HALVED = ("Earthquake",)   # TODO(grassy-terrain): Bulldoze and Magnitude when they are modeled


def modify(value, num):
    """Showdown's chained modifier: num is in 4096ths (4096 = x1). Rounds half down."""
    return (value * num + 2048 - 1) // 4096


def is_grounded(mon):
    """Terrain only touches grounded mons. TODO(items): Air Balloon, Iron Ball; TODO(gravity)."""
    return "flying" not in mon.types and mon.ability != "levitate"


def weather_damage_mod(weather, move_type):
    """(numerator, denominator) applied to damage, or None. Sun/Rain boost one type and halve the other."""
    boosted = {"sun": ("Fire", "Water"), "rain": ("Water", "Fire")}.get(weather)
    if boosted is None or move_type is None:
        return None
    if move_type == boosted[0]:
        return 3, 2
    if move_type == boosted[1]:
        return 1, 2
    return None


def field_base_power(weather, terrain, bp, move, attacker, defender):
    """Base power after terrain and Sand Force. The multipliers chain, so they apply to the power, not the damage."""
    mtype = move["type"]
    num = 4096
    if weather == "sand" and attacker.ability == "sandforce" and mtype in ("Rock", "Ground", "Steel"):
        num = num * TERRAIN_BOOST // 4096     # Sand Force: x1.3
    if terrain in TERRAIN_BOOSTED_TYPE and mtype == TERRAIN_BOOSTED_TYPE[terrain] and is_grounded(attacker):
        num = num * TERRAIN_BOOST // 4096
    if terrain == "misty" and mtype == "Dragon" and is_grounded(defender):
        num = num // 2
    if terrain == "grassy" and move.get("name") in GRASSY_HALVED and is_grounded(defender):
        num = num // 2
    return max(1, modify(bp, num)) if num != 4096 else bp
