"""Secondary effects: a chance of an extra effect on a target that was hit and is still alive.

Supports volatiles (flinch), stat drops and major status. TODO(secondary-effect): Shield Dust, Sheer Force,
Substitute, flinch-adding items.
"""
from .. import volatiles
from ..hooks import on
from ..stages import change_stat
from ..status import try_set_status


@on("on_hit", "effect:secondary")
def secondary(battle, ctx):
    target = ctx.current
    if target is ctx.user or target.fainted:
        return
    for sec in ctx.effects["secondary"]:
        vol = sec.get("volatile")
        if vol == "flinch" and (target.ref in battle.arena.get("moved", ()) or target.ability == "innerfocus"):
            continue                          # too late to flinch it, or it cannot flinch
        if not battle.rng.chance(sec["chance"], f"secondary:{ctx.move_id}"):
            continue
        if vol == "confusion":
            volatiles.apply(battle, target, vol, ctx.user, ctx.move_id, announce=False)
        elif vol:
            target.add_volatile(vol)
        if sec.get("status"):
            try_set_status(battle, target, sec["status"], ctx.user, ctx.move_id, announce=False)
        for stat, n in sec.get("boost", {}).items():
            change_stat(battle, target, stat, n, source=ctx.user, cause="foe")
