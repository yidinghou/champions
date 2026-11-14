"""Per-target hit loop: damage, then on_hit handlers (self-drop, secondaries, ...)."""
from ...calc.damage import damage
from ..hooks import fire
from .immunity import ignore_for


def hit_count(ctx):
    return 1  # TODO(multi-hit): fixed and 2-5 hit counts


def run(ctx):
    b, user = ctx.battle, ctx.user
    damaging = ctx.move["category"] != "Status" and ctx.move["base_power"]
    for target in list(ctx.targets):
        total = 0
        for _ in range(hit_count(ctx)):
            if damaging:
                roll = b.rng.randint(85, 100, "damage_roll")
                dmg = damage(user, target, ctx.move, roll=roll, spread=ctx.spread,
                             ignore_immunity_to=ignore_for(user, ctx.move))
                total += target.take(dmg)
            ctx.current = target
            fire(b, "on_hit", ctx, ctx.sources(user, target))
            if target.fainted:
                break
        ctx.damage[target.ref] = total
