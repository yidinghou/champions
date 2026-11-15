"""Pure math for the belief module: a distribution over k-move sets from per-move inclusion rates, and
best-first enumeration of a product of independent factors. No game data in here."""
from __future__ import annotations

import heapq
import itertools
from typing import Dict, Iterator, List, Sequence, Tuple

CAP = 0.995          # keeps odds finite: a move listed at 100% is treated as 99.5%


def scale_inclusion(pcts: Sequence[float], k: int = 4, cap: float = CAP) -> List[float]:
    """Per-move usage percentages (each move's chance of being in a k-move set) -> inclusion probabilities that
    sum to k, each at most `cap`. Fewer than or exactly k moves: all 1.0 (there is only one set)."""
    n = len(pcts)
    if n <= k:
        return [1.0] * n
    p = [min(cap, max(1e-9, x / 100.0)) for x in pcts]
    total = sum(p)
    if total > k:                                  # more than k moves "always" played: shrink them all proportionally
        return [x * k / total for x in p]
    for _ in range(100):                           # fewer: scale the uncapped ones up (water-filling)
        total = sum(p)
        if abs(total - k) < 1e-12:
            break
        free = [i for i in range(n) if p[i] < cap]
        if not free:
            break
        fixed = sum(p[i] for i in range(n) if p[i] >= cap)
        f = (k - fixed) / sum(p[i] for i in free)
        for i in free:
            p[i] = min(cap, p[i] * f)
    return p


def fit_inclusion(p: Sequence[float], k: int = 4, iters: int = 500, tol: float = 1e-9) -> List[float]:
    """Odds weights w so that P(S) proportional to prod(w_i for i in S) over k-subsets has inclusion
    probabilities p (which must sum to k). Fitted by iterative scaling on the odds."""
    n = len(p)
    if n <= k:
        return [1.0] * n
    combos = list(itertools.combinations(range(n), k))
    w = [x / (1 - x) for x in p]
    for _ in range(iters):
        weights = []
        for c in combos:
            v = 1.0
            for i in c:
                v *= w[i]
            weights.append(v)
        total = sum(weights)
        pi = [0.0] * n
        for c, v in zip(combos, weights):
            for i in c:
                pi[i] += v
        pi = [x / total for x in pi]
        err = max(abs(a - b) for a, b in zip(pi, p))
        if err != err:                                # NaN: bad input; keep the last finite weights
            break
        if err < tol:
            break
        w = [wi * (pt / (1 - pt)) / (q / (1 - q)) for wi, pt, q in zip(w, p, pi)]
    return w


def combo_distribution(names: Sequence[str], w: Sequence[float], k: int = 4) -> Dict[Tuple[str, ...], float]:
    """{sorted tuple of k names: probability}. If there are k or fewer names, the single set of all of them."""
    n = len(names)
    if n <= k:
        return {tuple(sorted(names)): 1.0}
    out = {}
    for c in itertools.combinations(range(n), k):
        v = 1.0
        for i in c:
            v *= w[i]
        out[tuple(sorted(names[i] for i in c))] = v
    return normalize(out)


def inclusion_of(dist: Dict[Tuple[str, ...], float]) -> Dict[str, float]:
    """Marginal chance that each name is in a set."""
    out: Dict[str, float] = {}
    for combo, p in dist.items():
        for m in combo:
            out[m] = out.get(m, 0.0) + p
    return out


def normalize(d: Dict) -> Dict:
    """Scale values to sum to 1. An all-zero dict is returned unchanged (callers check for it)."""
    total = sum(d.values())
    return {k: v / total for k, v in d.items()} if total > 0 else dict(d)


def best_first(factors: Sequence[Sequence[Tuple[object, float]]]) -> Iterator[Tuple[Tuple, float]]:
    """Yield (one item from each factor, product of probabilities) in descending probability.
    Each factor is a list of (item, probability) sorted by descending probability."""
    if any(not f for f in factors):
        return
    start = (0,) * len(factors)
    def prob(idx):
        p = 1.0
        for f, i in zip(factors, idx):
            p *= f[i][1]
        return p
    heap = [(-prob(start), start)]
    seen = {start}
    while heap:
        negp, idx = heapq.heappop(heap)
        yield tuple(f[i][0] for f, i in zip(factors, idx)), -negp
        for d in range(len(factors)):
            nxt = idx[:d] + (idx[d] + 1,) + idx[d + 1:]
            if nxt[d] < len(factors[d]) and nxt not in seen:
                seen.add(nxt)
                heapq.heappush(heap, (-prob(nxt), nxt))
