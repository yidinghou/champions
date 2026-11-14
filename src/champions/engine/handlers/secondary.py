"""Secondary effects: a chance of an extra effect on a target that was hit and is still alive.

Supports volatiles (flinch) and stat drops. TODO(secondary-effect): status, Shield Dust, Sheer Force,
Substitute, flinch-adding items.
"""
from ..hooks import on
from ..stages import change_stat


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
        if vol:
            target.add_volatile(vol)
        for stat, n in sec.get("boost", {}).items():
            change_stat(battle, target, stat, n, source=ctx.user, cause="foe")
