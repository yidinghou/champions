"""Stage 6: a Substitute stops status moves aimed at its holder (unless the move bypasses it)."""


def bypasses(ctx):
    return "bypasssub" in ctx.move["flags"] or ctx.user.ability == "infiltrator"


def behind(ctx, target):
    """Is `target` hidden behind a Substitute that this move cannot get past?"""
    return target is not ctx.user and "substitute" in target.volatiles and not bypasses(ctx)


def check(ctx):
    if ctx.move["category"] != "Status":
        return
    kept = []
    for t in ctx.targets:
        if behind(ctx, t):
            ctx.battle.log_event("fail", mon=t.ref, move=ctx.move_id, reason="substitute")
        else:
            kept.append(t)
    ctx.targets = kept
