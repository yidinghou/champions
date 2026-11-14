"""Field effects. Trick Room: lasts 5 turns counting the one it was used on; using it again ends it."""
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
