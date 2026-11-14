"""Hand-written effect data for moves and abilities the engine models.

moves.json has numbers (power, priority, target, flags) but no structured effects, only prose. So the
engine lists, per move, the effects it implements. A move missing from here raises Unsupported.
Effect keys: first_turn_only, secondary [{chance, volatile|boost}], self_drop {stat: -n}, recoil [n, d],
drain [n, d], protect, crit_stage.
"""
from __future__ import annotations

from .errors import Unsupported

MOVES = {
    "fakeout": {"first_turn_only": True, "secondary": [{"chance": 100, "volatile": "flinch"}]},
    "closecombat": {"self_drop": {"def": -1, "spd": -1}},
    "makeitrain": {"self_drop": {"spa": -1}},
    "dragonclaw": {},
    "earthquake": {},
    "surf": {},
    "extremespeed": {},
    "woodhammer": {"recoil": [1, 3]},
    "doubleedge": {"recoil": [1, 3]},
    "headsmash": {"recoil": [1, 2]},
    "gigadrain": {"drain": [1, 2]},
    "bulletseed": {},
    "stoneedge": {"crit_stage": 1},
    "protect": {"protect": True},
}

# Abilities with modeled behaviour live in handlers/. These have none that matters for the mechanics
# modeled so far (checked by hand); anything else raises Unsupported when a team uses it.
INERT_ABILITIES = {"blaze", "overgrow", "sandveil", "goodasgold", "justified"}
MODELED_ABILITIES = {
    "intimidate", "innerfocus", "oblivious", "owntempo", "scrappy", "guarddog",
    "clearbody", "whitesmoke", "hypercutter",
}


def move_effects(move_id):
    try:
        return MOVES[move_id]
    except KeyError:
        raise Unsupported(f"move not modeled: {move_id}") from None


def check_ability(ability):
    if ability not in MODELED_ABILITIES and ability not in INERT_ABILITIES:
        raise Unsupported(f"ability not modeled: {ability}")
