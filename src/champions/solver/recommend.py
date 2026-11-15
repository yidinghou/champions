"""Recommend a strategy against an opponent whose sets are only partly known (sampling version).

We draw several plausible opposing teams from a belief (champions.belief.TeamBelief) and play out each as its own
game. Our own actions are the same in every game, so each game gives a payoff matrix over the same rows. The
recommended mix is the single strategy that does best on average over those games when the opponent knows its own
set and best-replies to it (solve_bayes). Averaging per-game answers would instead assume we knew the set.
Sampling means the answer is an estimate: more samples, a steadier answer.
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from ..engine import game
from .actions import describe
from .matrix import solve_bayes
from .prior import candidate_joint_actions
from .search import solve


@dataclass
class Recommendation:
    rows: List[str]                      # our joint actions
    strategy: List[float]                # recommended probability of each
    value: float                         # expected score for us, averaged over the sampled opponents
    fused_strategy: List[float]          # the naive alternative: weighted average of each game's own best mix
    fused_value: float
    weights: List[float]                 # probability of each sampled opponent team
    sample_values: List[float]           # what `strategy` gets against each (opponent best-replying)
    sample_best: List[float]             # what we could get if we knew that opponent's set
    teams: List[List[dict]]              # the sampled opposing teams (engine specs)
    inert_share: float                   # share of sampled opposing Pokemon left with no simulable move
    seconds: float
    cells: int
    notes: List[str] = field(default_factory=list)

    @property
    def value_of_information(self) -> float:
        """How much better we would do on average if we knew the opponent's set."""
        return sum(w * b for w, b in zip(self.weights, self.sample_best)) - self.value


def _merge_duplicates(teams: Sequence[List[dict]], weights: Sequence[float]):
    seen: Dict[str, int] = {}
    out_t, out_w = [], []
    for t, w in zip(teams, weights):
        k = json.dumps(t, sort_keys=True)
        if k in seen:
            out_w[seen[k]] += w
        else:
            seen[k] = len(out_t)
            out_t.append(t)
            out_w.append(w)
    return out_t, out_w


def recommend(mine: List[dict], belief, n_samples: int = 8, depth: int = 1, seed: int = 0, view: str = "project",
              moves: Optional[int] = 2, status: int = 1, switches: int = 1, buckets: Optional[dict] = None,
              min_prob: float = 0.01, format: str = "doubles", require_moves: bool = False) -> Recommendation:
    """Our team `mine` (engine specs, leads first) against a TeamBelief with the opposing leads set.

    depth: turns to look ahead (see solve). moves/status/switches: how many actions per Pokemon to consider
    (None = every action; slow in doubles). buckets: damage-roll buckets (default 1, the fast setting)."""
    if not belief.leads:
        raise ValueError("the opposing leads must be known (TeamBelief.from_preview(..., leads=[...]))")
    buckets = buckets or {"damage_roll": 1}
    t0 = time.perf_counter()
    rng = random.Random(seed)
    teams, weights = _merge_duplicates(*zip(*belief.weighted_teams(n_samples, rng, view, require_moves)))
    battles = [game.start([mine, t], seed=1, format=format) for t in teams]

    cands = {}                                         # our joint actions, in first-seen order, shared by all games
    for b in battles:
        for combo in (candidate_joint_actions(b, 0, moves=moves, status=status, switches=switches)
                      if moves is not None else __import__("champions.solver.actions", fromlist=["x"]).joint_actions(b, 0)):
            cands.setdefault(tuple(combo), None)
    rows = [list(c) for c in cands]

    results = [solve(b, depth=depth, buckets=buckets, min_prob=min_prob, moves=moves, status=status, switches=switches,
                     root_full=False, rows=rows) for b in battles]
    matrices = [r.matrix for r in results]
    value, x, per = solve_bayes(matrices, weights)

    fused = [sum(w * r.row_mix[i] for w, r in zip(weights, results)) for i in range(len(rows))]
    fused_per = [min(sum(fused[i] * m[i][j] for i in range(len(rows))) for j in range(len(m[0]))) for m in matrices]
    fused_value = sum(w * v for w, v in zip(weights, fused_per))

    opp_mons = [(w, s) for w, t in zip(weights, teams) for s in t[:len(belief.leads)]]
    inert = sum(w for w, s in opp_mons if not s["moves"]) / max(1e-12, sum(w for w, _ in opp_mons))
    notes = []
    if inert > 0:
        notes.append(f"{inert:.0%} of the sampled opposing leads have no simulable move and so do nothing in these games")
    labels = [describe(battles[0], r, base_names=True) for r in rows]
    return Recommendation(rows=labels, strategy=x, value=value, fused_strategy=fused, fused_value=fused_value,
                          weights=list(weights), sample_values=per, sample_best=[r.value for r in results], teams=teams,
                          inert_share=inert, seconds=time.perf_counter() - t0,
                          cells=sum(r.stats.cells for r in results), notes=notes)
