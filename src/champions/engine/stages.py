"""Stat stage changes, with the hook that lets abilities block or flip them.

cause: "self" (the mon's own move, e.g. Close Combat), "foe" (a foe's move, e.g. Snarl) or
"intimidate" (a foe's ability). Foe-blockers such as Clear Body ignore "self".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .hooks import fire


@dataclass
class StatChange:
    mon: Any
    stat: str
    n: int
    source: Optional[Any] = None
    cause: str = "self"
    blocked: bool = False

    @property
    def foe_caused(self):
        return self.cause != "self"


def change_stat(battle, mon, stat, n, source=None, cause="self"):
    """Apply a stage change through on_try_boost. Returns the change actually applied (0 if blocked)."""
    ctx = StatChange(mon, stat, n, source, cause)
    fire(battle, "on_try_boost", ctx, [f"ability:{mon.ability}"])
    if ctx.blocked or ctx.n == 0:
        battle.log_event("blocked", mon=mon.ref, stat=stat, cause=cause, ability=mon.ability)
        return 0
    return mon.boost(stat, ctx.n, cause=cause)
