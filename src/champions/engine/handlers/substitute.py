"""Substitute and Shed Tail: pay HP, put a substitute in front of the mon (or its replacement)."""
from ..hooks import on


@on("on_hit", "effect:substitute")
def substitute(battle, ctx):
    user = ctx.user
    cost = user.max_hp // 4
    if "substitute" in user.volatiles:
        battle.log_event("fail", mon=user.ref, move=ctx.move_id, reason="already_substitute")
        return
    if user.hp <= cost:
        battle.log_event("fail", mon=user.ref, move=ctx.move_id, reason="too_weak")
        return
    user.take(cost)                                   # a direct cost: Magic Guard does not stop it
    user.add_volatile("substitute", {"hp": cost})


@on("on_hit", "effect:shed_tail")
def shed_tail(battle, ctx):
    """Costs half the user's max HP (rounded up); the replacement gets a substitute with half of that."""
    from ..items import switch_candidates
    user = ctx.user
    cost = (user.max_hp + 1) // 2
    reason = ("no_bench" if not switch_candidates(battle, user) else
              "already_substitute" if "substitute" in user.volatiles else
              "too_weak" if user.hp <= cost else None)
    if reason:
        battle.log_event("fail", mon=user.ref, move=ctx.move_id, reason=reason)
        ctx.failed = True
        return
    user.take(cost)
    ctx.shed_hp = cost // 2
