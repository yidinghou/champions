import random
import unittest

from champions.engine import game
from champions.engine.resolve import state_key
from champions.solver import solve
from champions.solver.matrix import prune_dominated, solve_matrix


def sp(s, m, a=None, **kw):
    return dict(species=s, moves=m, ability=a, **kw)


def duel(a, b, format="singles"):
    return game.start([a, b], seed=1, format=format)


class MatrixSolver(unittest.TestCase):
    def check(self, A):
        v, x, y = solve_matrix(A)
        self.assertAlmostEqual(sum(x), 1.0, places=6)
        self.assertAlmostEqual(sum(y), 1.0, places=6)
        n, m = len(A), len(A[0])
        for j in range(m):   # x guarantees at least v against every column
            self.assertGreaterEqual(sum(x[i] * A[i][j] for i in range(n)), v - 1e-6)
        for i in range(n):   # y holds the row player to at most v
            self.assertLessEqual(sum(y[j] * A[i][j] for j in range(m)), v + 1e-6)
        return v, x, y

    def test_matching_pennies(self):
        v, x, y = self.check([[1, -1], [-1, 1]])
        self.assertAlmostEqual(v, 0.0, places=6)
        self.assertAlmostEqual(x[0], 0.5, places=6)

    def test_saddle_point(self):
        v, x, y = self.check([[3, 1], [2, 0]])
        self.assertAlmostEqual(v, 1.0, places=6)

    def test_demo_2x2(self):
        v, x, y = self.check([[0.28, 0.0], [0.0, 0.27]])
        self.assertAlmostEqual(v, 0.28 * 0.27 / 0.55, places=6)

    def test_negative_values(self):
        self.check([[-0.5, -0.2], [-0.1, -0.9]])

    def test_random_matrices(self):
        rnd = random.Random(7)
        for _ in range(200):
            n, m = rnd.randint(1, 7), rnd.randint(1, 7)
            self.check([[rnd.uniform(-1, 1) for _ in range(m)] for _ in range(n)])

    def test_prune_keeps_value(self):
        rnd = random.Random(3)
        for _ in range(100):
            A = [[rnd.uniform(-1, 1) for _ in range(5)] for _ in range(5)]
            r, c = prune_dominated(A)
            self.assertAlmostEqual(solve_matrix(A)[0], solve_matrix([[A[i][j] for j in c] for i in r])[0], places=6)


class Search(unittest.TestCase):
    def test_guaranteed_ko_is_a_win(self):
        # Garchomp (faster) one-shots a 1 HP Incineroar: side 1 wins for sure
        b = duel([sp("incineroar", ["flamethrower"], hp=1)], [sp("garchomp", ["earthquake"])])
        r = solve(b, depth=1)
        self.assertAlmostEqual(r.value, -1.0, places=6)

    def test_input_unchanged_and_probabilities(self):
        b = duel([sp("incineroar", ["flamethrower", "closecombat"])], [sp("garchomp", ["earthquake", "dragonclaw"])])
        before = state_key(b)
        r = solve(b, depth=2)
        self.assertEqual(state_key(b), before)
        self.assertAlmostEqual(sum(r.row_mix), 1.0, places=6)
        self.assertAlmostEqual(sum(r.col_mix), 1.0, places=6)
        self.assertGreater(r.stats.nodes, 1)

    def test_memo_does_not_change_answer(self):
        b = duel([sp("incineroar", ["flamethrower", "closecombat"])], [sp("garchomp", ["earthquake", "dragonclaw"])])
        a = solve(b, depth=2, memo=True, keep=None)
        c = solve(b, depth=2, memo=False, keep=None)
        self.assertAlmostEqual(a.value, c.value, places=9)

    def test_depth_changes_value_when_game_continues(self):
        b = duel([sp("incineroar", ["flamethrower", "closecombat"])], [sp("garchomp", ["earthquake", "dragonclaw"])])
        self.assertNotAlmostEqual(solve(b, depth=1).value, solve(b, depth=2).value, places=3)


GOLDEN_SWITCH = ([sp("gyarados", ["surf", "earthquake", "icebeam", "stoneedge"]),
                  sp("venusaur", ["gigadrain", "sludgebomb", "earthquake", "sleeppowder"])],
                 [sp("gengar", ["shadowball", "sludgebomb", "thunderwave", "icebeam"]),
                  sp("dragonite", ["dragonclaw", "earthquake", "icebeam", "extremespeed"])])
GOLDEN_1V1 = ([sp("gyarados", ["surf", "earthquake", "icebeam", "stoneedge"])],
              [sp("dragonite", ["dragonclaw", "earthquake", "icebeam", "extremespeed"])])
ONE_BUCKET = {"damage_roll": 1}


def top_row(r):
    return max(zip(r.row_mix, r.rows))[1]


class Robustness(unittest.TestCase):
    def setUp(self):
        self.b = duel([sp("incineroar", ["flamethrower", "closecombat"])], [sp("garchomp", ["earthquake", "dragonclaw"])])

    def test_disjoint_dominance_and_topk_choices_do_not_crash(self):
        from unittest import mock
        from champions.solver import search
        with mock.patch.object(search, "prune_dominated", lambda A: ([0], [0])), \
             mock.patch.object(search, "prune_top_k", lambda A, k: ([1], [1])):
            r = solve(self.b, depth=2, dominance=True, keep=1, buckets=ONE_BUCKET)
        self.assertAlmostEqual(sum(r.row_mix), 1.0, places=6)

    def test_zero_time_limit_is_a_limit_not_no_limit(self):
        from champions.solver import SearchTimeout
        with self.assertRaises(SearchTimeout):
            solve(self.b, depth=1, time_limit=0)

    def test_no_time_limit_by_default(self):
        self.assertIsNotNone(solve(self.b, depth=1, buckets=ONE_BUCKET).value)

    def test_mega_variants_of_a_move_are_separate_choices(self):
        from unittest import mock
        from champions.engine.actions import Move
        from champions.solver import actions
        two = [Move(0, 0, "protect", (1, 0)), Move(0, 0, "protect", (1, 0), mega=True)]
        with mock.patch.object(actions.game, "legal_choices", lambda b, s: two):
            self.assertEqual(len(actions.slot_choices(self.b, 0)[0]), 2)


class Pruning(unittest.TestCase):
    """Golden positions for pruning (depth 2, 1 damage bucket). See issue #26.

    keep=k is a heuristic: it matched the exact solve under the original HP-difference score, which these goldens
    pin. The default evaluate() (status, stages, threat) is not guaranteed to prune the same way."""

    def setUp(self):
        from unittest import mock
        from champions.solver import search
        from champions.solver.evaluate import evaluate_hp
        p = mock.patch.object(search, "evaluate", evaluate_hp)
        p.start()
        self.addCleanup(p.stop)

    def test_5x5_with_switching_pruning_is_exact_and_cheaper(self):
        b = duel(*GOLDEN_SWITCH)
        exact = solve(b, depth=2, buckets=ONE_BUCKET)
        pruned = solve(b, depth=2, buckets=ONE_BUCKET, keep=1)
        self.assertAlmostEqual(pruned.value, exact.value, places=3)
        self.assertEqual(top_row(pruned), top_row(exact))
        for a, b2 in zip(sorted(pruned.row_mix), sorted(exact.row_mix)):
            self.assertAlmostEqual(a, b2, places=2)
        self.assertLess(pruned.stats.cells, 0.5 * exact.stats.cells)

    def test_1v1_narrow_pruning_misjudges_value_but_not_the_move(self):
        # one turn makes Dragon Claw look like Dragonite's best move, but two turns later Ice Beam is;
        # pruning drops Ice Beam, so Gyarados looks more dominant than it is. The recommended move is unchanged.
        b = duel(*GOLDEN_1V1)
        exact = solve(b, depth=2, buckets=ONE_BUCKET)
        narrow = solve(b, depth=2, buckets=ONE_BUCKET, keep=1)
        self.assertGreater(narrow.value, exact.value + 0.03)       # the known error
        self.assertLess(narrow.value - exact.value, 0.15)          # but small
        self.assertEqual(top_row(narrow), top_row(exact))

    def test_wider_keep_recovers_the_exact_value(self):
        b = duel(*GOLDEN_1V1)
        exact = solve(b, depth=2, buckets=ONE_BUCKET)
        self.assertAlmostEqual(solve(b, depth=2, buckets=ONE_BUCKET, keep=3).value, exact.value, places=3)


if __name__ == "__main__":
    unittest.main()
