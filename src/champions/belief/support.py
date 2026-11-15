"""What the engine can actually simulate, and how much of a belief that covers.

Two views of a set:
  project - delete moves the engine cannot simulate, swap an unsimulable ability for the inert 'noability',
            and keep the set. Gives usable opponents, but they look less capable than they are.
  strict  - drop the whole set if any move or ability is unsupported. Faithful, but little survives today.
Items are labels only: the engine models none, so they never count as supported.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from ..engine.effects_table import is_supported_ability, is_supported_move

INERT_ABILITY = "noability"


def move_ok(move: str) -> bool:
    return is_supported_move(move)


def ability_ok(ability: str) -> bool:
    return is_supported_ability(ability)


@dataclass
class Coverage:
    """How much of a belief's probability the engine can represent. All fractions are 0..1."""
    strict_mass: float          # chance a sampled set is fully simulable (every move and the ability supported, not Mega)
    move_share: float           # expected share of a set's moves that are supported
    ability_share: float        # chance the ability is supported
    item_share: float           # always 0.0 until the engine models items
    moves_dropped: float        # expected number of unsupported moves per set (what the project view deletes)
    tail_moves: Optional[float]  # usage the source did not list (see SetPrior.tails)
    tail_spreads: float
    empty_mass: float = 0.0     # chance the project view leaves a set with no simulable move at all (an inert opponent)


def coverage(moves: Dict[Tuple[str, ...], float], ia: Dict[tuple, float], tails: Dict[str, float]) -> Coverage:
    p_moves_ok = sum(p for c, p in moves.items() if all(move_ok(m) for m in c))
    p_abil_ok = sum(p for (_, a, mega), p in ia.items() if ability_ok(a))
    p_strict_ia = sum(p for (_, a, mega), p in ia.items() if ability_ok(a) and mega is None)
    exp_total = sum(p * len(c) for c, p in moves.items())
    exp_ok = sum(p * sum(1 for m in c if move_ok(m)) for c, p in moves.items())
    return Coverage(strict_mass=p_moves_ok * p_strict_ia, move_share=exp_ok / exp_total if exp_total else 0.0,
                    ability_share=p_abil_ok, item_share=0.0, moves_dropped=(exp_total - exp_ok),
                    tail_moves=tails.get("moves"), tail_spreads=tails.get("spreads", 0.0),
                    empty_mass=sum(p for c, p in moves.items() if not any(move_ok(m) for m in c)))
