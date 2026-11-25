"""Choose a move by playing games, instead of searching a tree.

Build the same one-turn table as the live solver (rows = our joint actions, columns = theirs, from
prior.candidate_joint_actions). Fill each cell with the mean result of random games that start with that pair of
actions: play the pair's first turn on a copy of the position, then let a playout policy choose for both sides until
somebody wins (or MAX_PLAYOUT_TURNS pass). Solve the table as a matrix game, so the answer is a mix, like the live
solver's.

The root options are the top 2 damaging moves and the best switch per slot (see ROOT).
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import List

from ..engine import game
from ..engine.actions import Move, Switch
from ..engine.rng import Rng
from .actions import describe, slot_choices
from .matrix import solve_matrix
from .prior import candidate_joint_actions, pressure
from .search import Result, get_pool

MAX_PLAYOUT_TURNS = 60
ROOT = dict(moves=2, status=0, switches=1)        # search.LIVE's root filter


def _pick_slots(battle, side, rnd, choose):
    """One choice per active slot of `side`, picked by choose(battle, side, slot, choices, rnd) from that slot's legal
    choices. No two slots switch to the same Pokemon and at most one Mega Evolves; a slot left with nothing legal
    is skipped."""
    out, switched, mega = [], set(), False
    for slot, choices in slot_choices(battle, side).items():
        legal = [c for c in choices
                 if not (isinstance(c, Switch) and c.to in switched) and not (isinstance(c, Move) and c.mega and mega)]
        if not legal:
            continue
        c = choose(battle, side, slot, legal, rnd)
        if isinstance(c, Switch):
            switched.add(c.to)
        elif c.mega:
            mega = True
        out.append(c)
    return out


def random_choices(battle, side, rnd):
    """Uniform over each slot's legal choices."""
    return _pick_slots(battle, side, rnd, lambda b, s, slot, legal, r: r.choice(legal))


def _strongest(battle, side, slot, legal, rnd):
    user = battle.sides[side].mon_at(slot)
    scored = [(pressure(battle, user, c), c) for c in legal if isinstance(c, Move)]
    scored = [(p, c) for p, c in scored if p is not None]
    if not scored:
        moves = [c for c in legal if isinstance(c, Move)]
        return rnd.choice(moves or legal)
    top = max(p for p, _ in scored)
    return rnd.choice([c for p, c in scored if p == top])


def greedy_choices(battle, side, rnd, explore=0.1):
    """Each slot uses its strongest move (by prior.pressure, ties at random); one time in ten a random choice.
    It never deliberately switches or uses a status move."""
    def choose(b, s, slot, legal, r):
        return r.choice(legal) if r.random() < explore else _strongest(b, s, slot, legal, r)
    return _pick_slots(battle, side, rnd, choose)


POLICIES = {"random": random_choices, "greedy": greedy_choices}


def result(battle):
    """+1 if side 0 won, -1 if side 1 won, 0 for a draw or an unfinished game."""
    return 1.0 if battle.winner == 0 else -1.0 if battle.winner == 1 else 0.0


def playout(battle, policy, rnd, max_turns=MAX_PLAYOUT_TURNS):
    """Play `battle` to the end with `policy` choosing for both sides. Changes `battle`. Returns result(battle)."""
    pick = POLICIES[policy] if isinstance(policy, str) else policy
    for _ in range(max_turns):
        if battle.winner is not None:
            break
        choices = pick(battle, 0, rnd) + pick(battle, 1, rnd)
        if not choices:
            break
        game.play_turn(battle, choices)
    return result(battle)


@dataclass
class RolloutStats:
    playouts: int = 0
    cells: int = 0
    min_per_cell: int = 0
    max_per_cell: int = 0
    seconds: float = 0.0
    counts: List[List[int]] = field(default_factory=list)


def _first_turn(battle, row, col, rnd):
    """A copy of the position after the cell's first turn."""
    b = battle.clone(rng=Rng(rnd.getrandbits(32)), record=False)
    game.play_turn(b, row + col)
    return b


def _fill(battle, rows, cols, policy, rnd, budget=None, per_cell=None):
    """Round-robin over every cell: each playout plays the cell's first turn, then plays out. With a budget it stops
    at the deadline but every cell gets at least one playout; with per_cell=n it plays exactly n rounds.
    Returns (totals, counts)."""
    n, m = len(rows), len(cols)
    totals = [[0.0] * m for _ in range(n)]
    counts = [[0] * m for _ in range(n)]
    deadline = None if budget is None else time.perf_counter() + budget
    rounds = 0
    while True:
        if per_cell is not None and rounds >= per_cell:
            break
        for i in range(n):
            for j in range(m):
                if rounds >= 1 and deadline is not None and time.perf_counter() >= deadline:
                    return totals, counts
                b = _first_turn(battle, rows[i], cols[j], rnd)
                totals[i][j] += playout(b, policy, rnd)
                counts[i][j] += 1
        rounds += 1
        if per_cell is None and deadline is None:
            break
    return totals, counts


def worker_seed(seed, k):
    return seed * 1_000_003 + k


def _fill_task(args):
    battle, rows, cols, policy, seed, budget, per_cell = args
    return _fill(battle, rows, cols, policy, random.Random(seed), budget, per_cell)


def _trivial(battle, seconds=0.0):
    v = result(battle)
    return Result(v, ["no choices"], ["no choices"], [[v]], [1.0], [1.0], RolloutStats(0, 1, 0, 0, seconds, [[0]]),
                  [[]], [[]], "no choices")


def solve_rollout(battle, budget=5.0, per_cell=None, policy="random", seed=0, root=ROOT, workers=1):
    """Fill the root table with playouts and solve it. budget: seconds (ignored when per_cell is given); per_cell:
    playouts per cell. workers > 1: each worker fills the whole table on search.get_pool and the counts are summed.
    The input battle is not changed."""
    t0 = time.perf_counter()
    rows, cols = candidate_joint_actions(battle, 0, **root), candidate_joint_actions(battle, 1, **root)
    if battle.winner is not None or not rows or not cols:
        return _trivial(battle)
    if workers > 1:
        each = None if per_cell is None else max(1, -(-per_cell // workers))
        pool = get_pool(workers)
        futs = [pool.submit(_fill_task, (battle, rows, cols, policy, worker_seed(seed, k),
                                         None if per_cell else budget, each)) for k in range(workers)]
        parts = [f.result() for f in futs]
        totals = [[sum(p[0][i][j] for p in parts) for j in range(len(cols))] for i in range(len(rows))]
        counts = [[sum(p[1][i][j] for p in parts) for j in range(len(cols))] for i in range(len(rows))]
    else:
        totals, counts = _fill(battle, rows, cols, policy, random.Random(worker_seed(seed, 0)),
                               None if per_cell else budget, per_cell)
    matrix = [[totals[i][j] / counts[i][j] for j in range(len(cols))] for i in range(len(rows))]
    value, x, y = solve_matrix(matrix)
    flat = [c for r in counts for c in r]
    stats = RolloutStats(sum(flat), len(flat), min(flat), max(flat), time.perf_counter() - t0, counts)
    return Result(value, [describe(battle, r) for r in rows], [describe(battle, c) for c in cols], matrix, x, y,
                  stats, rows, cols, f"{stats.playouts} {policy} playouts")
