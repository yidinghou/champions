"""Stage 3d: an ability that eats the move's type (Volt Absorb, Lightning Rod...) stops it, and boosts or heals."""
from ...calc.abilities import breaks
from .. import redirect


def check(ctx):
    kept = []
    for t in ctx.targets:
        effect = redirect.absorbs(t, ctx.move) if t is not ctx.user and not breaks(ctx.user, t) else None
        if effect:
            redirect.absorb(ctx.battle, t, ctx.move_id, effect)
        else:
            kept.append(t)
    ctx.targets = kept
