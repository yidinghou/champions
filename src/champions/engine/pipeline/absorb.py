"""Stage 3d: an ability that eats the move's type (Volt Absorb, Lightning Rod...) stops it, and boosts or heals."""
from .. import redirect


def check(ctx):
    kept = []
    for t in ctx.targets:
        effect = redirect.absorbs(t, ctx.move) if t is not ctx.user else None
        if effect:
            redirect.absorb(ctx.battle, t, ctx.move_id, effect)
        else:
            kept.append(t)
    ctx.targets = kept
