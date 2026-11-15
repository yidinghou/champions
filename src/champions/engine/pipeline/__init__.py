"""One move, as fixed stages. Each stage removes targets from ctx.targets or stops the move, and logs why.

can_move -> targets -> protect -> terrain -> screens -> absorb -> immunity -> accuracy -> per hit: damage, on_hit -> on_after_all_hits.
A target removed by a stage gets no later stage: no damage, no effects, no self-drop.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..effects_table import move_effects
from ..hooks import fire
from ..teams import moves_data
from .. import arena
from . import absorb, accuracy, can_move, hit, immunity, protect, screens, targets, terrain


@dataclass
class MoveContext:
    battle: Any
    user: Any
    move_id: str
    move: Dict[str, Any]            # moves.json entry
    effects: Dict[str, Any]         # effects_table entry
    chosen: Optional[tuple] = None  # (side, slot) the player picked
    targets: List[Any] = field(default_factory=list)
    spread: bool = False   # unused: hit.run decides spread from the targets that are actually hit
    damage: Dict[str, int] = field(default_factory=dict)   # target ref -> total damage dealt
    hit_count: Dict[str, int] = field(default_factory=dict)
    stopped: bool = False
    current: Any = None

    def stop(self):
        self.stopped = True
        self.targets = []

    def sources(self, *mons):
        out = [f"effect:{k}" for k in self.effects]
        for m in mons:
            out.append(f"ability:{m.ability}")
        return out


STAGES = [targets.resolve, protect.check, terrain.check, screens.check, absorb.check, immunity.check, accuracy.check]


def run_move(battle, user, move_id, chosen=None):
    effects = move_effects(move_id)
    move = arena.adjust_move(battle, moves_data()[move_id], effects)   # Weather Ball takes the weather's type
    ctx = MoveContext(battle, user, move_id, move, effects, chosen)
    if not can_move.check(ctx):
        return ctx
    battle.log_event("move", mon=user.ref, move=move_id)
    user.last_move = move_id
    if user.item == "choicescarf" and "choicelock" not in user.volatiles:
        user.add_volatile("choicelock", move_id)
    user.pp[move_id] = max(0, user.pp.get(move_id, 0) - 1)
    for stage in STAGES:
        stage(ctx)
        if ctx.stopped or not ctx.targets:
            return ctx
    hit.run(ctx)
    fire(battle, "on_after_all_hits", ctx, ctx.sources(user) + ([f"item:{user.item}"] if user.item else []))
    if ctx.move["category"] != "Status":
        for t in list(ctx.targets):                   # Eject Button and Red Card: the holder was hit and survived
            if t is not user and t.item and not t.fainted and ctx.damage.get(t.ref):
                ctx.current = t
                fire(battle, "on_after_hit_target", ctx, [f"item:{t.item}"])
    return ctx
