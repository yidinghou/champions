"""Secondary effects: a chance of an extra effect on a target that was hit and is still alive.

Initial version: flinch and volatile adds. TODO(secondary-effect): boosts, status, Shield Dust,
Sheer Force, Substitute.
"""
from ..hooks import on


@on("on_hit", "effect:secondary")
def secondary(battle, ctx):
    target = ctx.current
    if target is ctx.user or target.fainted:
        return
    for sec in ctx.effects["secondary"]:
        if not battle.rng.chance(sec["chance"], f"secondary:{ctx.move_id}"):
            continue
        vol = sec.get("volatile")
        if vol == "flinch":
            if target.ref in battle.arena.get("moved", ()):
                continue                      # a flinch only works before the target has moved
            if target.ability == "innerfocus":
                continue
        if vol:
            target.add_volatile(vol)
