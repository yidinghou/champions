"""Enumerate the outcomes of one turn: resolve(battle, choices) -> [(probability, battle after)]."""
from __future__ import annotations

from .game import play_turn
from .rng import EnumRng


def state_key(b):
    """Hashable summary of everything that affects the future, so identical outcomes can be merged."""
    mons = tuple((m.hp, m.status, m.status_turns, tuple(m.stages.values()), repr(sorted(m.volatiles.items())),
                  m.last_move, m.turns_out, tuple(sorted(m.pp.items())), m.mega)
                 for s in b.sides for m in s.team)
    sides = tuple((tuple(s.active), repr(sorted(s.conditions.items())), s.mega_used) for s in b.sides)
    return mons, sides, repr(sorted(b.arena.items())), b.turn, b.winner


def resolve(battle, choices, buckets=None, dists=None, min_prob=0.0, merge=True, record=False):
    """Play `choices` on copies of `battle` under every chance outcome.

    The input battle is not changed. Each result is (probability, battle). Outcomes with identical
    states are merged (merge=True). Branches less likely than min_prob are dropped and the rest are
    rescaled to sum to 1. buckets/dists tune the chance distribution (see EnumRng).
    """
    results, stack = [], [[]]
    while stack:
        prefix = stack.pop()
        rng = EnumRng(prefix, buckets, dists)
        c = battle.clone(rng=rng, record=record)
        play_turn(c, choices)
        trace = rng.trace
        chosen = [t[2] for t in trace]
        results.append((rng.probability, c))
        for depth in range(len(prefix), len(trace)):          # branches opened by this run
            n, probs, _ = trace[depth]
            base = 1.0
            for _, ps, i in trace[:depth]:
                base *= ps[i]
            for alt in range(1, n):
                if base * probs[alt] >= min_prob:
                    stack.append(chosen[:depth] + [alt])
    if merge:
        merged = {}
        for p, c in results:
            k = state_key(c)
            merged[k] = (merged[k][0] + p, merged[k][1]) if k in merged else (p, c)
        results = list(merged.values())
    total = sum(p for p, _ in results)
    return [(p / total, c) for p, c in results]
