"""Weather and terrain: state in `battle.arena`, setting, end-of-turn effects, and the rules other code asks about.

State: arena["weather"] ("sun" | "rain" | "sand" | "snow") with arena["weather_turns"] left, and the same for
arena["terrain"] ("electric" | "grassy" | "misty" | "psychic"). Absent means none. Turns count the one it was set on
and, as in Showdown, the weather ends before its end-of-turn effect on the last turn.

Numbers are Showdown's gen 9 values (5 turns, 8 with the matching rock or Terrain Extender); Champions may
differ, so the catalogue flags them `verify`.
TODO(weather): Cloud Nine and Air Lock, Hydration, Dry Skin, Solar Power, Forecast, Hail-style damage (none in snow).
"""
from __future__ import annotations

from ..calc.field import is_grounded, modify

DEFAULT_TURNS = 5
EXTENDED_TURNS = 8
WEATHER_ROCK = {"sun": "heatrock", "rain": "damprock", "sand": "smoothrock", "snow": "icyrock"}
SAND_SAFE_TYPES = ("rock", "ground", "steel")
SAND_SAFE_ABILITIES = ("overcoat", "magicguard", "sandveil", "sandrush", "sandforce")
SPEED_ABILITIES = {"rain": "swiftswim", "sun": "chlorophyll", "sand": "sandrush", "snow": "slushrush"}
WEATHER_HEAL_ABILITIES = {"rain": "raindish", "snow": "icebody"}    # 1/16 max HP each turn
GRASSY_HEAL = 16
WEATHER_WORDS = {"sun": "harsh sunlight", "rain": "rain", "sand": "a sandstorm", "snow": "snow"}
TERRAIN_WORDS = {"electric": "Electric Terrain", "grassy": "Grassy Terrain", "misty": "Misty Terrain",
                 "psychic": "Psychic Terrain"}


def weather(battle):
    return battle.arena.get("weather")


def terrain(battle):
    return battle.arena.get("terrain")


def _turns(setter, rock):
    return EXTENDED_TURNS if setter is not None and setter.item == rock else DEFAULT_TURNS


def set_weather(battle, kind, setter=None, cause=None):
    """Start `kind`. Returns False (and changes nothing) if that weather is already on."""
    if weather(battle) == kind:
        return False
    n = _turns(setter, WEATHER_ROCK[kind])
    battle.arena["weather"], battle.arena["weather_turns"] = kind, n
    battle.log_event("field", effect="weather", which=kind, start=True, turns=n,
                     mon=setter.ref if setter else None, cause=cause)
    return True


def set_terrain(battle, kind, setter=None, cause=None):
    if terrain(battle) == kind:
        return False
    n = _turns(setter, "terrainextender")
    battle.arena["terrain"], battle.arena["terrain_turns"] = kind, n
    battle.log_event("field", effect="terrain", which=kind, start=True, turns=n,
                     mon=setter.ref if setter else None, cause=cause)
    return True


def end_terrain(battle, cause):
    kind = battle.arena.pop("terrain", None)
    battle.arena.pop("terrain_turns", None)
    if kind:
        battle.log_event("field", effect="terrain", which=kind, end=True, cause=cause)


def speed_multiplier(battle, mon):
    """x2 for the weather-speed abilities (Swift Swim, Chlorophyll, Sand Rush, Slush Rush) and Surge Surfer."""
    w = weather(battle)
    if w and SPEED_ABILITIES[w] == mon.ability:
        return 2
    if mon.ability == "surgesurfer" and terrain(battle) == "electric":
        return 2
    return 1


def blocks_status(battle, mon, status):
    """Reason a field effect stops `status` landing on `mon`, or None."""
    if status == "frz" and weather(battle) == "sun":
        return "sun"
    t = terrain(battle)
    if t == "misty" and is_grounded(mon):
        return "misty_terrain"
    if t == "electric" and status == "slp" and is_grounded(mon):
        return "electric_terrain"
    return None


def blocks_volatile(battle, mon, name):
    t = terrain(battle)
    if t == "misty" and name == "confusion" and is_grounded(mon):
        return "misty_terrain"
    if t == "electric" and name == "yawn" and is_grounded(mon):
        return "electric_terrain"
    return None


def blocks_priority(battle, user, target, priority):
    """Psychic Terrain stops a priority move aimed at a grounded foe."""
    return (terrain(battle) == "psychic" and priority > 0 and target.side != user.side
            and is_grounded(target))


WEATHER_BALL_TYPE = {"sun": "Fire", "rain": "Water", "sand": "Rock", "snow": "Ice"}


def adjust_move(battle, move, effects):
    """The move as it is used right now. Weather Ball: 100 power and a weather type while weather is on."""
    kind = weather(battle)
    if effects.get("weather_ball") and kind:
        return {**move, "type": WEATHER_BALL_TYPE[kind], "base_power": move["base_power"] * 2}
    return move


def accuracy_override(battle, effects):
    """Thunder, Hurricane, Blizzard: True (never misses) or a percent for the current weather, else None."""
    return effects.get("weather_accuracy", {}).get(weather(battle))


def heal_amount(max_hp, kind):
    """Moonlight, Synthesis and Morning Sun: 1/2, 2/3 in sun (Showdown's 0.667), 1/4 in other weather.
    Each goes through Showdown's 4096ths rounding, so 1/4 rounds up when max HP leaves a remainder of 3."""
    return modify(max_hp, 2732 if kind == "sun" else 2048 if kind is None else 1024)


def _by_speed(battle):
    from .turn import speed
    mons = [m for s in battle.sides for _, m in s.alive_active()]
    mons.sort(key=lambda m: -speed(battle, m))
    return mons


def weather_residual(battle):
    """Start of the end-of-turn phase: count the weather down, then (if it lasted) its effect on each mon."""
    kind = weather(battle)
    if not kind:
        return
    left = battle.arena.get("weather_turns", 0) - 1
    if left <= 0:
        battle.arena.pop("weather")
        battle.arena.pop("weather_turns", None)
        battle.log_event("field", effect="weather", which=kind, end=True, cause="expired")
        return
    battle.arena["weather_turns"] = left
    for m in _by_speed(battle):
        if kind == "sand" and not (any(t in SAND_SAFE_TYPES for t in m.types) or m.ability in SAND_SAFE_ABILITIES):
            m.take(max(1, m.max_hp // 16))
        elif WEATHER_HEAL_ABILITIES.get(kind) == m.ability:
            m.heal(max(1, m.max_hp // 16))


def terrain_heal(battle):
    """Grassy Terrain heals every grounded mon 1/16 max HP (before status damage)."""
    if terrain(battle) != "grassy":
        return
    for m in _by_speed(battle):
        if is_grounded(m):
            m.heal(max(1, m.max_hp // GRASSY_HEAL))


def terrain_tick(battle):
    """Very end of the turn: count the terrain down and end it at zero."""
    if not terrain(battle):
        return
    left = battle.arena.get("terrain_turns", 0) - 1
    if left <= 0:
        end_terrain(battle, "expired")
    else:
        battle.arena["terrain_turns"] = left
