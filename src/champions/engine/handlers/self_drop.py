"""Guaranteed self stat drops (Close Combat, Make It Rain). Run once after the hit loop, and only
if some target was actually hit: an immune, missed or protected target never reaches the hit loop."""
from ..hooks import on
from ..stages import change_stat


@on("on_after_all_hits", "effect:self_drop")
def self_drop(battle, ctx):
    if not ctx.damage:
        return
    for stat, n in ctx.effects["self_drop"].items():
        change_stat(battle, ctx.user, stat, n, cause="self")
