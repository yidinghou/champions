"""Depth-limited expectiminimax over simultaneous-move turns.

At each node: list both sides' joint actions, resolve every pair under all chance outcomes, value each
outcome (by evaluating it, or by solving it again one level deeper), average by probability, and solve
the resulting matrix game. The node's value is the game value.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List

from ..engine.resolve import resolve, state_key
from .actions import describe, joint_actions
from .prior import candidate_joint_actions
from .evaluate import evaluate
from .matrix import prune_dominated, prune_top_k, solve_matrix


class SearchTimeout(Exception):
    """solve() ran past its time limit."""


@dataclass
class Stats:
    nodes: int = 0            # matrix games solved
    cells: int = 0            # (row, col) pairs resolved
    outcomes: int = 0         # chance outcomes produced
    memo_hits: int = 0
    pruned_cells: int = 0     # cells skipped by dominance pruning
    seconds: float = 0.0


@dataclass
class Result:
    value: float                      # expected score for side 0 under optimal play
    rows: List[str]                   # side 0 action labels
    cols: List[str]                   # side 1 action labels
    matrix: List[List[float]]         # value of each (row, col); None where pruned
    row_mix: List[float]
    col_mix: List[float]
    stats: Stats = field(default_factory=Stats)


class _Ctx:
    def __init__(self, buckets, min_prob, keep, dominance, memo, deadline, filt, deep_min_prob, root_full=True,
                 root_rows=None):
        self.buckets, self.min_prob, self.keep, self.dominance, self.memo = buckets, min_prob, keep, dominance, memo
        self.filt, self.deep_min_prob = filt, deep_min_prob     # filt: dict for candidate_joint_actions below the root, or None
        self.deadline = deadline
        self.root_full = root_full
        self.root_rows = root_rows        # fixed list of our joint actions at the root (so games can be compared)
        self.cache, self.stats = {}, Stats()


def _node(battle, depth, ctx, root=False):
    """Solve one turn. Returns (value, rows, cols, matrix, x, y)."""
    ctx.stats.nodes += 1
    if ctx.filt is None or (root and ctx.root_full):
        rows, cols = joint_actions(battle, 0), joint_actions(battle, 1)
    else:
        rows, cols = candidate_joint_actions(battle, 0, **ctx.filt), candidate_joint_actions(battle, 1, **ctx.filt)
    if root and ctx.root_rows is not None:
        rows = [list(r) for r in ctx.root_rows]
    min_prob = ctx.min_prob if root or ctx.deep_min_prob is None else ctx.deep_min_prob
    if not rows or not cols:
        v = evaluate(battle)
        return v, [], [], [[v]], [1.0], [1.0]
    outs = {}
    shallow = [[0.0] * len(cols) for _ in rows]
    for i, r in enumerate(rows):
        for j, c in enumerate(cols):
            if ctx.deadline is not None and time.perf_counter() > ctx.deadline:
                raise SearchTimeout()
            res = resolve(battle, r + c, buckets=ctx.buckets, min_prob=min_prob)
            outs[i, j] = res
            ctx.stats.cells += 1
            ctx.stats.outcomes += len(res)
            shallow[i][j] = sum(p * evaluate(b) for p, b in res)
    if depth <= 1:
        matrix = shallow
        keep_r, keep_c = list(range(len(rows))), list(range(len(cols)))
    else:
        keep_r, keep_c = list(range(len(rows))), list(range(len(cols)))
        if ctx.dominance:
            keep_r, keep_c = prune_dominated(shallow)
        if ctx.keep:
            kr, kc = prune_top_k(shallow, ctx.keep)
            both_r, both_c = [i for i in keep_r if i in kr], [j for j in keep_c if j in kc]
            keep_r, keep_c = (both_r, both_c) if both_r and both_c else (kr, kc)   # disjoint choices: trust top-k alone
        ctx.stats.pruned_cells += len(rows) * len(cols) - len(keep_r) * len(keep_c)
        matrix = [[None] * len(cols) for _ in rows]
        for i in keep_r:
            for j in keep_c:
                matrix[i][j] = sum(p * _value(b, depth - 1, ctx) for p, b in outs[i, j])
    sub = [[matrix[i][j] for j in keep_c] for i in keep_r]
    v, sx, sy = solve_matrix(sub)
    x, y = [0.0] * len(rows), [0.0] * len(cols)
    for k, i in enumerate(keep_r):
        x[i] = sx[k]
    for k, j in enumerate(keep_c):
        y[j] = sy[k]
    return v, rows, cols, matrix, x, y


def _value(battle, depth, ctx):
    if battle.winner is not None or depth <= 0:
        return evaluate(battle)
    if ctx.memo:
        key = (state_key(battle), depth)
        if key in ctx.cache:
            ctx.stats.memo_hits += 1
            return ctx.cache[key]
    v = _node(battle, depth, ctx)[0]
    if ctx.memo:
        ctx.cache[key] = v
    return v


def solve(battle, depth=2, buckets=None, min_prob=0.01, keep=None, dominance=False, memo=True, time_limit=None,
          moves=None, status=1, switches=1, root_full=True, deep_min_prob=None, rows=None):
    """Solve `battle` `depth` turns deep. The input is not changed.

    depth=1 is the plain one-turn matrix; each extra level plays one more simultaneous turn.
    buckets / min_prob control chance splitting (see EnumRng and resolve).
    keep=k: below the root's first turn, only search each side's k best actions by one-turn payoff plus
    every best reply (see prune_top_k). dominance=True also drops strictly dominated actions (unsound
    beyond one turn: it overstated a result by 8% in a benchmark). Both are heuristics; None/False = exact.
    moves=m: before building each matrix below the root, keep only each Pokemon's top m damaging moves, `status`
    status moves and `switches` switches by the cheap ranking in prior.py (None = keep every action). root_full=False
    applies it at the root too. deep_min_prob: drop chance outcomes rarer than this below the root.
    rows: a fixed list of our joint actions to use at the root instead of generating them (used to compare games
    against different opponent sets, which need the same rows). time_limit: seconds; raises SearchTimeout if exceeded.
    """
    t0 = time.perf_counter()
    filt = None if moves is None else {"moves": moves, "status": status, "switches": switches}
    ctx = _Ctx(buckets, min_prob, keep, dominance, memo, None if time_limit is None else t0 + time_limit, filt,
               deep_min_prob, root_full, rows)
    v, rows, cols, matrix, x, y = _node(battle, depth, ctx, root=True)
    ctx.stats.seconds = time.perf_counter() - t0
    return Result(v, [describe(battle, r) for r in rows], [describe(battle, c) for c in cols],
                  matrix, x, y, ctx.stats)
