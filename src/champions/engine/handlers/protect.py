"""Protect: blocks the rest of the turn. Consecutive uses succeed with chance 1/3 per previous use."""
from ..hooks import on


@on("on_hit", "effect:protect")
def protect(battle, ctx):
    user = ctx.user
    chain = user.volatiles.get("protect_chain", 0)
    if battle.rng.chance(100 / 3 ** chain, "protect"):
        user.add_volatile("protect")
        user.volatiles["protect_chain"] = chain + 1
    else:
        battle.log_event("fail", mon=user.ref, move=ctx.move_id, reason="protect_chain")
        user.volatiles["protect_chain"] = 0
