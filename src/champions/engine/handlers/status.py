"""Status moves (Will-O-Wisp, Toxic, Thunder Wave, Sleep Powder): inflict the status on each target hit."""
from .. import arena
from ..hooks import on
from ..status import REST_TURNS, YAWN_TURNS, try_set_status


@on("on_hit", "effect:status")
def inflict(battle, ctx):
    try_set_status(battle, ctx.current, ctx.effects["status"], ctx.user, ctx.move_id)


@on("on_hit", "effect:rest")
def rest(battle, ctx):
    user = ctx.user
    if user.hp == user.max_hp or user.status == "slp":
        battle.log_event("fail", mon=user.ref, move=ctx.move_id, reason="full_hp" if user.hp == user.max_hp else "already_asleep")
        return
    reason = arena.blocks_status(battle, user, "slp")
    if reason:
        battle.log_event("fail", mon=user.ref, move=ctx.move_id, reason=reason)
        return
    user.cure_status()
    user.heal(user.max_hp)
    user.set_status("slp", REST_TURNS)


@on("on_hit", "effect:cure_team")
def cure_team(battle, ctx):
    for mon in battle.sides[ctx.user.side].team:
        if not mon.fainted and mon.status:
            mon.cure_status()


@on("on_hit", "effect:yawn")
def yawn(battle, ctx):
    t = ctx.current
    if t.status or "yawn" in t.volatiles:
        battle.log_event("fail", mon=t.ref, move=ctx.move_id, reason="already_status" if t.status else "already_yawning")
        return
    reason = arena.blocks_volatile(battle, t, "yawn")
    if reason:
        battle.log_event("fail", mon=t.ref, move=ctx.move_id, reason=reason)
        return
    t.add_volatile("yawn", YAWN_TURNS)
