import io
import json
import os
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest import mock

from champions.belief import Belief, load_priors
from champions.belief import support as S
from champions.belief.prior import build_prior
from champions.engine import game
from champions.solver import recommend as rec_mod
from champions.solver import solve
from champions.solver.actions import describe, joint_actions
from champions.solver.cli import main as cli_main
from champions.solver.recommend import recommend
from tests.test_belief_prior import GARCHOMP

B1 = {"damage_roll": 1}


def spec(species, moves, ability=None, **kw):
    return dict(species=species, moves=moves, ability=ability, **kw)


MINE = [spec("incineroar", ["flamethrower", "closecombat"], "blaze"), spec("garchomp", ["earthquake", "dragonclaw"], "sandveil")]
TEAM_A = [spec("gengar", ["shadowball", "icebeam"], "cursedbody")]
TEAM_B = [spec("dragonite", ["dragonclaw", "extremespeed"], "innerfocus")]


class Fake:
    """Stands in for a TeamBelief with a fixed list of possible opposing teams."""
    def __init__(self, teams, weights=None, leads=("x",)):
        self.teams, self.leads = teams, leads
        self.w = weights or [1.0 / len(teams)] * len(teams)

    def weighted_teams(self, n, rng, view="project", require_moves=False):
        return list(zip(self.teams, self.w))


class Recommend(unittest.TestCase):
    def test_a_known_opponent_reduces_to_the_ordinary_solve(self):
        r = recommend(MINE[:1], Fake([TEAM_A]), depth=1, format="singles", moves=None)
        b = game.start([MINE[:1], TEAM_A], seed=1, format="singles")
        s = solve(b, depth=1, buckets=B1)
        self.assertAlmostEqual(r.value, s.value, places=6)
        self.assertAlmostEqual(r.fused_value, r.value, places=6)
        self.assertAlmostEqual(r.value_of_information, 0.0, places=6)
        for a, c in zip(sorted(r.strategy), sorted(s.row_mix)):
            self.assertAlmostEqual(a, c, places=4)

    def test_invariants_with_several_possible_opponents(self):
        r = recommend(MINE[:1], Fake([TEAM_A, TEAM_B], [0.3, 0.7]), depth=1, format="singles", moves=None)
        self.assertAlmostEqual(sum(r.strategy), 1.0, places=9)
        self.assertAlmostEqual(sum(r.weights), 1.0, places=9)
        self.assertGreaterEqual(r.value, r.fused_value - 1e-9)             # never worse than naive averaging
        self.assertGreaterEqual(r.value_of_information, -1e-9)             # knowing the set cannot hurt
        for have, could in zip(r.sample_values, r.sample_best):
            self.assertLessEqual(have, could + 1e-9)
        self.assertAlmostEqual(sum(w * v for w, v in zip(r.weights, r.sample_values)), r.value, places=9)

    def test_value_is_recomputed_independently_from_each_game(self):
        """Replay the same games with plain solve() and check the reported numbers against them."""
        r = recommend(MINE[:1], Fake([TEAM_A, TEAM_B], [0.5, 0.5]), depth=1, format="singles", moves=None)
        games = [solve(game.start([MINE[:1], t], seed=1, format="singles"), depth=1, buckets=B1) for t in (TEAM_A, TEAM_B)]
        self.assertEqual(r.rows, games[0].rows)
        for k, g in enumerate(games):
            self.assertAlmostEqual(r.sample_best[k], g.value, places=6)
            have = min(sum(r.strategy[i] * g.matrix[i][j] for i in range(len(r.rows))) for j in range(len(g.cols)))
            self.assertAlmostEqual(r.sample_values[k], have, places=6)

    def test_games_share_the_same_rows_even_when_their_best_moves_differ(self):
        """Earthquake is Garchomp's best move against Gengar (not immune) and Dragon Claw against Dragonite (Flying
        makes Earthquake useless). Filtering to one move per game gives different candidates, so the games must be put
        on a common set of rows or the strategy mixes up which action is which."""
        garchomp = [spec("garchomp", ["earthquake", "dragonclaw"], "sandveil")]
        r = recommend(garchomp, Fake([TEAM_A, TEAM_B], [0.5, 0.5]), depth=1, format="singles", moves=1, status=0, switches=0)
        self.assertEqual(sorted(r.rows), ["dragonclaw", "earthquake"])
        rows = joint_actions(game.start([garchomp, TEAM_A], seed=1, format="singles"), 0)
        share = dict(zip(r.rows, r.strategy))
        for k, team in enumerate((TEAM_A, TEAM_B)):
            g = solve(game.start([garchomp, team], seed=1, format="singles"), depth=1, buckets=B1, moves=1, status=0,
                      switches=0, root_full=False, rows=rows)
            x = [share[label] for label in g.rows]                  # our strategy, in this game's row order
            have = min(sum(x[i] * g.matrix[i][j] for i in range(2)) for j in range(len(g.cols)))
            self.assertAlmostEqual(r.sample_values[k], have, places=6)
            self.assertAlmostEqual(r.sample_best[k], g.value, places=6)

    def test_identical_sampled_teams_merge(self):
        r = recommend(MINE[:1], Fake([TEAM_A, TEAM_A, TEAM_B]), depth=1, format="singles", moves=None)
        self.assertEqual(len(r.teams), 2)
        self.assertAlmostEqual(sorted(r.weights)[1], 2 / 3)

    def test_leads_are_required(self):
        with self.assertRaises(ValueError):
            recommend(MINE, Fake([TEAM_A], leads=()), format="singles")

    def test_inert_opponents_are_reported(self):
        r = recommend(MINE[:1], Fake([[spec("gengar", [], "cursedbody")]]), depth=1, format="singles", moves=None)
        self.assertAlmostEqual(r.inert_share, 1.0)
        self.assertTrue(any("no simulable move" in n for n in r.notes))
        self.assertAlmostEqual(r.value, r.sample_best[0])

    def test_two_turns_runs(self):
        r = recommend(MINE[:1], Fake([TEAM_A]), depth=2, format="singles", moves=1)
        self.assertAlmostEqual(sum(r.strategy), 1.0, places=6)

    def test_same_seed_same_answer(self):
        book = load_priors(now=datetime(2026, 11, 15, tzinfo=timezone.utc))
        from champions.belief import TeamBelief
        tb = TeamBelief.from_preview(["gengar", "dragonite", "gyarados", "salamence"], book, leads=["gengar", "dragonite"])
        a = recommend(MINE, tb, n_samples=3, seed=11)
        b = recommend(MINE, tb, n_samples=3, seed=11)
        self.assertEqual(a.strategy, b.strategy)
        self.assertEqual(a.value, b.value)

    def test_labels_use_base_species_names(self):
        b = game.start([MINE, [spec("garchomp-mega-z", ["earthquake"], "levitate"), spec("gengar", ["shadowball"], "cursedbody")]],
                       seed=1, format="doubles")
        combo = next(c for c in joint_actions(b, 0) if any(getattr(x, "target", None) == (1, 0) for x in c))
        self.assertIn("Garchomp-Mega-Z", describe(b, combo))
        self.assertNotIn("Mega", describe(b, combo, base_names=True))


class RootRows(unittest.TestCase):
    def test_solve_uses_given_rows(self):
        b = game.start([MINE[:1], TEAM_A], seed=1, format="singles")
        rows = joint_actions(b, 0)[:1]
        r = solve(b, depth=1, buckets=B1, rows=rows)
        self.assertEqual(len(r.rows), 1)
        self.assertEqual(len(r.matrix), 1)


class RequireMoves(unittest.TestCase):
    def test_inert_sets_are_counted_and_can_be_resampled(self):
        from champions.belief import reference as R
        unsupported = [m for m in sorted(R.learnsets()["garchomp"]) if not S.move_ok(m)][:5]
        self.assertEqual(len(unsupported), 5)
        e = dict(GARCHOMP, moves={**{m: 90 - 5 * i for i, m in enumerate(unsupported)}, "rockslide": 30})
        b = Belief.from_prior(build_prior("garchomp", e, "munchstats"))
        self.assertGreater(b.coverage().empty_mass, 0.1)          # many sets keep no supported move
        rng = random.Random(1)
        inert = sum(1 for _ in range(400) if not b.sample(rng, "project").moves) / 400
        self.assertAlmostEqual(inert, b.coverage().empty_mass, delta=0.08)
        rng = random.Random(1)
        self.assertEqual(sum(1 for _ in range(400) if not b.sample(rng, "project", require_moves=True).moves), 0)

    def test_resampling_gives_up_after_a_bounded_number_of_tries(self):
        e = dict(GARCHOMP, moves={"Power Gem": 90, "Earth Power": 80, "Draco Meteor": 70, "Fire Blast": 60, "Rock Slide": 0.01})
        b = Belief.from_prior(build_prior("garchomp", e, "munchstats"))
        rng = random.Random(1)
        h = b.sample(rng, "project", require_moves=True)        # must return (possibly empty), never loop forever
        self.assertIsNotNone(h)

    def test_empty_mass_in_coverage(self):
        c = S.coverage({("powergem",): 0.4, ("powergem", "protect"): 0.6}, {(None, "roughskin", None): 1.0}, {})
        self.assertAlmostEqual(c.empty_mass, 0.4)


class Cli(unittest.TestCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch("sys.stderr", io.StringIO()):
            cli_main(list(argv))
        return out.getvalue()

    def team_file(self, team):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump({"team": team}, f)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_end_to_end_output(self):
        path = self.team_file(MINE + [spec("venusaur", ["gigadrain", "sludgebomb"], "overgrow"), spec("rotom", ["surf", "thunderwave"], "levitate")])
        out = self.run_cli("--mine", path, "--opp", "gengar,dragonite,gyarados,salamence", "--leads", "gengar,dragonite",
                           "--samples", "3", "--seen", "gengar:move:Shadow Ball")
        for text in ("Recommended play", "mix over your joint actions", "against each sampled opponent",
                     "value of knowing the opponent's set", "candidate actions"):
            self.assertIn(text, out)
        self.assertIn("shadowball", out)                 # the revealed move is in every sampled Gengar

    def test_singles_format(self):
        path = self.team_file(MINE[:1] + [spec("venusaur", ["gigadrain"], "overgrow")])
        out = self.run_cli("--mine", path, "--opp", "gengar,dragonite,gyarados", "--leads", "gengar", "--format", "singles", "--samples", "2")
        self.assertIn("Recommended play", out)

    def test_errors_are_clear(self):
        path = self.team_file(MINE)
        base = ["--mine", path, "--opp", "gengar,dragonite,gyarados,salamence", "--leads", "gengar,dragonite"]
        for bad, text in ((["--leads", "gengar"], "needs 2"), (["--seen", "gengar-shadowball"], "--seen wants"),
                          (["--seen", "pikachu:move:Surf"], "not on this team"),
                          (["--seen", "notapokemon:move:Surf"], "unknown species"),
                          (["--mine", "/no/such/file.json"], "cannot read")):
            args = base + bad
            with self.assertRaises(SystemExit) as e:
                self.run_cli(*args)
            self.assertIn(text, str(e.exception))

    def test_registered(self):
        from champions.cli import COMMANDS
        self.assertEqual(COMMANDS["recommend"][0], "champions.solver.cli")


if __name__ == "__main__":
    unittest.main()
