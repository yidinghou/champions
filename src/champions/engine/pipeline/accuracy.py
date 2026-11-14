"""Stage 5: accuracy roll. accuracy True always hits. TODO(accuracy-evasion): stage multipliers."""


def check(ctx):
    acc = ctx.move["accuracy"]
    if acc is True or acc is None:
        return
    kept = []
    for t in ctx.targets:
        if t is ctx.user or ctx.battle.rng.chance(acc, f"accuracy:{ctx.move_id}"):
            kept.append(t)
        else:
            ctx.battle.log_event("missed", mon=t.ref, move=ctx.move_id)
    ctx.targets = kept
