"""Stage 5: accuracy roll. accuracy True always hits.

Final accuracy = move accuracy x stage multiplier, where the stage is the user's accuracy stage minus
the target's evasion stage (clamped to -6..+6): (3+s)/3 for s >= 0, 3/(3-s) below.
"""
from ...calc.field import modify
from ...calc.items import chain
from .. import arena


def multiplier(stage):
    return (3 + stage) / 3 if stage >= 0 else 3 / (3 - stage)


EVASION_WEATHER = {"sand": "sandveil", "snow": "snowcloak"}   # x0.8 accuracy (3277/4096) against the holder


def final_accuracy(user, target, base, weather=None, target_moved=False):
    """Stage-adjusted accuracy, then the chained modifiers: Sand Veil/Snow Cloak (x0.8), Wide Lens (x1.1),
    Zoom Lens (x1.2, if the target already moved), Bright Powder on the target (x0.9)."""
    s = max(-6, min(6, user.stages["acc"] - target.stages["eva"]))
    acc = int(base * multiplier(s))
    mod = 4096
    if weather and EVASION_WEATHER.get(weather) == target.ability:
        mod = chain(mod, 3277)
    if user.item == "widelens":
        mod = chain(mod, 4505)
    if user.item == "zoomlens" and target_moved:
        mod = chain(mod, 4915)
    if target.item == "brightpowder":
        mod = chain(mod, 3686)
    return modify(acc, mod) if mod != 4096 else acc


def check(ctx):
    acc = ctx.move["accuracy"]
    override = arena.accuracy_override(ctx.battle, ctx.effects)
    if override is not None:
        acc = override               # True = never misses
    if acc is True or acc is None:
        return
    kept = []
    for t in ctx.targets:
        if t is ctx.user or "noguard" in (ctx.user.ability, t.ability) or ctx.battle.rng.chance(final_accuracy(ctx.user, t, acc, arena.weather(ctx.battle), t.ref in ctx.battle.arena.get("moved", ())), f"accuracy:{ctx.move_id}"):
            kept.append(t)
        else:
            ctx.battle.log_event("missed", mon=t.ref, move=ctx.move_id)
    ctx.targets = kept
