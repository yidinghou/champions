"""Per-target hit loop: per hit, crit roll, damage roll, damage, then on_hit handlers."""
from ...calc.damage import damage
from .. import arena, items, screens
from ...calc.items import berry_halves
from ...calc.typechart import effectiveness
from ..hooks import fire
from .immunity import ignore_for
from ...calc.abilities import breaks
from .substitute import behind
from .targets import SPREAD

# chance of a crit per crit stage, in percent (1/24, 1/8, 1/2, always)
CRIT_PCT = (100 / 24, 12.5, 50, 100)


def hit_count(ctx):
    """Fixed count, or the 2-5 spread: 2 and 3 at 35% each, 4 and 5 at 15% each."""
    mh = ctx.move["multihit"]
    if mh is None:
        if (ctx.user.ability == "parentalbond" and ctx.move["category"] != "Status" and ctx.move["base_power"]
                and "noparentalbond" not in ctx.move["flags"] and "charge" not in ctx.move["flags"]
                and not (ctx.move["target"] in SPREAD and len(ctx.targets) > 1)):
            return 2                                   # Parental Bond: a second hit at 1/4 power
        return 1
    if isinstance(mh, int):
        return mh
    if ctx.user.ability == "skilllink":
        return 5
    r = ctx.battle.rng.randint(1, 100, "hit_count")
    return 2 if r <= 35 else 3 if r <= 70 else 4 if r <= 85 else 5


def crit_pct(ctx):
    stage = ctx.effects.get("crit_stage", 0) + (1 if ctx.user.item == "scopelens" else 0)
    return CRIT_PCT[min(stage, 3)]


def run(ctx):
    b, user = ctx.battle, ctx.user
    damaging = ctx.move["category"] != "Status" and ctx.move["base_power"]
    spread = ctx.move["target"] in SPREAD and len(ctx.targets) > 1   # only if 2+ are actually hit
    for target in list(ctx.targets):
        total, hits, dealt = 0, 0, 0
        count = hit_count(ctx)
        parental = user.ability == "parentalbond" and ctx.move["multihit"] is None and count == 2
        for _ in range(count):
            hits += 1
            b.log_event("hit", mon=target.ref, move=ctx.move_id, n=hits, spread=spread)
            if damaging:
                no_crit = target.ability in ("shellarmor", "battlearmor") and not breaks(user, target)
                crit = not no_crit and b.rng.chance(crit_pct(ctx), "crit")
                if crit:
                    b.log_event("crit", mon=target.ref, move=ctx.move_id)
                roll = b.rng.randint(85, 100, "damage_roll")
                ignore = ignore_for(user, ctx.move, target)
                dmg = damage(user, target, ctx.move, crit=crit, roll=roll, spread=spread,
                             ignore_immunity_to=ignore, weather=arena.weather_for(b, user), terrain=arena.terrain(b),
                             hit_mod=1024 if parental and hits == 2 else 4096,
                             fairy_aura=any(m.ability == "fairyaura" for s in b.sides for _, m in s.alive_active()),
                             berry_ok=items.can_eat(b, target), screens=() if user.ability == "infiltrator" else screens.active_screens(b, target.side),
                             doubles=b.format == "doubles")
                if dmg and items.can_eat(b, target) and berry_halves(target.item, ctx.move["type"],
                                        effectiveness(ctx.move["type"], target.types, ignore)):
                    items.consume(b, target, cause="weaken", move=ctx.move_id)   # the calc already halved this hit
                if behind(ctx, target):                  # the Substitute takes the hit; nothing reaches the mon
                    sub_state = target.volatiles["substitute"]
                    taken = min(dmg, sub_state["hp"])
                    sub_state["hp"] -= taken
                    ctx.sub_damage[target.ref] = ctx.sub_damage.get(target.ref, 0) + taken
                    broke = sub_state["hp"] <= 0
                    b.log_event("substitute", mon=target.ref, move=ctx.move_id, amount=taken, left=max(0, sub_state["hp"]), broke=broke)
                    if broke:
                        target.remove_volatile("substitute")
                    ctx.current = target
                    fire(b, "on_hit", ctx, ["effect:self_drop"] if "self_drop" in ctx.effects else [])   # the user's own drop still happens
                    continue
                dmg = items.cap_damage(b, target, dmg)
                before = target.hp
                dealt = target.take(dmg)
                if target.fainted and target.ability == "innardsout" and not user.fainted:
                    user.take(before)                    # Innards Out: the attacker takes the HP the holder had left
                total += dealt
            ctx.current = target
            fire(b, "on_hit", ctx, ctx.sources(user, target))
            if damaging and dealt:
                fire(b, "on_damaging_hit", ctx, ([f"item:{target.item}"] if target.item else []) + [f"ability:{target.ability}"])
            if user.item and not ctx.move.get("sheer"):
                fire(b, "on_user_hit", ctx, [f"item:{user.item}"])
            if target.fainted:
                break
        ctx.damage[target.ref] = total
        ctx.hit_count[target.ref] = hits
