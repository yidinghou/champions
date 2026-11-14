"""Entry abilities. Initial version: Intimidate and the abilities that block it."""
from ..hooks import on
from ..stages import change_stat

INTIMIDATE_IMMUNE = ("innerfocus", "oblivious", "owntempo", "scrappy")


@on("on_switch_in", "ability:intimidate")
def intimidate(battle, mon):
    """Each living adjacent foe's Attack drops by 1. TODO: Substitute skips it."""
    for _, foe in battle.sides[1 - mon.side].alive_active():
        change_stat(battle, foe, "atk", -1, source=mon, cause="intimidate")


def _block_intimidate(battle, ctx):
    if ctx.cause == "intimidate":
        ctx.blocked = True


for _ab in INTIMIDATE_IMMUNE:
    on("on_try_boost", f"ability:{_ab}")(_block_intimidate)
