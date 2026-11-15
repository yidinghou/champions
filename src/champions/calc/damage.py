"""Damage in Showdown's modifier order, flooring each step. Level is fixed at 50 in Champions.

Weather (Sun/Rain damage, Sand Sp. Def for Rock, Snow Def for Ice) and terrain (base power) are modeled.
Items (type boosts, Muscle Band, Wise Glasses, Life Orb, Expert Belt, Light Ball, resist berries) are in items.py.
Stubbed to 1.0 for now (TODO S1): screens, abilities (except Guts), Helping Hand.
"""
from __future__ import annotations

from . import items
from .field import field_bp_mod, modify, weather_damage_mod
from .typechart import effectiveness

LEVEL = 50
ROLLS = tuple(range(85, 101))


def stage_multiplier(stage):
    return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)


def _stat(value, stage):
    return int(value * stage_multiplier(stage))


def damage(attacker, defender, move, *, crit=False, roll=100, spread=False, ignore_immunity_to=(),
           weather=None, terrain=None, berry_ok=True):
    """attacker/defender: engine Mon-like (stats, stages, types, status). move: a moves.json entry.
    berry_ok: False when the defender cannot eat its berry (a foe's Unnerve), so a resist berry does nothing.
    weather: "sun" | "rain" | "sand" | "snow" | None; terrain: "electric" | "grassy" | "misty" | "psychic" | None.
    Returns an int; 0 if the defender is immune."""
    bp = move["base_power"]
    if not bp or move["category"] == "Status":
        return 0
    held = attacker is not defender        # confusion's self-hit ignores items, terrain and weather
    chain = field_bp_mod(weather, terrain, move, attacker, defender)
    if held:
        chain = items.chain(chain, items.base_power_mod(attacker, move))
    if chain != 4096:
        bp = max(1, modify(bp, chain))
    special = move["category"] == "Special"
    a_key, d_key = ("spa", "spd") if special else ("atk", "def")
    a_stage, d_stage = attacker.stages[a_key], defender.stages[d_key]
    if crit:  # a crit ignores the attacker's drops and the defender's boosts
        a_stage, d_stage = max(a_stage, 0), min(d_stage, 0)
    a = _stat(attacker.stats[a_key], a_stage) * (items.attack_stat_mod(attacker) if held else 1)
    d = _stat(defender.stats[d_key], d_stage)

    if weather == "sand" and special and "rock" in defender.types:
        d = d * 3 // 2                       # Sand: Rock-types get 1.5x Sp. Def
    elif weather == "snow" and not special and "ice" in defender.types:
        d = d * 3 // 2                       # Snow: Ice-types get 1.5x Defense

    guts = attacker.ability == "guts" and attacker.status and not special
    if guts:
        a = a * 3 // 2
    eff = 1.0 if move["type"] is None else effectiveness(move["type"], defender.types, ignore_immunity_to)
    if eff == 0:
        return 0
    dmg = (2 * LEVEL // 5 + 2) * bp * a // d // 50 + 2
    if spread:
        dmg = dmg * 3 // 4
    wm = weather_damage_mod(weather, move["type"])
    if wm:
        dmg = modify(dmg, 6144 if wm == (3, 2) else 2048)
    if crit:
        dmg = dmg * 3 // 2
    dmg = dmg * roll // 100
    if move["type"] and move["type"].lower() in attacker.types:  # STAB (TODO: Adaptability)
        dmg = dmg * 3 // 2
    dmg = int(dmg * eff)
    if attacker.status == "brn" and not special and not guts:
        dmg //= 2
    if held:
        fm = items.final_mod(attacker, defender, move, eff, berry_ok)
        if fm != 4096:
            dmg = modify(dmg, fm)
    return max(1, dmg)
