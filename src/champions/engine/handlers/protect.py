"""Protect and its family: they block the rest of the turn. Consecutive uses succeed with chance 1/3 per previous use,
and a stalling move fails if nobody is left to act after it (Showdown's queue.willAct()).

Kinds: protect/detect (block anything with the protect flag), King's Shield (damaging moves only; contact -1 Atk),
Spiky Shield (contact: 1/8 max HP), Baneful Bunker (contact: poison), Endure (survive at 1 HP), Wide Guard (spread
moves aimed at the side) and Quick Guard (natural priority moves aimed at the side).
"""
from ..hooks import on

SIDE_GUARDS = ("wideguard", "quickguard")


@on("on_hit", "effect:protect")
def protect(battle, ctx):
    user = ctx.user
    kind = ctx.effects["protect"]
    kind = "protect" if kind is True else kind
    chain = user.volatiles.get("protect_chain", 0)
    if battle.arena.get("pending", 1) == 0:                # last to move: nothing left to protect from
        battle.log_event("fail", mon=user.ref, move=ctx.move_id, reason="last_to_move")
        user.volatiles["protect_chain"] = 0
        return
    if not battle.rng.chance(100 / 3 ** chain, "protect"):
        battle.log_event("fail", mon=user.ref, move=ctx.move_id, reason="protect_chain")
        user.volatiles["protect_chain"] = 0
        return
    user.volatiles["protect_chain"] = chain + 1
    if kind in SIDE_GUARDS:
        battle.sides[user.side].conditions[kind] = 1
        battle.log_event("field", effect="side", which=kind, side=user.side, start=True, turns=1, mon=user.ref, cause=ctx.move_id)
    elif kind == "endure":
        user.add_volatile("endure")
    else:
        user.add_volatile("protect", kind)                 # the value says which shield, for the contact effect
