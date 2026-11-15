"""Moves that change who is on the field: pivots and forced switches.

Pivot (U-turn, Volt Switch, Flip Turn, Parting Shot, Chilly Reception, Baton Pass): once the move has done its
work the user switches out for a bench mon. The player's choice can name the replacement (`Move.pivot_to`, a team
index); without one the first living bench mon comes in. It happens only if the move got as far as hitting (so not
if it missed, was Protected or was immune), the user is still standing, and there is a bench. Baton Pass hands the
stat stages, confusion and Leech Seed to the replacement before its entry effects run.
Forced switch (Dragon Tail, Circle Throw, Roar, Whirlwind): after the move the target, if it is alive and has a
bench, is swapped for a random bench mon (seeded RNG, label "forceswitch"). It happens before an Eject Button or
Red Card could react.
Numbers and rules are Showdown's gen 9; Champions may differ.
"""
from __future__ import annotations

from .actions import Switch
from .items import switch_candidates

BATON_VOLATILES = ("confusion", "leechseed")


def on_field(battle, mon):
    return mon.idx in battle.sides[mon.side].active


def _slot(battle, mon):
    return battle.sides[mon.side].active.index(mon.idx)


def pivot(ctx):
    """The user switches out after its move (U-turn and friends)."""
    from .game import run_switch
    b, user = ctx.battle, ctx.user
    if user.fainted or ctx.failed or not on_field(b, user):
        return
    bench = switch_candidates(b, user)
    if not bench:
        return
    to = ctx.pivot_to if ctx.pivot_to in bench else bench[0]
    passing = None
    if ctx.effects["pivot"] == "baton":
        passing = {"stages": dict(user.stages),
                   "volatiles": {k: v for k, v in user.volatiles.items() if k in BATON_VOLATILES}}
    run_switch(b, Switch(user.side, _slot(b, user), to), cause=ctx.move_id, passing=passing)


def force_out(ctx):
    """Dragon Tail, Circle Throw, Roar, Whirlwind: each surviving target is replaced by a random bench mon."""
    from .game import run_switch
    b = ctx.battle
    for t in list(ctx.targets):
        if t is ctx.user or t.fainted or not on_field(b, t):
            continue
        bench = switch_candidates(b, t)
        if bench:
            run_switch(b, Switch(t.side, _slot(b, t), b.rng.choice(bench, "forceswitch")), cause=ctx.move_id)
