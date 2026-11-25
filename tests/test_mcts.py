import random
import unittest

from champions.solver import mcts, rollout
from champions.engine.actions import Switch
from champions.solver import prior
from tests.test_rollout import OLD_ROOT, doubles, has_protect, protect_or_lose, won_singles


class NodeKey(unittest.TestCase):
    def test_shares_damage_rolls_but_not_a_faint(self):
        a = doubles(0)
        b = a.clone()
        mon = b.sides[0].mon_at(0)
        mon.hp -= max(1, mon.max_hp // 40)                # a damage roll's difference: same tenth
        if mcts._tenths(mon) != mcts._tenths(a.sides[0].mon_at(0)):
            mon.hp = a.sides[0].mon_at(0).hp - 1
        self.assertEqual(mcts.node_key(a), mcts.node_key(b))
        self.assertNotEqual(a.sides[0].mon_at(0).hp, mon.hp)
        mon.hp = 0
        self.assertNotEqual(mcts.node_key(a), mcts.node_key(b))


class RegretMatching(unittest.TestCase):
    def test_moves_toward_the_better_row(self):
        node = mcts.Node(doubles(1), rollout.ROOT)
        rnd = random.Random(0)
        for _ in range(300):                               # row 0 always scores 1, every other row -1
            i, j = node.pick(rnd, mcts.EXPLORE)
            node.update(i, j, 1.0 if i == 0 else -1.0)
        self.assertEqual(max(range(len(node.rows)), key=lambda k: node.s0[k]), 0)


class SolveMcts(unittest.TestCase):
    def test_a_won_position_is_worth_plus_or_minus_one(self):
        self.assertEqual(mcts.solve_mcts(won_singles(False), iterations=20).value, 1.0)
        self.assertEqual(mcts.solve_mcts(won_singles(True), iterations=20).value, -1.0)

    def test_same_seed_same_answer(self):
        b = doubles(2)
        r1, r2 = (mcts.solve_mcts(b, iterations=60, seed=9) for _ in range(2))
        self.assertEqual((r1.value, r1.matrix, r1.row_mix), (r2.value, r2.matrix, r2.row_mix))

    def test_the_tree_goes_deeper_than_one_turn(self):
        r = mcts.solve_mcts(doubles(3), iterations=400, seed=1)
        self.assertGreater(r.stats.max_depth, 1)
        self.assertEqual((len(r.matrix), len(r.matrix[0])), (len(r.rows), len(r.cols)))
        self.assertAlmostEqual(sum(r.row_mix), 1.0, places=6)

    def test_the_budget_stops_the_search(self):
        r = mcts.solve_mcts(doubles(4), budget=0.5)
        self.assertLess(r.stats.seconds, 3.0)
        self.assertGreaterEqual(r.stats.iterations, 1)

    def test_no_illegal_choice_is_ever_played(self):
        # play_turn validates its choices and raises ValueError on a bad one, in the tree and in playouts alike
        for seed in range(6):
            for protect in (False, True):
                mcts.solve_mcts(doubles(seed, protect), iterations=100, seed=seed, policy="greedy")

    def test_it_finds_protect(self):
        r = mcts.solve_mcts(protect_or_lose(), iterations=300, seed=1)
        got = {row: m[0] for row, m in zip(r.rows, r.matrix)}
        self.assertEqual(got, {"protect": 1.0, "gigadrain": -1.0})
        self.assertEqual(r.rows[max(range(len(r.rows)), key=lambda i: r.row_mix[i])], "protect")
        self.assertLess(r.value, 1.0)                  # the average mix starts uniform, so it is not all on Protect
        old = mcts.solve_mcts(protect_or_lose(), iterations=300, seed=1, root=OLD_ROOT)
        self.assertEqual(old.value, -1.0)

    def test_the_root_has_protect_and_every_switch(self):
        r = mcts.solve_mcts(doubles(1, protect=True), iterations=20)
        self.assertTrue(has_protect(r.row_actions))
        pairs = {(c.slot, c.to) for joint in r.row_actions for c in joint if isinstance(c, Switch)}
        self.assertEqual(len(pairs), 4)


if __name__ == "__main__":
    unittest.main()
