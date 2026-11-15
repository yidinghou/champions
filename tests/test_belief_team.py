import io
import random
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest import mock

from champions.belief import MoveSeen, TeamBelief, load_priors
from champions.belief import cli as belief_cli
from champions.belief.reference import species_table
from champions.engine import game

SIX = ["garchomp", "incineroar", "gholdengo", "rillaboom", "sneasler", "salamence"]


def base(spec):
    """Base species of an engine spec (a held Mega Stone makes the spec its Mega form)."""
    return species_table()[spec["species"]]["species"]


MINE = [{"species": "incineroar", "ability": "intimidate", "moves": ["flamethrower", "closecombat"]},
        {"species": "garchomp", "ability": "sandveil", "moves": ["earthquake", "dragonclaw"]}]


class Team(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = load_priors(now=datetime(2026, 11, 15, tzinfo=timezone.utc))

    def tb(self, **kw):
        return TeamBelief.from_preview(SIX, self.book, **kw)

    def test_uniform_over_fifteen_subsets(self):
        tb = self.tb()
        self.assertEqual(len(tb.subsets), 15)
        self.assertAlmostEqual(sum(tb.subsets.values()), 1.0)
        for s in SIX:
            self.assertAlmostEqual(tb.p_brought(s), 4 / 6)

    def test_appeared_species_were_brought(self):
        tb = self.tb().appeared("garchomp")
        self.assertAlmostEqual(tb.p_brought("garchomp"), 1.0)
        self.assertAlmostEqual(tb.p_brought("sneasler"), 3 / 5)       # 3 more slots over the other 5
        tb = tb.appeared("incineroar", "gholdengo", "rillaboom")
        self.assertEqual(len(tb.subsets), 1)
        self.assertAlmostEqual(tb.p_brought("sneasler"), 0.0)

    def test_too_many_appearances(self):
        with self.assertRaises(ValueError):
            self.tb().appeared(*SIX[:5])

    def test_leads_count_as_appeared(self):
        tb = self.tb(leads=["garchomp", "incineroar"])
        self.assertAlmostEqual(tb.p_brought("incineroar"), 1.0)
        self.assertEqual(tb.leads, ("garchomp", "incineroar"))

    def test_leads_may_be_given_as_display_names(self):
        tb = TeamBelief.from_preview(["Garchomp", "Incineroar", "Gholdengo", "Rillaboom"], self.book, leads=["Garchomp", "Incineroar"])
        self.assertEqual(tb.leads, ("garchomp", "incineroar"))
        self.assertEqual([base(t) for t in tb.sample_team(random.Random(1))[:2]], ["garchomp", "incineroar"])
        with self.assertRaises(ValueError):
            TeamBelief.from_preview(SIX, self.book, leads=["Pikachu"])

    def test_condition_marks_appeared_and_narrows_the_set(self):
        tb = self.tb().condition("rillaboom", MoveSeen("Fake Out"))
        self.assertAlmostEqual(tb.p_brought("rillaboom"), 1.0)
        self.assertAlmostEqual(tb.beliefs["rillaboom"].marginals()["moves"]["fakeout"], 1.0)
        self.assertAlmostEqual(self.tb().beliefs["rillaboom"].marginals()["moves"]["fakeout"] < 1.0, True)  # original intact

    def test_input_validation(self):
        with self.assertRaises(ValueError) as e:
            TeamBelief.from_preview(["garchomq"] + SIX[1:], self.book)
        self.assertIn("garchomp", str(e.exception))
        with self.assertRaises(ValueError):
            TeamBelief.from_preview(["garchomp", "garchomp", "incineroar", "rillaboom"], self.book)
        with self.assertRaises(ValueError):
            TeamBelief.from_preview(SIX[:3], self.book)
        with self.assertRaises(ValueError):
            self.tb().appeared("pikachu")

    def test_affinity_tilts_the_subsets(self):
        tb = TeamBelief.from_preview(SIX, self.book, affinity={("garchomp", "incineroar"): 1.0}, beta=2.0)
        self.assertGreater(tb.p_brought("garchomp"), 4 / 6)
        self.assertAlmostEqual(sum(tb.subsets.values()), 1.0)

    def test_sample_team_shape_and_leads_first(self):
        tb = self.tb(leads=["sneasler", "salamence"])
        rng = random.Random(5)
        for _ in range(30):
            team = tb.sample_team(rng)
            self.assertEqual(len(team), 4)
            self.assertEqual([base(t) for t in team[:2]], ["sneasler", "salamence"])
            self.assertEqual(len({base(t) for t in team}), 4)

    def test_sampled_teams_start_a_game(self):
        tb = self.tb(leads=["garchomp", "incineroar"])
        for team, w in tb.weighted_teams(8, random.Random(2)):
            b = game.start([MINE, team], seed=1, format="doubles")
            self.assertEqual({species_table()[m.species]["species"] for _, m in b.sides[1].alive_active()},
                             {"garchomp", "incineroar"})
            self.assertAlmostEqual(w, 1 / 8)

    def test_sampling_follows_the_subset_posterior(self):
        tb = self.tb().appeared("garchomp", "incineroar", "gholdengo")
        rng = random.Random(4)
        picks = [base(t) for _ in range(400) for t in tb.sample_team(rng)]
        self.assertEqual(picks.count("garchomp"), 400)
        self.assertEqual(sum(picks.count(s) for s in ("rillaboom", "sneasler", "salamence")), 400)

    def test_strict_view_may_have_no_simulable_team(self):
        with self.assertRaises(RuntimeError):
            self.tb().sample_team(random.Random(0), view="strict")


class Cli(unittest.TestCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch("sys.stderr", io.StringIO()):
            belief_cli.main(list(argv))
        return out.getvalue()

    def test_shows_sets_marginals_and_coverage(self):
        out = self.run_cli("garchomp", "--top", "3")
        for text in ("garchomp", "top 3 sets", "marginals:", "engine coverage", "data as of"):
            self.assertIn(text, out)

    def test_seen_flags_narrow_the_belief(self):
        out = self.run_cli("garchomp", "--seen-move", "Earthquake", "--seen-item", "Life Orb")
        self.assertIn("seen: move Earthquake, item Life Orb", out)
        self.assertIn("earthquake 100%", out)

    def test_impossible_is_reported(self):
        self.assertIn("IMPOSSIBLE", self.run_cli("garchomp", "--seen-ability", "Intimidate"))

    def test_unknown_species_suggests(self):
        with self.assertRaises(SystemExit) as e:
            self.run_cli("garchomq")
        self.assertIn("garchomp", str(e.exception))

    def test_views(self):
        for v in ("raw", "project", "strict"):
            self.assertIn(f"{v} view", self.run_cli("garchomp", "--view", v))

    def test_registered_in_umbrella_cli(self):
        from champions.cli import COMMANDS
        self.assertEqual(COMMANDS["belief"][0], "champions.belief.cli")


if __name__ == "__main__":
    unittest.main()
