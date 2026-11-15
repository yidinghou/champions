"""Stage 4: type immunity. Status moves skip it unless the move says `type_immunity` (Thunder Wave)."""
from types import SimpleNamespace

from ...calc.abilities import breaks
from ...calc.field import is_grounded
from ...calc.typechart import is_immune

SCRAPPY_HITS = ("ghost",)


def ignore_for(user, move, target=None):
    if user.ability == "scrappy" and move["type"] in ("Normal", "Fighting"):
        return SCRAPPY_HITS
    if target is not None and target.item == "ironball" and move["type"] == "Ground":
        return ("flying",)                                   # Iron Ball: a Flying type takes neutral Ground damage
    return ()


def check(ctx):
    move = ctx.move
    if ctx.pranked:                                   # a Prankster-boosted status move does nothing to a Dark foe
        kept = []
        for t in ctx.targets:
            if t.side != ctx.user.side and "dark" in t.types:
                ctx.battle.log_event("immune", mon=t.ref, move=ctx.move_id, ability="prankster")
            else:
                kept.append(t)
        ctx.targets = kept
    if (move["category"] == "Status" or not move["base_power"]) and not ctx.effects.get("type_immunity"):
        return
    kept = []
    for t in ctx.targets:
        if t is not ctx.user and t.ability == "bulletproof" and "bullet" in move["flags"] and not breaks(ctx.user, t):
            ctx.battle.log_event("immune", mon=t.ref, move=ctx.move_id, ability=t.ability)
            continue
        probe = SimpleNamespace(**{**t.__dict__, "ability": "noability"}) if breaks(ctx.user, t) else t
        lifted = move["type"] == "Ground" and not is_grounded(probe)     # Levitate, Air Balloon, Flying
        if t is not ctx.user and (lifted and "flying" not in t.types or is_immune(move["type"], t.types, ignore_for(ctx.user, move, t))):
            ctx.battle.log_event("immune", mon=t.ref, move=ctx.move_id)
        else:
            kept.append(t)
    ctx.targets = kept
