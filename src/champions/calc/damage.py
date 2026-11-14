"""Damage in Showdown's modifier order, flooring each step. Level is fixed at 50 in Champions.

Stubbed to 1.0 for now (TODO S1): weather, screens, items, abilities, terrain, Helping Hand.
"""
from __future__ import annotations

from .typechart import effectiveness

LEVEL = 50
ROLLS = tuple(range(85, 101))


def stage_multiplier(stage):
    return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)


def _stat(value, stage):
    return int(value * stage_multiplier(stage))


def damage(attacker, defender, move, *, crit=False, roll=100, spread=False, ignore_immunity_to=()):
    """attacker/defender: engine Mon-like (stats, stages, types, status). move: a moves.json entry.
    Returns an int; 0 if the defender is immune."""
    bp = move["base_power"]
    if not bp or move["category"] == "Status":
        return 0
    special = move["category"] == "Special"
    a_key, d_key = ("spa", "spd") if special else ("atk", "def")
    a_stage, d_stage = attacker.stages[a_key], defender.stages[d_key]
    if crit:  # a crit ignores the attacker's drops and the defender's boosts
        a_stage, d_stage = max(a_stage, 0), min(d_stage, 0)
    a = _stat(attacker.stats[a_key], a_stage)
    d = _stat(defender.stats[d_key], d_stage)

    eff = effectiveness(move["type"], defender.types, ignore_immunity_to)
    if eff == 0:
        return 0
    dmg = (2 * LEVEL // 5 + 2) * bp * a // d // 50 + 2
    if spread:
        dmg = dmg * 3 // 4
    # TODO(S1): weather
    if crit:
        dmg = dmg * 3 // 2
    dmg = dmg * roll // 100
    if move["type"].lower() in attacker.types:  # STAB (TODO: Adaptability)
        dmg = dmg * 3 // 2
    dmg = int(dmg * eff)
    if attacker.status == "brn" and not special:
        dmg //= 2
    return max(1, dmg)
