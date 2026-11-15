"""Enumerate the outcomes of one turn: resolve(battle, choices) -> [(probability, battle after)]."""
from __future__ import annotations

from .game import play_turn
from .rng import EnumRng


# Every dataclass field of Mon / Side / Battle is either part of the key or listed as fixed for a whole battle
# (or irrelevant). tests/test_resolve.py fails if a field is added to the state without being placed in one list.
MON_KEYED = ("hp", "status", "status_turns", "stages", "volatiles", "last_move", "turns_out", "pp", "mega")
MON_FIXED = ("species", "types", "ability", "item", "moves", "stats", "max_hp", "side", "idx", "_log")
SIDE_KEYED = ("active", "conditions", "mega_used")
SIDE_FIXED = ("team",)
BATTLE_KEYED = ("arena", "turn", "winner")
BATTLE_IGNORED = ("sides", "rng", "format", "log", "record")      # log and rng do not affect what happens next here


def _freeze(v):
    return repr(sorted(v.items())) if isinstance(v, dict) else tuple(v) if isinstance(v, list) else v


def state_key(b):
    """Hashable summary of everything that affects the future, so identical outcomes can be merged."""
    mons = tuple(tuple(_freeze(getattr(m, f)) for f in MON_KEYED) for s in b.sides for m in s.team)
    sides = tuple(tuple(_freeze(getattr(s, f)) for f in SIDE_KEYED) for s in b.sides)
    return mons, sides, tuple(_freeze(getattr(b, f)) for f in BATTLE_KEYED)


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
        merged = {}                                   # key -> [total probability, best single path's prob, battle]
        for p, c in results:
            k = state_key(c)
            if k in merged:
                m = merged[k]
                m[0] += p
                if p > m[1]:
                    m[1], m[2] = p, c                  # show the most likely path (matters for the log)
            else:
                merged[k] = [p, p, c]
        results = [(m[0], m[2]) for m in merged.values()]
    total = sum(p for p, _ in results)
    return [(p / total, c) for p, c in results]
