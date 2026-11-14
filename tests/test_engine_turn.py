import unittest

from champions.engine import effects_table, game, teams
from champions.engine.actions import Move
from champions.engine.errors import Unsupported
from champions.engine.rng import ForcedRng
from champions.engine.turn import order_actions


def spec(species, moves, ability=None, **kw):
    return dict(species=species, moves=moves, ability=ability, **kw)


def fake_out_battle(seed=1, rng=None):
    return game.start([[spec("incineroar", ["fakeout"], "blaze")],
                       [spec("garchomp", ["dragonclaw"], "sandveil")]],
                      seed=seed, format="singles", rng=rng)


class EffectTable(unittest.TestCase):
    def test_every_modeled_move_exists_in_data(self):
        for mv in effects_table.MOVES:
            self.assertIn(mv, teams.moves_data(), mv)


class Ordering(unittest.TestCase):
    def test_priority_beats_speed(self):
        b = fake_out_battle()
        acts = order_actions(b, [Move(1, 0, "dragonclaw", (0, 0)), Move(0, 0, "fakeout", (1, 0))])
        self.assertEqual([a.choice.move for a in acts], ["fakeout", "dragonclaw"])

    def test_speed_orders_equal_priority(self):
        b = game.start([[spec("incineroar", ["dragonclaw"], "blaze")],
                        [spec("garchomp", ["dragonclaw"], "sandveil")]], format="singles")
        acts = order_actions(b, [Move(0, 0, "dragonclaw", (1, 0)), Move(1, 0, "dragonclaw", (0, 0))])
        self.assertEqual([a.choice.side for a in acts], [1, 0])   # Garchomp is faster

    def test_trick_room_reverses_speed_not_priority(self):
        b = game.start([[spec("incineroar", ["dragonclaw", "fakeout"], "blaze")],
                        [spec("garchomp", ["dragonclaw"], "sandveil")]], format="singles")
        b.arena["trick_room"] = 4
        acts = order_actions(b, [Move(0, 0, "dragonclaw", (1, 0)), Move(1, 0, "dragonclaw", (0, 0))])
        self.assertEqual([a.choice.side for a in acts], [0, 1])
        acts = order_actions(b, [Move(0, 0, "fakeout", (1, 0)), Move(1, 0, "dragonclaw", (0, 0))])
        self.assertEqual(acts[0].choice.move, "fakeout")

    def test_speed_tie_is_seeded(self):
        def first(seed):
            b = game.start([[spec("garchomp", ["dragonclaw"], "sandveil")],
                            [spec("garchomp", ["dragonclaw"], "sandveil")]], seed=seed, format="singles")
            return order_actions(b, [Move(0, 0, "dragonclaw", (1, 0)),
                                     Move(1, 0, "dragonclaw", (0, 0))])[0].choice.side
        self.assertEqual(first(5), first(5))


class FakeOutTurn(unittest.TestCase):
    def play(self):
        b = fake_out_battle()
        game.play_turn(b, [Move(0, 0, "fakeout", (1, 0)), Move(1, 0, "dragonclaw", (0, 0))])
        return b

    def test_fake_out_flinches_the_faster_mon(self):
        b = self.play()
        kinds = [e.kind for e in b.log if e.kind in ("move", "damage", "volatile", "fail")]
        self.assertEqual(kinds, ["move", "damage", "volatile", "fail"])
        fail = b.events("fail")[0]
        self.assertEqual((fail.data["mon"], fail.data["move"], fail.data["reason"]),
                         ("p2:garchomp", "dragonclaw", "flinch"))
        self.assertEqual(b.mon(0, 0).hp, b.mon(0, 0).max_hp)       # Garchomp never attacked
        self.assertLess(b.mon(1, 0).hp, b.mon(1, 0).max_hp)

    def test_flinch_clears_at_end_of_turn(self):
        b = self.play()
        self.assertNotIn("flinch", b.mon(1, 0).volatiles)

    def test_fake_out_fails_on_turn_two(self):
        b = self.play()
        game.play_turn(b, [Move(0, 0, "fakeout", (1, 0)), Move(1, 0, "dragonclaw", (0, 0))])
        reasons = [e.data["reason"] for e in b.events("fail")]
        self.assertIn("first_turn_only", reasons)


class Pipeline(unittest.TestCase):
    def test_immune_target_takes_nothing(self):
        b = game.start([[spec("lucario", ["closecombat"], "innerfocus")],
                        [spec("gengar", ["dragonclaw"], "goodasgold" )]], format="singles")
        game.play_turn(b, [Move(0, 0, "closecombat", (1, 0)), Move(1, 0, "dragonclaw", (0, 0))])
        self.assertEqual(len(b.events("immune")), 1)
        self.assertEqual(b.mon(1, 0).hp, b.mon(1, 0).max_hp)

    def test_protect_blocks_before_accuracy(self):
        b = game.start([[spec("garchomp", ["headsmash"], "sandveil")],
                        [spec("incineroar", ["protect"], "blaze")]], format="singles")
        game.play_turn(b, [Move(0, 0, "headsmash", (1, 0)), Move(1, 0, "protect")])
        self.assertEqual(len(b.events("protected")), 1)
        self.assertEqual(b.events("missed"), [])
        self.assertEqual(b.mon(1, 0).hp, b.mon(1, 0).max_hp)

    def test_miss_stops_the_move(self):
        b = game.start([[spec("garchomp", ["headsmash"], "sandveil")],
                        [spec("incineroar", ["dragonclaw"], "blaze")]], format="singles",
                       rng=ForcedRng([False]))
        game.play_turn(b, [Move(0, 0, "headsmash", (1, 0))])
        self.assertEqual(len(b.events("missed", mon="p2:incineroar", move="headsmash")), 1)
        self.assertEqual(b.events("damage"), [])


class Gate(unittest.TestCase):
    def test_unsupported_move_raises(self):
        with self.assertRaises(Unsupported):
            game.start([[spec("garchomp", ["splash"], "sandveil")], ["incineroar"]], format="singles")

    def test_unsupported_ability_raises(self):
        with self.assertRaises(Unsupported):
            game.start([[spec("garchomp", ["dragonclaw"], "roughskin")],
                        [spec("incineroar", ["fakeout"], "blaze")]], format="singles")

    def test_run_to_end_finishes(self):
        def policy(b):
            return [game.legal_choices(b, s)[0] for s in (0, 1)]
        b = game.run_to_end([[spec("garchomp", ["dragonclaw"], "sandveil")],
                             [spec("incineroar", ["dragonclaw"], "blaze")]], 3, policy, format="singles")
        self.assertIsNotNone(b.winner)


if __name__ == "__main__":
    unittest.main()
