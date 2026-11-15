"""Field effects. Trick Room: lasts 5 turns counting the one it was used on; using it again ends it.
Weather and terrain (moves and abilities that set them, healing moves that read the weather) live in arena.py."""
from .. import arena
from ..hooks import on

TRICK_ROOM_TURNS = 5


@on("on_hit", "effect:trick_room")
def trick_room(battle, ctx):
    if battle.arena.get("trick_room"):
        battle.arena.pop("trick_room")
        battle.log_event("field", effect="trick_room", end=True, cause="reused", mon=ctx.user.ref)
    else:
        battle.arena["trick_room"] = TRICK_ROOM_TURNS
        battle.log_event("field", effect="trick_room", start=True, turns=TRICK_ROOM_TURNS, mon=ctx.user.ref)


def tick_field(battle):
    """End of turn: count Trick Room down and end it at zero."""
    left = battle.arena.get("trick_room", 0)
    if left:
        if left - 1 > 0:
            battle.arena["trick_room"] = left - 1
        else:
            battle.arena.pop("trick_room")
            battle.log_event("field", effect="trick_room", end=True, cause="expired")


@on("on_hit", "effect:weather")
def set_weather_move(battle, ctx):
    kind = ctx.effects["weather"]
    if not arena.set_weather(battle, kind, ctx.user, cause=ctx.move_id):
        battle.log_event("fail", mon=ctx.user.ref, move=ctx.move_id, reason=f"already_{kind}")


@on("on_hit", "effect:terrain")
def set_terrain_move(battle, ctx):
    kind = ctx.effects["terrain"]
    if not arena.set_terrain(battle, kind, ctx.user, cause=ctx.move_id):
        battle.log_event("fail", mon=ctx.user.ref, move=ctx.move_id, reason=f"already_{kind}")


@on("on_hit", "effect:weather_heal")
def weather_heal(battle, ctx):
    """Moonlight, Synthesis, Morning Sun: heal by the weather. Full HP is a failure, as for any heal."""
    user = ctx.user
    if user.hp == user.max_hp:
        battle.log_event("fail", mon=user.ref, move=ctx.move_id, reason="full_hp")
        return
    user.heal(arena.heal_amount(user.max_hp, arena.weather(battle)))


WEATHER_SETTERS = {"drizzle": "rain", "drought": "sun", "sandstream": "sand", "snowwarning": "snow"}
TERRAIN_SETTERS = {"electricsurge": "electric", "grassysurge": "grassy", "mistysurge": "misty",
                   "psychicsurge": "psychic"}


def _weather_setter(kind):
    def handler(battle, mon):
        arena.set_weather(battle, kind, mon, cause=mon.ability)      # already on: nothing happens, silently
    return handler


def _terrain_setter(kind):
    def handler(battle, mon):
        arena.set_terrain(battle, kind, mon, cause=mon.ability)
    return handler


for _ab, _kind in WEATHER_SETTERS.items():
    on("on_switch_in", f"ability:{_ab}")(_weather_setter(_kind))
for _ab, _kind in TERRAIN_SETTERS.items():
    on("on_switch_in", f"ability:{_ab}")(_terrain_setter(_kind))
