import math
import random
import unittest

from champions.belief import AbilitySeen, Belief, ItemSeen, MoveSeen, SetHyp, project_set
from champions.belief import factors as F
from champions.belief import support as S
from champions.belief.prior import build_prior
from champions.engine import teams
from tests.test_belief_prior import GARCHOMP


def belief():
    return Belief.from_prior(build_prior("garchomp", dict(GARCHOMP), "munchstats"))


class Conditioning(unittest.TestCase):
    def test_move_seen_keeps_only_sets_with_it(self):
        b = belief().condition(MoveSeen("Power Gem"))
        self.assertTrue(all("powergem" in c for c in b.moves))
        self.assertAlmostEqual(sum(b.moves.values()), 1.0, places=9)
        self.assertAlmostEqual(b.marginals()["moves"]["powergem"], 1.0, places=9)
        self.assertLess(b.evidence, 1.0)

    def test_evidence_is_the_prior_probability_of_the_observations(self):
        b0 = belief()
        inc = b0.marginals()["moves"]["earthquake"]
        b = b0.condition(MoveSeen("earthquake"))
        self.assertAlmostEqual(b.evidence, inc, places=9)
        self.assertAlmostEqual(b.log_evidence(), math.log(inc), places=9)

    def test_four_seen_moves_leave_one_set(self):
        b = belief()
        for m in ("Earthquake", "Dragon Claw", "Rock Slide", "Protect"):
            b = b.condition(MoveSeen(m))
        self.assertEqual(list(b.moves), [("dragonclaw", "earthquake", "protect", "rockslide")])
        self.assertFalse(b.impossible)

    def test_fifth_move_is_impossible(self):
        b = belief()
        for m in ("Earthquake", "Dragon Claw", "Rock Slide", "Protect", "Stone Edge"):
            b = b.condition(MoveSeen(m))
        self.assertTrue(b.impossible)
        self.assertIn("more than 4", b.notes[-1])

    def test_item_and_ability_conditioning(self):
        b = belief().condition(ItemSeen("Life Orb"))
        self.assertEqual(set(b.marginals()["items"]), {"lifeorb"})
        b = b.condition(AbilitySeen("Sand Veil"))
        self.assertEqual(set(b.marginals()["abilities"]), {"sandveil"})
        self.assertAlmostEqual(sum(b.ia.values()), 1.0)

    def test_mega_stone_reveals_the_mega_ability(self):
        b = belief().condition(ItemSeen("Garchompite Z"))
        self.assertEqual(set(b.ia), {("garchompitez", "levitate", "garchomp-mega-z")})

    def test_order_does_not_matter_without_repairs(self):
        a = belief().condition(MoveSeen("Earthquake")).condition(ItemSeen("Life Orb")).condition(MoveSeen("Protect"))
        b = belief().condition(ItemSeen("Life Orb")).condition(MoveSeen("Protect")).condition(MoveSeen("Earthquake"))
        self.assertAlmostEqual(a.evidence, b.evidence, places=12)
        for k, v in a.moves.items():
            self.assertAlmostEqual(v, b.moves[k], places=12)

    def test_unlisted_but_legal_move_is_repaired(self):
        b = belief().condition(MoveSeen("Earthquake")).condition(MoveSeen("bite"))     # learnable, not in the data
        self.assertFalse(b.impossible)
        self.assertTrue(all("bite" in c and "earthquake" in c for c in b.moves))        # earlier evidence is kept
        self.assertTrue(any("bite" in n for n in b.notes))
        self.assertAlmostEqual(b.evidence, b.evidence)                                  # finite
        self.assertLess(b.evidence, 0.01)                                               # a repaired observation is a priori unlikely

    def test_unlearnable_move_is_impossible(self):
        b = belief().condition(MoveSeen("moonblast"))
        self.assertTrue(b.impossible)
        self.assertEqual(b.condition(MoveSeen("earthquake")), b)                        # stays impossible, unchanged

    def test_illegal_ability_is_impossible_and_legal_unlisted_is_repaired(self):
        self.assertTrue(belief().condition(AbilitySeen("Intimidate")).impossible)
        b = belief()
        b = b.condition(AbilitySeen("Sand Veil"))          # listed
        self.assertFalse(b.impossible)

    def test_unlisted_item_is_accepted(self):
        b = belief().condition(ItemSeen("Quick Claw"))
        self.assertFalse(b.impossible)
        self.assertEqual(set(b.marginals()["items"]), {"quickclaw"})

    def test_conditioning_does_not_mutate_the_original(self):
        b = belief()
        before = dict(b.moves)
        b.condition(MoveSeen("Earthquake"))
        self.assertEqual(b.moves, before)


class Views(unittest.TestCase):
    def test_archetypes_are_ordered_and_account_for_all_probability(self):
        a = belief().archetypes(k=5000, view="raw")
        ws = [w for _, w in a.items]
        self.assertEqual(ws, sorted(ws, reverse=True))
        self.assertAlmostEqual(sum(ws) + a.residual, 1.0, places=9)
        small = belief().archetypes(k=3)
        self.assertEqual(len(small.items), 3)
        self.assertGreater(small.residual, 0.0)

    def test_project_view_removes_unsupported_moves_and_abilities(self):
        for h, _ in belief().archetypes(k=300, view="project").items:
            self.assertTrue(all(S.move_ok(m) for m in h.moves))
            self.assertTrue(S.ability_ok(h.ability))
        self.assertNotIn("powergem", {m for h, _ in belief().archetypes(k=300).items for m in h.moves})

    def test_strict_view_drops_whole_sets_and_megas(self):
        a = belief().archetypes(k=300, view="strict")
        self.assertTrue(a.items)
        for h, _ in a.items:
            self.assertTrue(all(S.move_ok(m) for m in h.moves) and S.ability_ok(h.ability))
            self.assertIsNone(h.mega_form)
        self.assertAlmostEqual(sum(w for _, w in a.items) + a.residual, 1.0, places=9)

    def test_merge_items_ranks_without_items(self):
        merged = belief().archetypes(k=3000, view="project", merge_items=True)
        split = belief().archetypes(k=3000, view="project", merge_items=False)
        self.assertLess(len(merged.items), len(split.items))
        self.assertAlmostEqual(sum(w for _, w in merged.items) + merged.residual, 1.0, places=9)

    def test_bad_view_rejected(self):
        with self.assertRaises(ValueError):
            belief().archetypes(view="nope")
        with self.assertRaises(ValueError):
            belief().sample(random.Random(0), view="nope")

    def test_coverage(self):
        c = belief().coverage()
        self.assertTrue(0 < c.move_share < 1)
        self.assertEqual(c.item_share, 0.0)
        self.assertAlmostEqual(c.tail_moves, 0.075)
        self.assertLessEqual(c.strict_mass, c.ability_share + 1e-9)

    def test_sampler_matches_marginals(self):
        b, rng, n = belief(), random.Random(7), 20000
        draws = [b.sample(rng) for _ in range(n)]
        m = b.marginals()
        for move in ("earthquake", "protect", "powergem"):
            freq = sum(move in h.moves for h in draws) / n
            self.assertAlmostEqual(freq, m["moves"][move], delta=0.02)
        self.assertAlmostEqual(sum(h.item == "lifeorb" for h in draws) / n, m["items"]["lifeorb"], delta=0.02)

    def test_sampling_is_seeded(self):
        a = [belief().sample(random.Random(3), "project") for _ in range(2)]
        self.assertEqual(a[0], a[1])

    def test_strict_sampling_only_returns_simulable_sets(self):
        rng = random.Random(1)
        for _ in range(200):
            h = belief().sample(rng, "strict")
            self.assertTrue(all(S.move_ok(m) for m in h.moves) and S.ability_ok(h.ability) and h.mega_form is None)

    def test_strict_sampling_can_come_up_empty(self):
        b = belief().condition(MoveSeen("Power Gem"))              # unsupported move in every set
        self.assertIsNone(b.sample(random.Random(0), "strict"))


class SetHypSpec(unittest.TestCase):
    def test_spec_builds_in_the_engine(self):
        for h, _ in belief().archetypes(k=20, view="project").items:
            mon = teams.build_mon(h.spec("garchomp"))
            self.assertEqual(mon.moves, list(h.moves))
            self.assertGreater(mon.max_hp, 0)

    def test_mega_set_uses_the_mega_form(self):
        h = SetHyp(("earthquake",), "garchompitez", "levitate", "jolly", "0/32/0/0/2/32", "garchomp-mega-z")
        self.assertEqual(h.spec("garchomp")["species"], "garchomp-mega-z")
        self.assertEqual(teams.build_mon(h.spec("garchomp")).species, "garchomp-mega-z")

    def test_project_set(self):
        h = SetHyp(("powergem", "protect"), None, "roughskin", "jolly", "0/32/0/0/2/32")
        p = project_set(h)
        self.assertEqual(p.moves, ("protect",))
        self.assertEqual(p.ability, "noability")


class Coverage(unittest.TestCase):
    def test_numbers_on_a_small_table(self):
        moves = {("earthquake", "protect"): 0.5, ("earthquake", "powergem"): 0.5}
        ia = {(None, "intimidate", None): 0.5, (None, "roughskin", None): 0.5}
        c = S.coverage(moves, ia, {"moves": 0.1, "spreads": 0.2})
        self.assertAlmostEqual(c.strict_mass, 0.25)
        self.assertAlmostEqual(c.move_share, 0.75)
        self.assertAlmostEqual(c.ability_share, 0.5)
        self.assertAlmostEqual(c.moves_dropped, 0.5)
        self.assertEqual((c.tail_moves, c.tail_spreads, c.item_share), (0.1, 0.2, 0.0))

    def test_mega_sets_are_not_strictly_simulable(self):
        c = S.coverage({("earthquake",): 1.0}, {("garchompitez", "levitate", "garchomp-mega-z"): 1.0}, {})
        self.assertEqual(c.strict_mass, 0.0)
        self.assertEqual(c.ability_share, 1.0)


if __name__ == "__main__":
    unittest.main()
