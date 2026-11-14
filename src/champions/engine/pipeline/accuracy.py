"""Stage 5: accuracy roll. accuracy True always hits.

Final accuracy = move accuracy x stage multiplier, where the stage is the user's accuracy stage minus
the target's evasion stage (clamped to -6..+6): (3+s)/3 for s >= 0, 3/(3-s) below.
"""


def multiplier(stage):
    return (3 + stage) / 3 if stage >= 0 else 3 / (3 - stage)


def final_accuracy(user, target, base):
    s = max(-6, min(6, user.stages["acc"] - target.stages["eva"]))
    return int(base * multiplier(s))


def check(ctx):
    acc = ctx.move["accuracy"]
    if acc is True or acc is None:
        return
    kept = []
    for t in ctx.targets:
        if t is ctx.user or ctx.battle.rng.chance(final_accuracy(ctx.user, t, acc), f"accuracy:{ctx.move_id}"):
            kept.append(t)
        else:
            ctx.battle.log_event("missed", mon=t.ref, move=ctx.move_id)
    ctx.targets = kept
