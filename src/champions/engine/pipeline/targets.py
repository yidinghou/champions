"""Stage 2: turn the move's target type plus the board into the list of mons it hits.

Supported target kinds: normal, any, self, allAdjacentFoes, allAdjacent, adjacentAlly.
Anything else raises Unsupported. Adjacency is simplified: every slot is adjacent to every other.
"""
from ..errors import Unsupported

SPREAD = {"allAdjacentFoes", "allAdjacent"}


def _foes(battle, user):
    return [m for _, m in battle.sides[1 - user.side].alive_active()]


def _ally(battle, user):
    return [m for _, m in battle.sides[user.side].alive_active() if m is not user]


def resolve(ctx):
    b, user, kind = ctx.battle, ctx.user, ctx.move["target"]
    if kind == "self":
        ctx.targets = [user]
    elif kind in ("normal", "any"):
        t = b.mon(*ctx.chosen) if ctx.chosen else None
        if t is None or t.fainted:
            foes = _foes(b, user)  # retarget to a living foe, or fail
            t = foes[0] if foes else None
        if t is None:
            b.log_event("fail", mon=user.ref, move=ctx.move_id, reason="no_target")
            return ctx.stop()
        ctx.targets = [t]
    elif kind == "allAdjacentFoes":
        ctx.targets = _foes(b, user)
    elif kind == "allAdjacent":
        ctx.targets = _foes(b, user) + _ally(b, user)
    elif kind == "adjacentAlly":
        ctx.targets = _ally(b, user)
    else:
        raise Unsupported(f"target kind not modeled: {kind}")
    if not ctx.targets:
        b.log_event("fail", mon=user.ref, move=ctx.move_id, reason="no_target")
        return ctx.stop()
    ctx.spread = kind in SPREAD and len(ctx.targets) > 1
