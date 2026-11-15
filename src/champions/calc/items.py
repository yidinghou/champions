"""Item effects on damage. Pure functions on the attacker's and defender's `item`, no engine imports.

Modifiers are in 4096ths (4096 = x1) and chain: two of them multiply first, then round once, as in Showdown.
Numbers are Showdown's gen 9 values; Champions may differ (flagged `verify` in the catalogue).
"""
from __future__ import annotations

TYPE_BOOST = {          # item -> type it boosts by x1.2 (4915/4096)
    "silkscarf": "Normal", "charcoal": "Fire", "mysticwater": "Water", "magnet": "Electric", "miracleseed": "Grass",
    "nevermeltice": "Ice", "blackbelt": "Fighting", "poisonbarb": "Poison", "softsand": "Ground", "sharpbeak": "Flying",
    "twistedspoon": "Psychic", "silverpowder": "Bug", "hardstone": "Rock", "spelltag": "Ghost", "dragonfang": "Dragon",
    "blackglasses": "Dark", "metalcoat": "Steel", "fairyfeather": "Fairy",
}
TYPE_BOOST_MOD = 4915
BAND_MOD = 4505           # Muscle Band (physical) and Wise Glasses (special): x1.1
LIFE_ORB_MOD = 5324       # x1.3
EXPERT_BELT_MOD = 4915    # x1.2 on a super effective hit
RESIST_BERRY = {          # berry -> type whose super effective hit it halves (Chilan: any Normal hit)
    "occaberry": "Fire", "passhoberry": "Water", "wacanberry": "Electric", "rindoberry": "Grass", "yacheberry": "Ice",
    "chopleberry": "Fighting", "kebiaberry": "Poison", "shucaberry": "Ground", "cobaberry": "Flying",
    "payapaberry": "Psychic", "tangaberry": "Bug", "chartiberry": "Rock", "kasibberry": "Ghost", "habanberry": "Dragon",
    "colburberry": "Dark", "babiriberry": "Steel", "roseliberry": "Fairy", "chilanberry": "Normal",
}


def chain(a, b):
    """Combine two 4096ths modifiers."""
    return (a * b + 2048) >> 12


def base_power_mod(attacker, move):
    """Chained base-power modifier (4096 = none) from the attacker's item."""
    item, mod = attacker.item, 4096
    if TYPE_BOOST.get(item) == move["type"]:
        mod = chain(mod, TYPE_BOOST_MOD)
    if item == "muscleband" and move["category"] == "Physical":
        mod = chain(mod, BAND_MOD)
    if item == "wiseglasses" and move["category"] == "Special":
        mod = chain(mod, BAND_MOD)
    return mod


def berry_halves(item, move_type, eff):
    """Does this held item halve this hit? (The engine consumes the berry when it does.)"""
    t = RESIST_BERRY.get(item)
    return t is not None and move_type == t and (eff > 1 or t == "Normal")


def final_mod(attacker, defender, move, eff, berry_ok=True):
    """Chained modifier on the final damage from Life Orb, Expert Belt and the defender's resist berry."""
    mod = 4096
    if attacker.item == "lifeorb":
        mod = chain(mod, LIFE_ORB_MOD)
    if attacker.item == "expertbelt" and eff > 1:
        mod = chain(mod, EXPERT_BELT_MOD)
    if berry_ok and berry_halves(defender.item, move["type"], eff):
        mod = chain(mod, 2048)
    return mod


def attack_stat_mod(attacker):
    """Light Ball doubles Pikachu's Attack and Sp. Atk."""
    return 2 if attacker.item == "lightball" and attacker.species == "pikachu" else 1
