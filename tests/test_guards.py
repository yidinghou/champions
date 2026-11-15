"""Unit tests for the guard moves: the stalling rule, turn bookkeeping and state."""
import unittest

from champions.engine import game
from champions.engine.actions import Move
from champions.engine.resolve import resolve
from champions.engine.rng import LabeledRng


def spec(species, ability, moves, **kw):
    return {"species": species, "ability": ability, "moves": moves, **kw}


def start(p1, p2, fmt="singles", rolls=None):
    return game.start([p1, p2], seed=1, format=fmt, rng=LabeledRng(rolls))


class Stalling(unittest.TestCase):
    def test_pending_is_cleared_when_the_turn_ends(self):
        b = start([spec("clefable", "unaware", ["bodyslam"])], [spec("snorlax", "thickfat", ["protect"])])
        game.play_turn(b, [Move(0, 0, "bodyslam", (1, 0)), Move(1, 0, "protect", None)])
        self.assertNotIn("pending", b.arena)

    def test_pending_counts_the_actions_still_to_come(self):
        seen = []
        from champions.engine import handlers  # noqa: F401
        from champions.engine.hooks import on

        @on("on_hit", "effect:protect")
        def spy(battle, ctx):
            seen.append(battle.arena["pending"])
        b = start([spec("clefable", "unaware", ["bodyslam"])], [spec("snorlax", "thickfat", ["protect"])])
        game.play_turn(b, [Move(0, 0, "bodyslam", (1, 0)), Move(1, 0, "protect", None)])
        self.assertEqual(seen, [1])                     # Protect goes first; Body Slam is still to come

    def test_a_guard_failing_as_last_mover_does_not_roll(self):
        b = start([spec("clefable", "unaware", ["protect"])], [spec("snorlax", "thickfat", ["protect"])])
        game.play_turn(b, [Move(1, 0, "protect", None)])
        self.assertEqual(b.events("rng", label="protect"), [])
        self.assertEqual(b.events("fail", reason="last_to_move")[0].data["mon"], "p2:snorlax")

    def test_resolve_branches_over_the_stall_roll_not_the_last_mover_failure(self):
        b = start([spec("clefable", "unaware", ["bodyslam"])], [spec("snorlax", "thickfat", ["protect"])])
        b.sides[1].team[0].volatiles["protect_chain"] = 1
        out = resolve(b, [Move(0, 0, "bodyslam", (1, 0)), Move(1, 0, "protect", None)])
        survived = sorted(round(p, 3) for p, c in out if c.sides[1].team[0].hp == c.sides[1].team[0].max_hp)
        self.assertEqual(survived, [0.333])


class Contact(unittest.TestCase):
    def test_spiky_shield_can_knock_out_a_weak_attacker(self):
        b = start([spec("clefable", "unaware", ["bodyslam"], hp=3)], [spec("snorlax", "thickfat", ["spikyshield"])])
        game.play_turn(b, [Move(0, 0, "bodyslam", (1, 0)), Move(1, 0, "spikyshield", None)])
        self.assertTrue(b.sides[0].team[0].fainted)

    def test_the_shield_kind_is_the_volatile_value(self):
        b = start([spec("clefable", "unaware", ["protect"])], [spec("snorlax", "thickfat", ["kingsshield", "bodyslam"])])
        game.play_turn(b, [Move(0, 0, "protect", None), Move(1, 0, "kingsshield", None)])
        self.assertEqual(b.sides[1].team[0].volatiles.get("protect"), None)      # cleared at end of turn

    def test_endure_and_protect_clear_at_the_end_of_the_turn(self):
        b = start([spec("clefable", "unaware", ["bodyslam"])], [spec("snorlax", "thickfat", ["endure", "bodyslam"])])
        game.play_turn(b, [Move(0, 0, "bodyslam", (1, 0)), Move(1, 0, "endure", None)])
        self.assertNotIn("endure", b.sides[1].team[0].volatiles)


class Safeguard(unittest.TestCase):
    def test_state_key_and_clone_see_the_side_condition(self):
        from champions.engine.resolve import state_key
        a = start([spec("clefable", "unaware", ["protect"])], [spec("snorlax", "thickfat", ["safeguard"])])
        b = a.clone()
        b.sides[1].conditions["safeguard"] = 3
        self.assertNotEqual(state_key(a), state_key(b))
        self.assertNotIn("safeguard", a.sides[1].conditions)

    def test_a_yawn_already_applied_still_puts_the_mon_to_sleep(self):
        b = start([spec("clefable", "unaware", ["protect"])], [spec("snorlax", "thickfat", ["protect"], volatiles={"yawn": 1})])
        b.sides[1].conditions["safeguard"] = 3
        game.play_turn(b, [Move(0, 0, "protect", None), Move(1, 0, "protect", None)])
        self.assertEqual(b.sides[1].team[0].status, "slp")


if __name__ == "__main__":
    unittest.main()
