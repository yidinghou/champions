"""Stage 3: Protect-style block. Moves with the protect flag are stopped for a protected target."""


def check(ctx):
    if "protect" not in ctx.move["flags"]:
        return
    if ctx.user.ability in ("unseenfist", "piercingdrill") and "contact" in ctx.move["flags"]:
        return                                    # contact moves go through Protect
    kept = []
    for t in ctx.targets:
        if t is not ctx.user and t.volatiles.get("protect"):
            ctx.battle.log_event("protected", mon=t.ref, move=ctx.move_id)
        else:
            kept.append(t)
    ctx.targets = kept
