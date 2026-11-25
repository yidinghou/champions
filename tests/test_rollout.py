import random
import unittest

from champions.engine import game
from champions.engine.actions import Move, Switch
from champions.solver import prior, rollout
from champions.solver.actions import slot_choices


def sp(s, m, a=None, **kw):
    return dict(species=s, moves=m, ability=a, **kw)


POOL = [("incineroar", ["fakeout", "flamethrower", "closecombat", "nightslash"], "intimidate"),
        ("garchomp", ["earthquake", "dragonclaw", "rockslide", "stoneedge"], "sandveil"),
        ("venusaur", ["gigadrain", "sludgebomb", "sleeppowder", "earthquake"], "overgrow"),
        ("rotom", ["thunderwave", "surf", "shadowball", "willowisp"], "levitate"),
        ("gengar", ["shadowball", "sludgebomb", "thunderwave", "icebeam"], "cursedbody"),
        ("dragonite", ["dragonclaw", "extremespeed", "icebeam", "earthquake"], "innerfocus"),
        ("gyarados", ["surf", "icebeam", "stoneedge", "earthquake"], "intimidate"),
        ("salamence", ["dragonclaw", "flamethrower", "earthquake", "rockslide"], "intimidate")]


def doubles(seed):
    mons = random.Random(seed).sample(POOL, 8)
    return game.start([[sp(*m) for m in mons[:4]], [sp(*m) for m in mons[4:]]], seed=1, format="doubles")


def won_singles(flip=False):
    """Dragonite faces a 1 HP Venusaur: whoever has Dragonite wins."""
    a, b = [sp("dragonite", ["extremespeed"], "innerfocus")], [sp("venusaur", ["gigadrain"], "overgrow", hp=1)]
    return game.start([b, a] if flip else [a, b], seed=1, format="singles")


class Policies(unittest.TestCase):
    def test_policies_stay_legal_through_whole_games(self):
        for name, policy in rollout.POLICIES.items():
            for seed in range(3):
                b = doubles(seed)
                rnd = random.Random(seed)
                for _ in range(40):
                    if b.winner is not None:
                        break
                    choices = policy(b, 0, rnd) + policy(b, 1, rnd)
                    game.validate(b, choices)            # raises on an illegal choice
                    game.play_turn(b, choices)

    def test_one_choice_per_active_slot(self):
        b = doubles(0)
        for policy in rollout.POLICIES.values():
            for side in (0, 1):
                picks = policy(b, side, random.Random(3))
                self.assertEqual(sorted(c.slot for c in picks), sorted(slot for slot, _ in b.sides[side].alive_active()))

    def test_greedy_uses_the_strongest_move(self):
        b = doubles(1)
        rnd = random.Random(0)
        user = b.sides[0].mon_at(0)
        legal = slot_choices(b, 0)[0]
        best = max(p for p in (prior.pressure(b, user, c) for c in legal if isinstance(c, Move)) if p is not None)
        hits = 0
        for _ in range(200):
            c = [c for c in rollout.greedy_choices(b, 0, rnd) if c.slot == 0][0]
            if isinstance(c, Move) and prior.pressure(b, user, c) == best:
                hits += 1
        self.assertGreater(hits, 150)

    def test_a_playout_runs_on_a_copy(self):
        b = doubles(2)
        before = b.turn
        rollout.playout(b.clone(record=False), "random", random.Random(0))
        self.assertEqual(b.turn, before)

    def test_a_won_position_is_worth_plus_or_minus_one(self):
        for flip, want in ((False, 1.0), (True, -1.0)):
            r = rollout.solve_rollout(won_singles(flip), per_cell=3)
            self.assertEqual(r.value, want)


class SolveRollout(unittest.TestCase):
    def test_same_seed_same_answer(self):
        b = doubles(3)
        r1 = rollout.solve_rollout(b, per_cell=2, seed=5)
        r2 = rollout.solve_rollout(b, per_cell=2, seed=5)
        self.assertEqual((r1.value, r1.matrix, r1.row_mix), (r2.value, r2.matrix, r2.row_mix))

    def test_shape_and_input_unchanged(self):
        b = doubles(4)
        turn, hp = b.turn, [m.hp for s in b.sides for m in s.team]
        r = rollout.solve_rollout(b, per_cell=1)
        self.assertEqual((len(r.matrix), len(r.matrix[0])), (len(r.rows), len(r.cols)))
        self.assertEqual((len(r.row_actions), len(r.col_actions)), (len(r.rows), len(r.cols)))
        self.assertAlmostEqual(sum(r.row_mix), 1.0, places=6)
        self.assertAlmostEqual(sum(r.col_mix), 1.0, places=6)
        self.assertEqual((b.turn, [m.hp for s in b.sides for m in s.team]), (turn, hp))
        self.assertEqual(r.stats.min_per_cell, 1)

    def test_a_budget_fills_every_cell(self):
        r = rollout.solve_rollout(doubles(5), budget=0.0)
        self.assertGreaterEqual(r.stats.min_per_cell, 1)
        self.assertLessEqual(r.stats.max_per_cell - r.stats.min_per_cell, 1)

    def test_a_finished_position_has_no_choices(self):
        b = won_singles()
        game.play_turn(b, [Move(0, 0, "extremespeed", (1, 0))])
        self.assertIsNotNone(b.winner)
        r = rollout.solve_rollout(b)
        self.assertEqual((r.label, len(r.rows), len(r.cols), r.value), ("no choices", 1, 1, 1.0))


if __name__ == "__main__":
    unittest.main()
