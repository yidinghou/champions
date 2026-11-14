"""Stage 4: type immunity. Status moves skip it unless the move says `type_immunity` (Thunder Wave)."""
from ...calc.typechart import is_immune

SCRAPPY_HITS = ("ghost",)


def ignore_for(user, move):
    if user.ability == "scrappy" and move["type"] in ("Normal", "Fighting"):
        return SCRAPPY_HITS
    return ()


def check(ctx):
    move = ctx.move
    if (move["category"] == "Status" or not move["base_power"]) and not ctx.effects.get("type_immunity"):
        return
    kept = []
    for t in ctx.targets:
        if t is not ctx.user and is_immune(move["type"], t.types, ignore_for(ctx.user, move)):
            ctx.battle.log_event("immune", mon=t.ref, move=ctx.move_id)
        else:
            kept.append(t)
    ctx.targets = kept
