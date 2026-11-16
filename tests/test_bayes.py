import random
import unittest

from champions.solver.matrix import lp_max, solve_bayes, solve_matrix


def objective(x, matrices, w):
    """sum_s w_s * min_j (x . A_s)_j, computed straight from the definition."""
    tot = sum(w)
    return sum(ws / tot * min(sum(x[i] * m[i][j] for i in range(len(x))) for j in range(len(m[0])))
               for ws, m in zip(w, matrices))


class LP(unittest.TestCase):
    def test_textbook_problem(self):
        # maximize 3x + 5y  s.t. x <= 4, 2y <= 12, 3x + 2y <= 18  ->  x=2, y=6, value 36
        z, obj = lp_max([3, 5], [[1, 0], [0, 2], [3, 2]], [4, 12, 18])
        self.assertAlmostEqual(obj, 36.0)
        self.assertAlmostEqual(z[0], 2.0)
        self.assertAlmostEqual(z[1], 6.0)

    def test_degenerate_problem_terminates(self):
        # several constraints tight at the start (b = 0): Bland's rule must not cycle
        z, obj = lp_max([1, 1], [[1, -1], [-1, 1], [1, 1]], [0, 0, 2])
        self.assertAlmostEqual(obj, 2.0)

    def test_unbounded_is_reported(self):
        with self.assertRaises(ValueError):
            lp_max([1, 0], [[0, 1]], [1])


class Bayes(unittest.TestCase):
    def test_one_game_equals_the_ordinary_solve(self):
        rnd = random.Random(1)
        for _ in range(40):
            n, m = rnd.randint(1, 5), rnd.randint(1, 5)
            A = [[rnd.uniform(-1, 1) for _ in range(m)] for _ in range(n)]
            v, x, per = solve_bayes([A], [1.0])
            self.assertAlmostEqual(v, solve_matrix(A)[0], places=6)
            self.assertAlmostEqual(per[0], v, places=9)

    def test_identical_games_equal_one_game(self):
        A = [[0.28, 0.0], [0.0, 0.27]]
        v, x, _ = solve_bayes([A, A, A], [1, 2, 3])
        self.assertAlmostEqual(v, 0.28 * 0.27 / 0.55, places=6)

    def test_value_matches_its_own_definition_and_x_is_a_distribution(self):
        rnd = random.Random(2)
        for _ in range(30):
            R = rnd.randint(2, 5)
            # each game has its own number of columns (the opponent's options) but the same rows (ours)
            mats = []
            for _ in range(rnd.randint(2, 4)):
                cols = rnd.randint(1, 4)
                mats.append([[rnd.uniform(-1, 1) for _ in range(cols)] for _ in range(R)])
            w = [rnd.random() + 0.1 for _ in mats]
            v, x, per = solve_bayes(mats, w)
            self.assertAlmostEqual(sum(x), 1.0, places=9)
            self.assertTrue(all(p >= -1e-12 for p in x))
            self.assertAlmostEqual(v, objective(x, mats, w), places=9)

    def test_optimal_against_a_brute_force_search(self):
        """No other strategy (grid over a 2-row simplex) beats the LP's."""
        rnd = random.Random(3)
        for _ in range(25):
            mats = []
            for _ in range(rnd.randint(2, 4)):
                cols = rnd.randint(1, 4)
                mats.append([[rnd.uniform(-1, 1) for _ in range(cols)] for _ in range(2)])
            w = [rnd.random() + 0.1 for _ in mats]
            v, x, _ = solve_bayes(mats, w)
            best = max(objective([p / 2000, 1 - p / 2000], mats, w) for p in range(2001))
            self.assertGreaterEqual(v, best - 1e-6)
            self.assertLessEqual(v, best + 1e-3)           # and it is not just a lucky overestimate

    def test_beats_random_strategies_with_more_rows(self):
        rnd = random.Random(4)
        mats = [[[rnd.uniform(-1, 1) for _ in range(3)] for _ in range(5)] for _ in range(4)]
        w = [1, 2, 3, 4]
        v, _, _ = solve_bayes(mats, w)
        for _ in range(3000):
            x = [rnd.random() for _ in range(5)]
            t = sum(x)
            self.assertLessEqual(objective([p / t for p in x], mats, w), v + 1e-9)

    def test_never_worse_than_averaging_each_games_own_answer(self):
        rnd = random.Random(5)
        for _ in range(30):
            mats = [[[rnd.uniform(-1, 1) for _ in range(3)] for _ in range(4)] for _ in range(3)]
            w = [rnd.random() + 0.1 for _ in mats]
            v, _, _ = solve_bayes(mats, w)
            fused = [sum(w[s] / sum(w) * solve_matrix(mats[s])[1][i] for s in range(3)) for i in range(4)]
            self.assertGreaterEqual(v, objective(fused, mats, w) - 1e-9)

    def test_knowing_the_game_never_hurts(self):
        rnd = random.Random(6)
        for _ in range(30):
            mats = [[[rnd.uniform(-1, 1) for _ in range(3)] for _ in range(4)] for _ in range(3)]
            w = [rnd.random() + 0.1 for _ in mats]
            v, _, _ = solve_bayes(mats, w)
            informed = sum(wi / sum(w) * solve_matrix(m)[0] for wi, m in zip(w, mats))
            self.assertGreaterEqual(informed, v - 1e-9)

    def test_hedges_when_the_best_action_depends_on_the_hidden_type(self):
        # row 0 is great in game 1 and bad in game 2 (and vice versa); row 2 is decent in both
        g1 = [[1.0, 1.0], [0.0, 0.0], [0.6, 0.6]]
        g2 = [[0.0, 0.0], [1.0, 1.0], [0.6, 0.6]]
        v, x, _ = solve_bayes([g1, g2], [0.5, 0.5])
        self.assertAlmostEqual(v, 0.6, places=6)
        self.assertGreaterEqual(max(x), 0.0)
        self.assertAlmostEqual(objective([0, 0, 1], [g1, g2], [0.5, 0.5]), 0.6)

    def test_mismatched_rows_rejected(self):
        with self.assertRaises(ValueError):
            solve_bayes([[[1.0]], [[1.0], [2.0]]], [1, 1])


if __name__ == "__main__":
    unittest.main()
