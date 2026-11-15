"""One move, as fixed stages. Each stage removes targets from ctx.targets or stops the move, and logs why.

can_move -> targets -> protect -> terrain -> screens -> bounce -> absorb -> immunity -> accuracy -> substitute -> per hit: damage, on_hit -> on_after_all_hits.
A target removed by a stage gets no later stage: no damage, no effects, no self-drop.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .. import pivot
from ..effects_table import move_effects
from ..hooks import fire
from ..teams import moves_data
from .. import arena
from . import absorb, accuracy, bounce, substitute, can_move, hit, immunity, protect, screens, targets, terrain


@dataclass
class MoveContext:
    battle: Any
    user: Any
    move_id: str
    move: Dict[str, Any]            # moves.json entry
    effects: Dict[str, Any]         # effects_table entry
    chosen: Optional[tuple] = None  # (side, slot) the player picked
    pivot_to: Optional[int] = None  # the replacement the player named for a pivot move
    pranked: bool = False           # a status move whose priority Prankster raised (Dark foes are immune)
    bounced: bool = False           # this move was reflected by Magic Bounce (it cannot be reflected again)
    failed: bool = False            # a handler reported that the move did nothing (so a pivot does not follow)
    targets: List[Any] = field(default_factory=list)
    spread: bool = False   # unused: hit.run decides spread from the targets that are actually hit
    damage: Dict[str, int] = field(default_factory=dict)   # target ref -> total damage dealt
    sub_damage: Dict[str, int] = field(default_factory=dict)  # target ref -> damage a Substitute took
    shed_hp: int = 0                                          # Shed Tail: HP of the substitute the replacement gets
    hit_count: Dict[str, int] = field(default_factory=dict)
    stopped: bool = False
    current: Any = None

    def dealt_total(self):
        """Damage dealt to targets and to their Substitutes: what recoil, drain, Shell Bell and Life Orb go by."""
        return sum(self.damage.values()) + sum(self.sub_damage.values())

    def stop(self):
        self.stopped = True
        self.targets = []

    def sources(self, *mons):
        out = [f"effect:{k}" for k in self.effects]
        for m in mons:
            out.append(f"ability:{m.ability}")
        return out


STAGES = [targets.resolve, protect.check, terrain.check, screens.check, bounce.check, absorb.check, immunity.check, accuracy.check, substitute.check]


def run_bounced(battle, holder, move_id, victim):
    """Magic Bounce: `holder` uses the reflected status move on `victim` (no PP, no choice, cannot bounce again)."""
    effects = move_effects(move_id)
    ctx = MoveContext(battle, holder, move_id, moves_data()[move_id], effects, None, bounced=True)
    ctx.targets = [victim]
    battle.log_event("move", mon=holder.ref, move=move_id, bounced=True)
    for stage in STAGES[1:]:
        stage(ctx)
        if ctx.stopped or not ctx.targets:
            return
    hit.run(ctx)


def run_move(battle, user, move_id, chosen=None, pivot_to=None):
    effects = move_effects(move_id)
    if user.ability == "sheerforce" and effects.get("secondary"):
        effects = {k: v for k, v in effects.items() if k != "secondary"}      # extra effects traded for x1.3 power
    move = arena.adjust_move(battle, moves_data()[move_id], effects, user)   # Weather Ball takes the weather's type
    if user.ability == "sheerforce" and move_effects(move_id).get("secondary"):
        move = {**move, "sheer": True}
    ctx = MoveContext(battle, user, move_id, move, effects, chosen, pivot_to)
    ctx.pranked = user.ability == "prankster" and move["category"] == "Status"
    if not can_move.check(ctx):
        return ctx
    battle.log_event("move", mon=user.ref, move=move_id)
    user.last_move = move_id
    if user.ability == "protean" and "protean" not in user.volatiles and move["type"]:
        user.volatiles["protean"] = list(user.types)         # remembered so it can be undone on switch-out
        user.types = [move["type"].lower()]
        battle.log_event("ability", mon=user.ref, ability="protean", types="/".join(user.types))
    if user.item == "choicescarf" and "choicelock" not in user.volatiles:
        user.add_volatile("choicelock", move_id)
    user.pp[move_id] = max(0, user.pp.get(move_id, 0) - 1)
    for stage in STAGES:
        stage(ctx)
        if ctx.stopped or not ctx.targets:
            return ctx
    hit.run(ctx)
    berserk(ctx)
    fire(battle, "on_after_all_hits", ctx, ctx.sources(user) + ([f"item:{user.item}"] if user.item else []))
    if ctx.effects.get("force_switch"):
        pivot.force_out(ctx)                          # Dragon Tail and Roar act before any Eject Button
    if ctx.move["category"] != "Status":
        for t in list(ctx.targets):                   # Eject Button and Red Card: the holder was hit and survived
            if t is not user and t.item and not t.fainted and ctx.damage.get(t.ref) and battle.on_field(t):
                ctx.current = t
                fire(battle, "on_after_hit_target", ctx, [f"item:{t.item}"])
    if ctx.effects.get("pivot"):
        pivot.pivot(ctx)
    return ctx


def berserk(ctx):
    """Berserk: a target pushed from above half HP to half or less by this move gets +1 Sp. Atk."""
    from ..stages import change_stat
    for t in ctx.targets:
        dealt = ctx.damage.get(t.ref, 0)
        if t.ability == "berserk" and dealt and not t.fainted and t.hp * 2 <= t.max_hp < (t.hp + dealt) * 2:
            change_stat(ctx.battle, t, "spa", 1, source=t, cause="self")
