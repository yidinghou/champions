"""Protect: the user is protected for the rest of the turn. TODO(protect): 1/3 consecutive-use chain."""
from ..hooks import on


@on("on_hit", "effect:protect")
def protect(battle, ctx):
    ctx.user.add_volatile("protect")
