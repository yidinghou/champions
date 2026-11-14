"""Status moves (Will-O-Wisp, Toxic, Thunder Wave, Sleep Powder): inflict the status on each target hit."""
from ..hooks import on
from ..status import try_set_status


@on("on_hit", "effect:status")
def inflict(battle, ctx):
    try_set_status(battle, ctx.current, ctx.effects["status"], ctx.user, ctx.move_id)
