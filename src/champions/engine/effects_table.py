"""Hand-written effect data for moves and abilities the engine models.

moves.json has numbers (power, priority, target, flags) but no structured effects, only prose. So the
engine lists, per move, the effects it implements. A move missing from here raises Unsupported.
Effect keys: first_turn_only, volatile, target_boost, trap, status, rest, cure_team, yawn, type_immunity, secondary [{chance, volatile|boost|status}], self_drop {stat: -n}, recoil [n, d],
drain [n, d], protect, crit_stage, trick_room, weather (sun|rain|sand|snow), terrain (electric|grassy|misty|psychic),
weather_heal, weather_ball, weather_accuracy {weather: True | percent}, side_condition (reflect|lightscreen|auroraveil|tailwind),
break_screens, redirect (followme|ragepowder).
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
    "confuseray": {"volatile": "confusion"},
    "swagger": {"target_boost": {"atk": 2}, "volatile": "confusion"},
    "taunt": {"volatile": "taunt"},
    "encore": {"volatile": "encore"},
    "disable": {"volatile": "disable"},
    "leechseed": {"volatile": "leechseed"},
    "firespin": {"trap": {"turns": [4, 5], "dmg": True}},
    "meanlook": {"trap": {"turns": None, "dmg": False}},
    "rest": {"rest": True},
    "healbell": {"cure_team": True},
    "yawn": {"yawn": True},
    "trickroom": {"trick_room": True},
    "icebeam": {"secondary": [{"chance": 10, "status": "frz"}]},
    "sunnyday": {"weather": "sun"},
    "raindance": {"weather": "rain"},
    "sandstorm": {"weather": "sand"},
    "snowscape": {"weather": "snow"},
    "electricterrain": {"terrain": "electric"},
    "grassyterrain": {"terrain": "grassy"},
    "mistyterrain": {"terrain": "misty"},
    "psychicterrain": {"terrain": "psychic"},
    "moonlight": {"weather_heal": True},
    "synthesis": {"weather_heal": True},
    "morningsun": {"weather_heal": True},
    "weatherball": {"weather_ball": True},
    "thunder": {"secondary": [{"chance": 30, "status": "par"}], "weather_accuracy": {"rain": True, "sun": 50}},
    "hurricane": {"secondary": [{"chance": 30, "volatile": "confusion"}], "weather_accuracy": {"rain": True, "sun": 50}},
    "followme": {"redirect": "followme"},
    "ragepowder": {"redirect": "ragepowder"},
    "thunderbolt": {"secondary": [{"chance": 10, "status": "par"}]},
    "hydropump": {},
    "reflect": {"side_condition": "reflect"},
    "lightscreen": {"side_condition": "lightscreen"},
    "auroraveil": {"side_condition": "auroraveil"},
    "tailwind": {"side_condition": "tailwind"},
    "brickbreak": {"break_screens": True},
    "psychicfangs": {"break_screens": True},
    "blizzard": {"secondary": [{"chance": 10, "status": "frz"}], "weather_accuracy": {"snow": True}},
}

# Abilities with modeled behaviour live in handlers/. These have none that matters for the mechanics
# modeled so far (checked by hand); anything else raises Unsupported when a team uses it.
INERT_ABILITIES = {"noability", "blaze", "overgrow", "goodasgold", "justified", "levitate", "keeneye",
                   # no effect on the status cases that use them (status is applied by moves only):
                   "cursedbody", "unaware", "quickfeet", "merciless", "pressure", "angerpoint"}
MODELED_ABILITIES = {
    "intimidate", "innerfocus", "oblivious", "owntempo", "scrappy", "guarddog",
    "clearbody", "whitesmoke", "hypercutter", "guts", "magicguard",
    # weather and terrain (see engine/arena.py)
    "drizzle", "drought", "sandstream", "snowwarning", "electricsurge", "grassysurge", "mistysurge", "psychicsurge",
    "chlorophyll", "swiftswim", "sandrush", "slushrush", "surgesurfer", "sandforce", "sandveil", "snowcloak",
    "overcoat", "raindish", "icebody", "unnerve",
    "lightningrod", "stormdrain", "sapsipper", "motordrive", "voltabsorb", "waterabsorb",
    # Mega Evolution abilities (see engine/mega.py)
    "hugepower", "purepower", "toughclaws", "adaptability", "megalauncher", "strongjaw", "ironfist", "sharpness",
    "technician", "pixilate", "aerilate", "refrigerate", "dragonize", "thickfat", "multiscale", "filter", "shellarmor",
    "noguard", "skilllink", "speedboost", "unseenfist", "piercingdrill", "infiltrator", "stalwart", "bulletproof",
    "eelevate", "regenerator", "contrary", "defiant", "competitive", "solarpower",
}


def move_effects(move_id):
    try:
        return MOVES[move_id]
    except KeyError:
        raise Unsupported(f"move not modeled: {move_id}") from None


def check_ability(ability):
    if ability not in MODELED_ABILITIES and ability not in INERT_ABILITIES:
        raise Unsupported(f"ability not modeled: {ability}")


def is_supported_move(move_id):
    """Non-raising check: would the engine simulate this move? (`move_effects` raises Unsupported instead.)"""
    return move_id in MOVES


def is_supported_ability(ability_id):
    """Non-raising check: is this ability modeled, or known to be inert? (`check_ability` raises instead.)"""
    return ability_id in MODELED_ABILITIES or ability_id in INERT_ABILITIES
