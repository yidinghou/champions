"""Event log record, and the fixed lists of event kinds and hook names (one source of truth)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Event:
    turn: int
    kind: str
    data: dict = field(default_factory=dict)

    def to_dict(self):
        return {"turn": self.turn, "kind": self.kind, "data": self.data}

    def __str__(self):
        body = " ".join(f"{k}={v}" for k, v in self.data.items())
        return f"T{self.turn} {self.kind:<9} {body}"


# What can appear in the log. Stages that stop a target log one of the abort kinds.
EVENT_KINDS = frozenset({
    "start", "turn", "switch", "mega", "move", "damage", "heal", "recoil", "boost", "status",
    "volatile", "faint", "win", "rng",
    # aborts
    "fail", "immune", "protected", "missed", "blocked",
})

# Points where handlers (abilities, items, effects) can attach. Fired by the pipeline and turn loop.
HOOK_NAMES = frozenset({
    "on_switch_in",        # a mon entered (battle start, switch, replacement)
    "on_try_boost",        # a stat change is about to happen; handler may block or flip it
    "on_try_hit",          # before damage, after targets are chosen
    "on_hit",              # after each hit's damage: self-drops, secondaries
    "on_after_all_hits",   # after the hit loop: recoil, drain
    "on_residual",         # end of turn
})
