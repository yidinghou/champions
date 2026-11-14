"""One move, as fixed stages. Each stage removes targets from ctx.targets or stops the move, and logs why.

can_move -> targets -> protect -> immunity -> accuracy -> per hit: damage, on_hit -> on_after_all_hits.
A target removed by a stage gets no later stage: no damage, no effects, no self-drop.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..effects_table import move_effects
from ..hooks import fire
from ..teams import moves_data
from . import accuracy, can_move, hit, immunity, protect, targets


@dataclass
class MoveContext:
    battle: Any
    user: Any
    move_id: str
    move: Dict[str, Any]            # moves.json entry
    effects: Dict[str, Any]         # effects_table entry
    chosen: Optional[tuple] = None  # (side, slot) the player picked
    targets: List[Any] = field(default_factory=list)
    spread: bool = False
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


STAGES = [targets.resolve, protect.check, immunity.check, accuracy.check]


def run_move(battle, user, move_id, chosen=None):
    ctx = MoveContext(battle, user, move_id, moves_data()[move_id], move_effects(move_id), chosen)
    if not can_move.check(ctx):
        return ctx
    battle.log_event("move", mon=user.ref, move=move_id)
    user.pp[move_id] = max(0, user.pp.get(move_id, 0) - 1)
    for stage in STAGES:
        stage(ctx)
        if ctx.stopped or not ctx.targets:
            return ctx
    hit.run(ctx)
    fire(battle, "on_after_all_hits", ctx, ctx.sources(user))
    return ctx
