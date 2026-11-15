"""Stage 3c: Brick Break and Psychic Fangs shatter the target side's screens, before the hit, if the target is
not immune to the move's type (so a Protected or immune target keeps them)."""
from ...calc.typechart import is_immune
from .. import screens


def check(ctx):
    if not ctx.effects.get("break_screens"):
        return
    for side in sorted({t.side for t in ctx.targets if t.side != ctx.user.side
                        and not is_immune(ctx.move["type"], t.types)}):
        for name in screens.SCREENS:
            screens.remove_condition(ctx.battle, side, name, ctx.move_id)
