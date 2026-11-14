"""Stage 1: can the user act at all? Sleep and freeze, then flinch, then Disable/Taunt/confusion."""
from .. import status, volatiles


def _stop(ctx, reason):
    ctx.battle.log_event("fail", mon=ctx.user.ref, move=ctx.move_id, reason=reason)
    ctx.stop()
    return False


def check(ctx):
    user = ctx.user
    reason = status.before_move(ctx.battle, user, ctx.move)
    if reason:
        return _stop(ctx, reason)
    if "flinch" in user.volatiles:
        return _stop(ctx, "flinch")
    reason = volatiles.before_move(ctx.battle, user, ctx.move_id, ctx.move)
    if reason:
        return _stop(ctx, reason)
    if ctx.effects.get("first_turn_only") and user.turns_out > 0:
        return _stop(ctx, "first_turn_only")
    return True
