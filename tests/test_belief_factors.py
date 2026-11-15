import itertools
import unittest

from champions.belief import factors as F


class Inclusion(unittest.TestCase):
    def test_scale_sums_to_k_and_caps(self):
        p = F.scale_inclusion([99, 90, 80, 70, 60, 50, 40, 30, 20, 10])
        self.assertAlmostEqual(sum(p), 4.0, places=9)
        self.assertTrue(all(0 < x <= F.CAP for x in p))

    def test_few_moves_have_one_set(self):
        self.assertEqual(F.scale_inclusion([80, 50, 30]), [1.0, 1.0, 1.0])
        self.assertEqual(F.combo_distribution(["a", "b", "c"], [1, 1, 1]), {("a", "b", "c"): 1.0})
        self.assertEqual(len(F.combo_distribution(list("abcd"), [1, 1, 1, 1])), 1)

    def test_fit_matches_targets(self):
        pcts = [80.9, 42.7, 39.3, 38.0, 37.2, 31.3, 30.0, 20.0, 10.0, 5.0]
        p = F.scale_inclusion(pcts)
        names = [f"m{i}" for i in range(len(p))]
        dist = F.combo_distribution(names, F.fit_inclusion(p))
        self.assertAlmostEqual(sum(dist.values()), 1.0, places=9)
        inc = F.inclusion_of(dist)
        for n, target in zip(names, p):
            self.assertAlmostEqual(inc[n], target, places=6)

    def test_degenerate_high_rates_do_not_crash(self):
        p = F.scale_inclusion([100, 100, 100, 100, 100, 5])
        dist = F.combo_distribution(list("abcdef"), F.fit_inclusion(p))
        self.assertAlmostEqual(sum(dist.values()), 1.0, places=9)
        inc = F.inclusion_of(dist)
        self.assertAlmostEqual(inc["a"], 4 / 5.05 * 0.995, places=2)    # five "always" moves share four slots
        self.assertLess(inc["f"], 0.1)

    def test_number_of_sets(self):
        dist = F.combo_distribution(list("abcdefg"), F.fit_inclusion(F.scale_inclusion([50] * 7)))
        self.assertEqual(len(dist), 35)          # C(7, 4)


class Enumeration(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(F.normalize({"a": 1, "b": 3}), {"a": 0.25, "b": 0.75})
        self.assertEqual(F.normalize({"a": 0.0}), {"a": 0.0})        # all-zero stays zero, no division

    def test_best_first_is_descending_and_complete(self):
        fs = [[("a", .6), ("b", .4)], [("x", .5), ("y", .3), ("z", .2)], [("p", .9), ("q", .1)]]
        out = list(F.best_first(fs))
        probs = [p for _, p in out]
        self.assertEqual(probs, sorted(probs, reverse=True))
        self.assertEqual(len(out), 12)
        self.assertAlmostEqual(sum(probs), 1.0)
        self.assertEqual(out[0][0], ("a", "x", "p"))
        self.assertEqual({o for o, _ in out}, set(itertools.product("ab", "xyz", "pq")))

    def test_best_first_empty_factor(self):
        self.assertEqual(list(F.best_first([[("a", 1.0)], []])), [])


if __name__ == "__main__":
    unittest.main()
