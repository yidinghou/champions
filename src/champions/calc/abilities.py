"""Ability effects on damage. Pure functions on the attacker's and defender's `ability`, no engine imports.

Modifiers are in 4096ths (4096 = x1) and chain with the item and terrain modifiers. Numbers are Showdown's gen 9
values; Champions may differ (flagged `verify` in the catalogue).
"""
from __future__ import annotations

from .items import chain

ATE_TYPE = {"pixilate": "Fairy", "aerilate": "Flying", "refrigerate": "Ice", "dragonize": "Dragon"}
ATE_MOD = 4915                      # x1.2 on the Normal moves an -ate ability has turned into its type
FLAG_BOOST = {                      # ability -> (move flag, modifier)
    "toughclaws": ("contact", 5325), "megalauncher": ("pulse", 6144), "strongjaw": ("bite", 6144),
    "ironfist": ("punch", 4915), "sharpness": ("slicing", 6144),
}


MOLD_BREAKERS = ("moldbreaker", "teravolt", "turboblaze")
BREAKABLE = frozenset({            # defender abilities a Mold Breaker user's move ignores
    "voltabsorb", "waterabsorb", "lightningrod", "stormdrain", "sapsipper", "motordrive", "levitate", "eelevate",
    "thickfat", "multiscale", "filter", "shellarmor", "bulletproof", "magicbounce", "clearbody", "whitesmoke",
    "hypercutter", "guarddog", "sandveil", "snowcloak", "auraguard", "contrary", "defiant", "competitive"})


def breaks(user, target):
    """Does `user`'s Mold Breaker (or Teravolt, Turboblaze) switch off `target`'s ability against this move?"""
    return user is not target and user.ability in MOLD_BREAKERS and target.ability in BREAKABLE


def base_power_mod(attacker, move, fairy_aura=False):
    """Chained base-power modifier (4096 = none) from the attacker's ability."""
    ab, mod = attacker.ability, 4096
    boost = FLAG_BOOST.get(ab)
    if boost and boost[0] in move["flags"]:
        mod = chain(mod, boost[1])
    if ab == "technician" and move["base_power"] <= 60:
        mod = chain(mod, 6144)
    if ab in ATE_TYPE and move.get("ate"):
        mod = chain(mod, ATE_MOD)
    if ab == "sheerforce" and move.get("sheer"):
        mod = chain(mod, 5325)
    if ab == "firemane" and move["type"] == "Fire":
        mod = chain(mod, 6144)
    if fairy_aura and move["type"] == "Fairy":
        mod = chain(mod, 5448)                   # x1.33 for every Fairy move on the field
    return mod


def attack_stat(a, attacker, defender, move, weather):
    """The attack stat after abilities: Huge Power and Pure Power, Solar Power in sun, the defender's Thick Fat."""
    special = move["category"] == "Special"
    if attacker.ability in ("hugepower", "purepower") and not special:
        a *= 2
    if attacker.ability == "solarpower" and weather == "sun" and special:
        a = a * 3 // 2
    if defender.ability == "thickfat" and move["type"] in ("Fire", "Ice"):
        a = a // 2
    return a


def stab(attacker):
    """(numerator, denominator) of the same-type bonus: 3/2, or 2 with Adaptability."""
    return (2, 1) if attacker.ability == "adaptability" else (3, 2)


def defense_mod(defender, eff, move=None):
    """Chained final-damage modifier from the defender's ability: Multiscale at full HP, Filter on a super
    effective hit, Aura Guard against contact moves."""
    mod = 4096
    if defender.ability == "auraguard" and move is not None and "contact" in move["flags"]:
        mod = chain(mod, 2048)
    if defender.ability == "multiscale" and defender.hp == defender.max_hp:
        mod = chain(mod, 2048)
    if defender.ability == "filter" and eff > 1:
        mod = chain(mod, 3072)
    return mod
