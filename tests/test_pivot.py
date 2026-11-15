"""Unit tests for pivot moves and forced switches: choices, enumeration and edge cases."""
import unittest

from champions.engine import game, replay
from champions.engine.actions import Move, from_dict
from champions.engine.resolve import resolve
from champions.engine.rng import LabeledRng


def spec(species, ability, moves, **kw):
    return {"species": species, "ability": ability, "moves": moves, **kw}


def start(p1, p2, fmt="singles"):
    return game.start([p1, p2], seed=1, format=fmt, rng=LabeledRng())


BENCH = [spec("garchomp", "sandveil", ["protect"]), spec("mawile", "noability", ["protect"])]


class Choices(unittest.TestCase):
    def test_pivot_to_round_trips_through_a_replay_dict(self):
        m = Move(0, 0, "uturn", (1, 0), pivot_to=2)
        self.assertEqual(from_dict(m.to_dict()), m)
        self.assertNotIn("pivot_to", Move(0, 0, "uturn", (1, 0)).to_dict())

    def test_legal_choices_name_each_replacement_for_a_pivot_move(self):
        b = start([spec("clefable", "unaware", ["uturn", "bodyslam"])] + BENCH, [spec("snorlax", "thickfat", ["protect"])])
        moves = [c for c in game.legal_choices(b, 0) if isinstance(c, Move)]
        self.assertEqual(sorted(c.pivot_to for c in moves if c.move == "uturn"), [1, 2])
        self.assertEqual([c.pivot_to for c in moves if c.move == "bodyslam"], [None])

    def test_a_single_bench_mon_needs_no_choice(self):
        b = start([spec("clefable", "unaware", ["uturn"]), BENCH[0]], [spec("snorlax", "thickfat", ["protect"])])
        self.assertEqual([c.pivot_to for c in game.legal_choices(b, 0) if isinstance(c, Move)], [None])

    def test_illegal_pivot_targets_are_refused(self):
        b = start([spec("clefable", "unaware", ["uturn"]), spec("garchomp", "sandveil", ["protect"], hp=0)],
                  [spec("snorlax", "thickfat", ["protect"])])
        for bad in (0, 1, 5, -1):
            with self.assertRaises(ValueError, msg=bad):
                game.play_turn(b, [Move(0, 0, "uturn", (1, 0), pivot_to=bad)])

    def test_replay_with_a_pivot_is_deterministic(self):
        teams = [[spec("clefable", "unaware", ["uturn"])] + BENCH, [spec("snorlax", "thickfat", ["protect"])]]
        r = replay.make_replay(teams, 3, [[Move(0, 0, "uturn", (1, 0), pivot_to=2)]], "singles")
        a, b = replay.log_to_list(replay.play_replay(r)), replay.log_to_list(replay.play_replay(r))
        self.assertEqual(a, b)
        self.assertIn("p1:mawile", [e["data"].get("mon") for e in a if e["kind"] == "switch"])


class Forced(unittest.TestCase):
    def test_resolve_branches_over_the_random_replacement(self):
        b = start([spec("clefable", "unaware", ["dragontail"])],
                  [spec("snorlax", "thickfat", ["protect"]), spec("garchomp", "sandveil", ["protect"]), spec("mawile", "noability", ["protect"])])
        out = resolve(b, [Move(0, 0, "dragontail", (1, 0))])
        came_in = {c.sides[1].team[c.sides[1].active[0]].species for _, c in out}
        self.assertEqual(came_in - {"snorlax"}, {"garchomp", "mawile"})        # snorlax: the 90% accurate move missed
        self.assertAlmostEqual(sum(p for p, _ in out), 1.0)

    def test_the_forced_mons_queued_move_lapses(self):
        """Doubles: both use Roar (-6); the faster Clefable drags Snorlax out before it acts, and the replacement
        does not use Snorlax's choice."""
        teams = [[spec("clefable", "unaware", ["roar"]), spec("mawile", "noability", ["protect"])],
                 [spec("snorlax", "thickfat", ["roar"]), spec("garchomp", "sandveil", ["protect"]), spec("pikachu", "noability", ["protect"])]]
        b = game.start(teams, seed=1, format="doubles", rng=LabeledRng())
        game.play_turn(b, [Move(0, 0, "roar", (1, 0)), Move(1, 0, "roar", (0, 0))])
        self.assertEqual(b.events("move", mon="p2:snorlax"), [])
        self.assertEqual(b.events("move", mon="p2:pikachu"), [])

    def test_baton_pass_goes_through_hooks_in_order(self):
        b = start([spec("clefable", "unaware", ["batonpass"]), spec("arcanine", "intimidate", ["protect"])],
                  [spec("snorlax", "thickfat", ["protect"])])
        b.sides[0].team[0].stages["atk"] = 2
        game.play_turn(b, [Move(0, 0, "batonpass", None)])
        self.assertEqual(b.sides[0].team[1].stages["atk"], 2)
        self.assertEqual(b.sides[1].team[0].stages["atk"], -1)


if __name__ == "__main__":
    unittest.main()
