"""Stage 3a: Magic Bounce sends a reflectable status move back at its user."""
from ...calc.abilities import breaks


def check(ctx):
    from . import run_bounced
    if ctx.bounced or ctx.move["category"] != "Status" or "reflectable" not in ctx.move["flags"]:
        return
    kept, bounced = [], []
    for t in ctx.targets:
        if t is not ctx.user and t.ability == "magicbounce" and not breaks(ctx.user, t):
            bounced.append(t)
        else:
            kept.append(t)
    ctx.targets = kept
    for holder in bounced:
        ctx.battle.log_event("bounce", mon=holder.ref, move=ctx.move_id, to=ctx.user.ref)
        run_bounced(ctx.battle, holder, ctx.move_id, ctx.user)
