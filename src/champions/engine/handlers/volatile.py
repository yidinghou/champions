"""Moves that add a volatile: Confuse Ray, Swagger, Taunt, Encore, Disable, Leech Seed, Fire Spin, Mean Look."""
from .. import volatiles
from ..hooks import on
from ..stages import change_stat


@on("on_hit", "effect:target_boost")
def target_boost(battle, ctx):
    t = ctx.current
    if not t.fainted:
        for stat, n in ctx.effects["target_boost"].items():
            change_stat(battle, t, stat, n, source=ctx.user, cause="foe")


@on("on_hit", "effect:volatile")
def add_volatile(battle, ctx):
    volatiles.apply(battle, ctx.current, ctx.effects["volatile"], ctx.user, ctx.move_id)


@on("on_hit", "effect:trap")
def trap(battle, ctx):
    cfg = ctx.effects["trap"]
    volatiles.trap(battle, ctx.current, ctx.user, ctx.move_id, cfg["turns"], cfg["dmg"])
