"""Simultaneous-move Monte Carlo tree search (SM-MCTS with regret matching).

Each node of the tree is a position where both sides choose at once. A node holds the same kind of table as the
live solver's root (rows = our joint actions, columns = theirs) and, for every cell, the mean result of the
iterations that went through it. Each side picks a row or column by regret matching on those means; an iteration
walks down the tree that way, adds one new node, plays the rest of the game with a playout policy (see rollout.py)
and backs the result up the path. The root's mean table is solved at the end like any matrix game, but the mix
returned is the average strategy the two sides played, which is what regret matching converges on.

The options at every node are the top 2 damaging moves, Protect and every switch per slot (rollout.ROOT).
Positions that differ only by a damage roll share a node (node_key rounds HP up to tenths).
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import List

from ..engine import game
from ..engine.resolve import (BATTLE_KEYED, MON_KEYED, SIDE_KEYED, _freeze)
from ..engine.rng import Rng
from .actions import describe
from .prior import candidate_joint_actions
from .rollout import ROOT, _trivial, playout, result, worker_seed
from .search import Result, get_pool

EXPLORE = 0.2
HP_STEPS = 10


def _tenths(m):
    return 0 if m.hp <= 0 else math.ceil(m.hp * HP_STEPS / m.max_hp)


def node_key(b):
    """state_key, but with HP rounded up to tenths of max HP (0 only when fainted), so positions that differ by a
    damage roll share a node."""
    mons = tuple(tuple(_tenths(m) if f == "hp" else _freeze(getattr(m, f)) for f in MON_KEYED)
                 for s in b.sides for m in s.team)
    sides = tuple(tuple(_freeze(getattr(s, f)) for f in SIDE_KEYED) for s in b.sides)
    return mons, sides, tuple(_freeze(getattr(b, f)) for f in BATTLE_KEYED)


def _strategy(regret):
    pos = [max(0.0, r) for r in regret]
    tot = sum(pos)
    return [p / tot for p in pos] if tot > 0 else [1.0 / len(regret)] * len(regret)


def _sample(weights, rnd):
    x, acc = rnd.random() * sum(weights), 0.0
    for k, w in enumerate(weights):
        acc += w
        if x < acc:
            return k
    return len(weights) - 1


class Node:
    def __init__(self, battle, root):
        self.rows = candidate_joint_actions(battle, 0, **root)
        self.cols = candidate_joint_actions(battle, 1, **root)
        n, m = len(self.rows), len(self.cols)
        self.total = [[0.0] * m for _ in range(n)]
        self.n = [[0] * m for _ in range(n)]
        self.visits, self.sum_v = 0, 0.0
        self.r0, self.r1 = [0.0] * n, [0.0] * m          # cumulative regrets
        self.s0, self.s1 = [0.0] * n, [0.0] * m          # cumulative strategies

    def mean(self, i, j):
        """Mean result of the cell; an untried cell counts as the node's average so far."""
        k = self.n[i][j]
        if k:
            return self.total[i][j] / k
        return self.sum_v / self.visits if self.visits else 0.0

    def pick(self, rnd, explore=EXPLORE):
        picked = []
        for regret, cum in ((self.r0, self.s0), (self.r1, self.s1)):
            strat = _strategy(regret)
            for k, p in enumerate(strat):
                cum[k] += p
            picked.append(_sample([(1 - explore) * p + explore / len(strat) for p in strat], rnd))
        return picked[0], picked[1]

    def update(self, i, j, v):
        self.total[i][j] += v
        self.n[i][j] += 1
        self.visits += 1
        self.sum_v += v
        here = self.mean(i, j)
        for a in range(len(self.rows)):                  # side 0 maximizes
            self.r0[a] += self.mean(a, j) - here
        for b in range(len(self.cols)):                  # side 1 minimizes
            self.r1[b] += here - self.mean(i, b)


def _iterate(battle, root_node, tree, policy, rnd, root, explore):
    """One iteration. Returns (depth reached, whether a playout was played)."""
    b = battle.clone(rng=Rng(rnd.getrandbits(32)), record=False)
    node, path, played = root_node, [], False
    while True:
        if b.winner is not None:
            v = result(b)
            break
        if not node.rows or not node.cols:
            v, played = playout(b, policy, rnd), True
            break
        i, j = node.pick(rnd, explore)
        choices = node.rows[i] + node.cols[j]
        try:
            game.validate(b, choices)
        except ValueError:                       # a shared node's options may not fit this exact position
            v, played = playout(b, policy, rnd), True
            break
        path.append((node, i, j))
        game.play_turn(b, choices)
        if b.winner is not None:
            v = result(b)
            break
        key = node_key(b)
        nxt = tree.get(key)
        if nxt is None:
            tree[key] = Node(b, root)
            v, played = playout(b, policy, rnd), True
            break
        node = nxt
    for nd, i, j in path:
        nd.update(i, j, v)
    return len(path), played


def _grow(battle, budget, iterations, policy, seed, root, explore):
    """Grow one process's tree. Returns the root's statistics as plain lists."""
    rnd = random.Random(seed)
    root_node = Node(battle, root)
    tree = {node_key(battle): root_node}
    deadline = None if budget is None else time.perf_counter() + budget
    done = playouts = max_depth = 0
    while True:
        if iterations is not None and done >= iterations:
            break
        if iterations is None and done >= 1 and time.perf_counter() >= deadline:
            break
        depth, played = _iterate(battle, root_node, tree, policy, rnd, root, explore)
        done += 1
        playouts += played
        max_depth = max(max_depth, depth)
    return dict(total=root_node.total, n=root_node.n, s0=root_node.s0, s1=root_node.s1, iterations=done,
                nodes=len(tree), max_depth=max_depth, playouts=playouts)


def _grow_task(args):
    return _grow(*args)


@dataclass
class MctsStats:
    iterations: int = 0
    nodes: int = 0
    max_depth: int = 0
    seconds: float = 0.0
    playouts: int = 0
    min_per_cell: int = 0
    max_per_cell: int = 0
    counts: List[List[int]] = field(default_factory=list)


def solve_mcts(battle, budget=5.0, iterations=None, policy="random", seed=0, root=ROOT, workers=1, explore=EXPLORE):
    """Search `battle` with SM-MCTS and return a Result. budget: seconds (ignored when iterations is given);
    iterations: how many to run. workers > 1: root parallelization, one tree per worker (on search.get_pool) with
    the root statistics summed. The input battle is not changed. matrix = the mean result per cell (an untried
    cell gets the root's average); row_mix / col_mix = the average strategies; value = x.M.y."""
    t0 = time.perf_counter()
    rows, cols = candidate_joint_actions(battle, 0, **root), candidate_joint_actions(battle, 1, **root)
    if battle.winner is not None or not rows or not cols:
        r = _trivial(battle)
        r.stats = MctsStats(0, 1, 0, 0.0, 0, 0, 0, [[0]])
        return r
    k = max(1, workers)
    each = None if iterations is None else max(1, -(-iterations // k))
    args = [(battle, None if iterations else budget, each, policy, worker_seed(seed, w), root, explore)
            for w in range(k)]
    if k > 1:
        pool = get_pool(k)
        parts = [f.result() for f in [pool.submit(_grow_task, a) for a in args]]
    else:
        parts = [_grow(*args[0])]
    n, m = len(rows), len(cols)
    total = [[sum(p["total"][i][j] for p in parts) for j in range(m)] for i in range(n)]
    cnt = [[sum(p["n"][i][j] for p in parts) for j in range(m)] for i in range(n)]
    s0 = [sum(p["s0"][i] for p in parts) for i in range(n)]
    s1 = [sum(p["s1"][j] for p in parts) for j in range(m)]
    seen = sum(map(sum, cnt))
    avg = sum(map(sum, total)) / seen if seen else 0.0
    matrix = [[total[i][j] / cnt[i][j] if cnt[i][j] else avg for j in range(m)] for i in range(n)]
    x, y = [v / sum(s0) for v in s0], [v / sum(s1) for v in s1]
    value = sum(x[i] * y[j] * matrix[i][j] for i in range(n) for j in range(m))
    flat = [c for r in cnt for c in r]
    iters = sum(p["iterations"] for p in parts)
    stats = MctsStats(iters, sum(p["nodes"] for p in parts), max(p["max_depth"] for p in parts),
                      time.perf_counter() - t0, sum(p["playouts"] for p in parts), min(flat), max(flat), cnt)
    return Result(value, [describe(battle, r) for r in rows], [describe(battle, c) for c in cols], matrix, x, y,
                  stats, rows, cols, f"MCTS, {iters} iterations ({policy} playouts)")
