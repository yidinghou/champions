"""Per-target hit loop: per hit, crit roll, damage roll, damage, then on_hit handlers."""
from ...calc.damage import damage
from .. import arena
from ..hooks import fire
from .immunity import ignore_for
from .targets import SPREAD

# chance of a crit per crit stage, in percent (1/24, 1/8, 1/2, always)
CRIT_PCT = (100 / 24, 12.5, 50, 100)


def hit_count(ctx):
    """Fixed count, or the 2-5 spread: 2 and 3 at 35% each, 4 and 5 at 15% each."""
    mh = ctx.move["multihit"]
    if mh is None:
        return 1
    if isinstance(mh, int):
        return mh
    r = ctx.battle.rng.randint(1, 100, "hit_count")
    return 2 if r <= 35 else 3 if r <= 70 else 4 if r <= 85 else 5


def crit_pct(ctx):
    return CRIT_PCT[min(ctx.effects.get("crit_stage", 0), 3)]


def run(ctx):
    b, user = ctx.battle, ctx.user
    damaging = ctx.move["category"] != "Status" and ctx.move["base_power"]
    spread = ctx.move["target"] in SPREAD and len(ctx.targets) > 1   # only if 2+ are actually hit
    for target in list(ctx.targets):
        total, hits = 0, 0
        for _ in range(hit_count(ctx)):
            hits += 1
            b.log_event("hit", mon=target.ref, move=ctx.move_id, n=hits, spread=spread)
            if damaging:
                crit = b.rng.chance(crit_pct(ctx), "crit")
                if crit:
                    b.log_event("crit", mon=target.ref, move=ctx.move_id)
                roll = b.rng.randint(85, 100, "damage_roll")
                dmg = damage(user, target, ctx.move, crit=crit, roll=roll, spread=spread,
                             ignore_immunity_to=ignore_for(user, ctx.move),
                             weather=arena.weather(b), terrain=arena.terrain(b))
                total += target.take(dmg)
            ctx.current = target
            fire(b, "on_hit", ctx, ctx.sources(user, target))
            if target.fainted:
                break
        ctx.damage[target.ref] = total
        ctx.hit_count[target.ref] = hits
