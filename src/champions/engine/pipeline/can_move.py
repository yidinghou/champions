"""Stage 1: can the user act at all?"""
from .. import status


def check(ctx):
    user = ctx.user
    if "flinch" in user.volatiles:
        ctx.battle.log_event("fail", mon=user.ref, move=ctx.move_id, reason="flinch")
        ctx.stop()
        return False
    reason = status.before_move(ctx.battle, user, ctx.move)
    if reason:
        ctx.battle.log_event("fail", mon=user.ref, move=ctx.move_id, reason=reason)
        ctx.stop()
        return False
    if ctx.effects.get("first_turn_only") and user.turns_out > 0:
        ctx.battle.log_event("fail", mon=user.ref, move=ctx.move_id, reason="first_turn_only")
        ctx.stop()
        return False
    return True
