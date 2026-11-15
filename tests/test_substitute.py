"""Unit tests for Substitute and Shed Tail: HP arithmetic, state handling and the cases the catalogue cannot count."""
import unittest

from champions.engine import game
from champions.engine.actions import Move
from champions.engine.resolve import state_key
from champions.engine.rng import LabeledRng


def spec(species, ability, moves, **kw):
    return {"species": species, "ability": ability, "moves": moves, **kw}


def start(p1, p2):
    return game.start([p1, p2], seed=1, format="singles", rng=LabeledRng())


class Arithmetic(unittest.TestCase):
    def test_cost_and_decoy_hp_are_a_quarter_floored(self):
        b = start([spec("clefable", "unaware", ["substitute"])], [spec("snorlax", "thickfat", ["protect"])])
        m = b.sides[0].team[0]
        full = m.hp
        game.play_turn(b, [Move(0, 0, "substitute", None)])
        self.assertEqual(full - m.hp, full // 4)
        self.assertEqual(m.volatiles["substitute"]["hp"], full // 4)

    def test_the_decoy_takes_exactly_its_hp_and_no_overflow(self):
        b = start([spec("clefable", "unaware", ["bodyslam"])], [spec("snorlax", "thickfat", ["protect"], volatiles={"substitute": {"hp": 3}})])
        game.play_turn(b, [Move(0, 0, "bodyslam", (1, 0))])
        ev = b.events("substitute")[0].data
        self.assertEqual((ev["amount"], ev["broke"]), (3, True))
        self.assertEqual(b.sides[1].team[0].hp, b.sides[1].team[0].max_hp)

    def test_damage_to_the_decoy_equals_what_the_mon_would_have_taken(self):
        def hit(volatiles):
            b = start([spec("clefable", "unaware", ["bodyslam"])], [spec("snorlax", "thickfat", ["protect"], volatiles=volatiles)])
            game.play_turn(b, [Move(0, 0, "bodyslam", (1, 0))])
            return b
        plain = hit({})
        behind = hit({"substitute": {"hp": 1000}})
        taken = plain.events("damage", mon="p2:snorlax")[0].data["amount"]
        self.assertEqual(behind.events("substitute")[0].data["amount"], taken)

    def test_dealt_total_counts_the_decoy(self):
        from champions.engine.pipeline import MoveContext
        ctx = MoveContext(None, None, "x", {}, {})
        ctx.damage, ctx.sub_damage = {"a": 5}, {"b": 7}
        self.assertEqual(ctx.dealt_total(), 12)


class State(unittest.TestCase):
    def test_state_key_and_clone_see_the_decoys_hp(self):
        b = start([spec("clefable", "unaware", ["bodyslam"])], [spec("snorlax", "thickfat", ["protect"], volatiles={"substitute": {"hp": 100}})])
        c = b.clone()
        game.play_turn(c, [Move(0, 0, "bodyslam", (1, 0))])
        self.assertEqual(b.sides[1].team[0].volatiles["substitute"]["hp"], 100)
        self.assertNotEqual(state_key(b), state_key(c))

    def test_baton_pass_copies_the_decoy_instead_of_sharing_it(self):
        b = start([spec("snorlax", "thickfat", ["batonpass"], volatiles={"substitute": {"hp": 40}}), spec("garchomp", "sandveil", ["protect"])],
                  [spec("clefable", "unaware", ["protect"])])
        game.play_turn(b, [Move(0, 0, "batonpass", None)])
        new = b.sides[0].team[1]
        self.assertEqual(new.volatiles["substitute"], {"hp": 40})
        self.assertIsNot(new.volatiles["substitute"], b.sides[0].team[0].volatiles.get("substitute"))

    def test_the_decoy_is_cleared_on_faint(self):
        b = start([spec("snorlax", "thickfat", ["protect"], volatiles={"substitute": {"hp": 40}}, hp=1, status="brn")],
                  [spec("clefable", "unaware", ["protect"])])
        game.play_turn(b, [Move(1, 0, "protect", None)])
        self.assertNotIn("substitute", b.sides[0].team[0].volatiles)


if __name__ == "__main__":
    unittest.main()
