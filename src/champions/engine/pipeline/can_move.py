"""Stage 1: can the user act at all?"""


def check(ctx):
    user = ctx.user
    if "flinch" in user.volatiles:
        ctx.battle.log_event("fail", mon=user.ref, move=ctx.move_id, reason="flinch")
        ctx.stop()
        return False
    if ctx.effects.get("first_turn_only") and user.turns_out > 0:
        ctx.battle.log_event("fail", mon=user.ref, move=ctx.move_id, reason="first_turn_only")
        ctx.stop()
        return False
    return True
