"""Recoil and drain, from the damage actually dealt (capped by the target's remaining HP)."""
from ..hooks import on


def _dealt(ctx):
    return sum(ctx.damage.values())


@on("on_after_all_hits", "effect:recoil")
def recoil(battle, ctx):
    total = _dealt(ctx)
    if total <= 0:
        return
    n, d = ctx.effects["recoil"]
    amount = max(1, total * n // d)
    battle.log_event("recoil", mon=ctx.user.ref, amount=amount)
    ctx.user.take(amount)


@on("on_after_all_hits", "effect:drain")
def drain(battle, ctx):
    total = _dealt(ctx)
    if total <= 0:
        return
    n, d = ctx.effects["drain"]
    amount = max(1, total * n // d)
    if ctx.user.item == "bigroot":
        amount = amount * 5324 // 4096           # x1.3
    ctx.user.heal(amount)
