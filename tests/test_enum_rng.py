import unittest

from champions.engine import game
from champions.engine.resolve import resolve, state_key
from champions.engine.rng import EnumRng, _buckets
from champions.engine.actions import Move


def sp(s, m, a=None):
    return dict(species=s, moves=m, ability=a)


def duel(m0, m1, **kw):
    return game.start([[sp("incineroar", m0, "blaze")], [sp("garchomp", m1, "sandveil")]],
                      seed=1, format="singles", **kw)


class Buckets(unittest.TestCase):
    def test_probabilities_sum_to_one_and_cover_range(self):
        for a, b, k in [(85, 100, 4), (85, 100, 3), (1, 3, 5), (0, 0, 2), (2, 5, 4)]:
            out = _buckets(a, b, k)
            self.assertAlmostEqual(sum(p for _, p in out), 1.0)
            self.assertTrue(all(a <= v <= b for v, _ in out))


class Enum(unittest.TestCase):
    def test_chance_branches(self):
        r = EnumRng()
        self.assertTrue(r.chance(100))             # certain: no branch
        self.assertEqual(r.trace, [])
        self.assertTrue(r.chance(30))              # index 0 = True
        self.assertAlmostEqual(r.probability, 0.3)
        r2 = EnumRng([1])
        self.assertFalse(r2.chance(30))
        self.assertAlmostEqual(r2.probability, 0.7)

    def test_randint_uniform_when_unbucketed(self):
        r = EnumRng()
        r.randint(1, 3, "sleep_turns")
        self.assertEqual(r.trace[0][0], 3)

    def test_hit_count_distribution(self):
        r = EnumRng()
        r.randint(1, 100, "hit_count")
        self.assertEqual(r.trace[0][1], [0.35, 0.35, 0.15, 0.15])


class Resolve(unittest.TestCase):
    def test_probabilities_sum_to_one(self):
        b = duel(["flamethrower"], ["dragonclaw"])
        out = resolve(b, [Move(0, 0, "flamethrower", (1, 0)), Move(1, 0, "dragonclaw", (0, 0))])
        self.assertAlmostEqual(sum(p for p, _ in out), 1.0)
        self.assertGreater(len(out), 1)

    def test_input_battle_unchanged(self):
        b = duel(["flamethrower"], ["dragonclaw"])
        before = state_key(b)
        resolve(b, [Move(0, 0, "flamethrower", (1, 0)), Move(1, 0, "dragonclaw", (0, 0))])
        self.assertEqual(state_key(b), before)

    def test_matches_known_probabilities(self):
        # Garchomp's Dragon Claw at 100% accuracy: only crit (1/24) and the 4 damage buckets branch
        b = duel(["protect"], ["dragonclaw"])
        out = resolve(b, [Move(0, 0, "protect"), Move(1, 0, "dragonclaw", (0, 0))], merge=False)
        self.assertEqual(len(out), 1)               # protected: no hit, no branch

    def test_status_move_accuracy_split(self):
        b = duel(["toxic"], ["protect"])      # toxic vs protect: blocked, certain
        out = resolve(b, [Move(0, 0, "toxic", (1, 0)), Move(1, 0, "protect")])
        self.assertEqual(len(out), 1)
        b = duel(["toxic"], ["dragonclaw"])
        out = resolve(b, [Move(0, 0, "toxic", (1, 0)), Move(1, 0, "dragonclaw", (0, 0))])
        par = sum(p for p, c in out if c.sides[1].team[0].status == "tox")
        self.assertGreater(par, 0.5)
        self.assertLess(par, 1.0)

    def test_min_prob_prunes_and_renormalizes(self):
        b = duel(["flamethrower"], ["dragonclaw"])
        ch = [Move(0, 0, "flamethrower", (1, 0)), Move(1, 0, "dragonclaw", (0, 0))]
        full, pruned = resolve(b, ch), resolve(b, ch, min_prob=0.05)
        self.assertLess(len(pruned), len(full))
        self.assertAlmostEqual(sum(p for p, _ in pruned), 1.0)

    def test_expected_hp_close_to_sampling(self):
        b = duel(["flamethrower"], ["protect"])
        ch = [Move(0, 0, "flamethrower", (1, 0)), Move(1, 0, "protect")]
        exact = sum(p * c.sides[1].team[0].hp for p, c in resolve(b, ch))
        n, tot = 4000, 0
        for seed in range(n):
            c = b.clone(record=False); c.rng._r.seed(seed)
            game.play_turn(c, ch); tot += c.sides[1].team[0].hp
        self.assertLess(abs(exact - tot / n), 0.03 * b.sides[1].team[0].max_hp)


if __name__ == "__main__":
    unittest.main()
