"""Hand-written effect data for moves and abilities the engine models.

moves.json has numbers (power, priority, target, flags) but no structured effects, only prose. So the
engine lists, per move, the effects it implements. A move missing from here raises Unsupported.
Effect keys: first_turn_only, status, rest, cure_team, yawn, type_immunity, secondary [{chance, volatile|boost|status}], self_drop {stat: -n}, recoil [n, d],
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
    "snarl": {"secondary": [{"chance": 100, "boost": {"spa": -1}}]},
    "shadowball": {"secondary": [{"chance": 20, "boost": {"spd": -1}}]},
    "ironhead": {"secondary": [{"chance": 30, "volatile": "flinch"}]},
    "rockslide": {"secondary": [{"chance": 30, "volatile": "flinch"}]},
    "dracometeor": {"self_drop": {"spa": -2}},
    "doublehit": {},
    "pinmissile": {},
    "rockblast": {},
    "nightslash": {"crit_stage": 1},
    "aerialace": {},
    "willowisp": {"status": "brn"},
    "toxic": {"status": "tox"},
    "thunderwave": {"status": "par", "type_immunity": True},
    "sleeppowder": {"status": "slp"},
    "hypnosis": {"status": "slp"},
    "poisonjab": {"secondary": [{"chance": 30, "status": "psn"}]},
    "sludgebomb": {"secondary": [{"chance": 30, "status": "psn"}]},
    "flamethrower": {"secondary": [{"chance": 10, "status": "brn"}]},
    "bodyslam": {},
    "rest": {"rest": True},
    "healbell": {"cure_team": True},
    "yawn": {"yawn": True},
    "icebeam": {"secondary": [{"chance": 10, "status": "frz"}]},
}

# Abilities with modeled behaviour live in handlers/. These have none that matters for the mechanics
# modeled so far (checked by hand); anything else raises Unsupported when a team uses it.
INERT_ABILITIES = {"noability", "blaze", "overgrow", "sandveil", "goodasgold", "justified", "levitate",
                   # no effect on the status cases that use them (status is applied by moves only):
                   "thickfat", "cursedbody", "unaware", "quickfeet", "merciless", "pressure", "angerpoint"}
MODELED_ABILITIES = {
    "intimidate", "innerfocus", "oblivious", "owntempo", "scrappy", "guarddog",
    "clearbody", "whitesmoke", "hypercutter", "guts", "magicguard",
}


def move_effects(move_id):
    try:
        return MOVES[move_id]
    except KeyError:
        raise Unsupported(f"move not modeled: {move_id}") from None


def check_ability(ability):
    if ability not in MODELED_ABILITIES and ability not in INERT_ABILITIES:
        raise Unsupported(f"ability not modeled: {ability}")
