"""Stage 5: accuracy roll. accuracy True always hits.

Final accuracy = move accuracy x stage multiplier, where the stage is the user's accuracy stage minus
the target's evasion stage (clamped to -6..+6): (3+s)/3 for s >= 0, 3/(3-s) below.
"""
from ...calc.field import modify
from .. import arena


def multiplier(stage):
    return (3 + stage) / 3 if stage >= 0 else 3 / (3 - stage)


EVASION_WEATHER = {"sand": "sandveil", "snow": "snowcloak"}   # x0.8 accuracy (3277/4096) against the holder


def final_accuracy(user, target, base, weather=None):
    s = max(-6, min(6, user.stages["acc"] - target.stages["eva"]))
    acc = int(base * multiplier(s))
    if weather and EVASION_WEATHER.get(weather) == target.ability:
        acc = modify(acc, 3277)
    return acc


def check(ctx):
    acc = ctx.move["accuracy"]
    override = arena.accuracy_override(ctx.battle, ctx.effects)
    if override is not None:
        acc = override               # True = never misses
    if acc is True or acc is None:
        return
    kept = []
    for t in ctx.targets:
        if t is ctx.user or ctx.battle.rng.chance(final_accuracy(ctx.user, t, acc, arena.weather(ctx.battle)), f"accuracy:{ctx.move_id}"):
            kept.append(t)
        else:
            ctx.battle.log_event("missed", mon=t.ref, move=ctx.move_id)
    ctx.targets = kept
