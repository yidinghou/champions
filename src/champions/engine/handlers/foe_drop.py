"""Abilities that block or flip foe-caused stat drops. Self-caused drops (Close Combat) are ignored."""
from ..hooks import on


def _block_foe_drop(stats=None):
    def handler(battle, ctx):
        if ctx.foe_caused and ctx.n < 0 and (stats is None or ctx.stat in stats):
            ctx.blocked = True
    return handler


for _ab in ("clearbody", "whitesmoke"):
    on("on_try_boost", f"ability:{_ab}")(_block_foe_drop())
on("on_try_boost", "ability:hypercutter")(_block_foe_drop({"atk"}))


@on("on_try_boost", "ability:guarddog")
def guard_dog(battle, ctx):
    """Guard Dog turns Intimidate's drop into a +1 Attack boost."""
    if ctx.cause == "intimidate":
        ctx.n = 1
