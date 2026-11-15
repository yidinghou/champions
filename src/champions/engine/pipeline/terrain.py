"""Stage 3b: Psychic Terrain stops a priority move aimed at a grounded foe."""
from .. import arena


def check(ctx):
    kept = []
    for t in ctx.targets:
        if arena.blocks_priority(ctx.battle, ctx.user, t, ctx.move["priority"]):
            ctx.battle.log_event("blocked", mon=t.ref, move=ctx.move_id, reason="psychic_terrain")
        else:
            kept.append(t)
    ctx.targets = kept
