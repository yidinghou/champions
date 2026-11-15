"""A player's choice for one active slot. Small, frozen, serialisable: this is what replays store."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

Target = Tuple[int, int]  # (side, slot)


@dataclass(frozen=True)
class Move:
    side: int
    slot: int
    move: str
    target: Optional[Target] = None
    mega: bool = False
    pivot_to: Optional[int] = None      # team index to switch to after a pivot move (U-turn...); None = first living bench mon

    def to_dict(self):
        d = {"side": self.side, "slot": self.slot, "move": self.move,
             "target": list(self.target) if self.target else None}
        if self.mega:
            d["mega"] = True
        if self.pivot_to is not None:
            d["pivot_to"] = self.pivot_to
        return d


@dataclass(frozen=True)
class Switch:
    side: int
    slot: int
    to: int

    def to_dict(self):
        return {"side": self.side, "slot": self.slot, "switch": self.to}


def from_dict(d):
    if "switch" in d:
        return Switch(d["side"], d["slot"], d["switch"])
    t = d.get("target")
    return Move(d["side"], d["slot"], d["move"], tuple(t) if t else None, bool(d.get("mega")), d.get("pivot_to"))
