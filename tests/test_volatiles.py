"""Unit tests for volatile status: the numbers and edge rules the catalogue cases only pin indirectly."""
import unittest

from champions.calc.damage import damage
from champions.engine import game, volatiles
from champions.engine.rng import LabeledRng
from champions.engine.teams import build_mon, moves_data


def mon(species, ability, moves, **kw):
    return build_mon({"species": species, "ability": ability, "moves": moves, **kw})


def battle(a, b, rolls=None, fmt="singles"):
    return game.start([a, b], seed=1, format=fmt, rng=LabeledRng(rolls or {}))


class Confusion(unittest.TestCase):
    def test_self_hit_is_typeless_40_power_with_own_stats(self):
        m = mon("snorlax", "thickfat", [])
        d = damage(m, m, volatiles.SELF_HIT, crit=False, roll=100)
        a, de = m.stats["atk"], m.stats["def"]
        self.assertEqual(d, (2 * 50 // 5 + 2) * 40 * a // de // 50 + 2)      # no STAB (Normal), no type chart

    def test_self_hit_gets_no_stab(self):
        m = mon("snorlax", "thickfat", [])          # a Normal type: a Normal move would get STAB
        normal = dict(volatiles.SELF_HIT, type="Normal")
        self.assertGreater(damage(m, m, normal, roll=100), damage(m, m, volatiles.SELF_HIT, roll=100))

    def test_confusion_ends_and_the_mon_acts(self):
        b = battle([{"species": "snorlax", "ability": "thickfat", "moves": ["bodyslam"], "volatiles": {"confusion": 1}}],
                   [{"species": "clefable", "ability": "unaware", "moves": ["protect"]}], {"confusion_hit": [True]})
        game.play_turn(b, [game.Move(0, 0, "bodyslam", (1, 0))])
        self.assertNotIn("confusion", b.mon(0, 0).volatiles)       # the timer hit 0, so no self-hit roll
        self.assertEqual(len(b.events("move", mon="p1:snorlax")), 1)

    def test_sleeping_mon_does_not_tick_confusion(self):
        b = battle([{"species": "snorlax", "ability": "thickfat", "moves": ["bodyslam"], "status": "slp",
                     "status_turns": 3, "volatiles": {"confusion": 3}}],
                   [{"species": "clefable", "ability": "unaware", "moves": ["protect"]}])
        game.play_turn(b, [game.Move(0, 0, "bodyslam", (1, 0))])
        self.assertEqual(b.mon(0, 0).volatiles["confusion"], 3)


class Timers(unittest.TestCase):
    def test_taunt_expires_after_three_turn_ends(self):
        b = battle([{"species": "snorlax", "ability": "thickfat", "moves": ["protect"], "volatiles": {"taunt": 3}}],
                   [{"species": "clefable", "ability": "unaware", "moves": ["protect"]}])
        for _ in range(2):
            game.play_turn(b, [game.Move(0, 0, "protect", None)])
            self.assertIn("taunt", b.mon(0, 0).volatiles)
            b.mon(0, 0).volatiles.pop("protect_chain", None)
        game.play_turn(b, [game.Move(0, 0, "protect", None)])
        self.assertNotIn("taunt", b.mon(0, 0).volatiles)

    def test_encore_and_disable_lengths(self):
        self.assertEqual((volatiles.ENCORE_TURNS, volatiles.DISABLE_TURNS, volatiles.TAUNT_TURNS), (3, 4, 3))


class Choices(unittest.TestCase):
    def setUp(self):
        self.m = mon("snorlax", "thickfat", ["bodyslam", "yawn", "protect"])
        self.mv = moves_data()

    def test_taunt_removes_status_moves(self):
        self.m.volatiles["taunt"] = 2
        self.assertEqual([x for x in self.m.moves if volatiles.can_choose(self.m, x, self.mv[x])], ["bodyslam"])

    def test_disable_removes_only_that_move(self):
        self.m.volatiles["disable"] = {"move": "bodyslam", "turns": 2}
        self.assertEqual([x for x in self.m.moves if volatiles.can_choose(self.m, x, self.mv[x])], ["yawn", "protect"])

    def test_encore_leaves_only_the_locked_move(self):
        self.m.volatiles["encore"] = {"move": "yawn", "turns": 2}
        self.assertEqual([x for x in self.m.moves if volatiles.can_choose(self.m, x, self.mv[x])], ["yawn"])
        self.assertEqual(volatiles.forced_move(self.m, "bodyslam"), "yawn")


class Trapping(unittest.TestCase):
    def test_trap_ends_when_the_trapper_leaves(self):
        b = battle([{"species": "dragonite", "ability": "innerfocus", "moves": ["firespin"]},
                    {"species": "lucario", "ability": "innerfocus", "moves": ["bodyslam"]}],
                   [{"species": "snorlax", "ability": "thickfat", "moves": ["protect"]}], {"trap_turns": [5]})
        game.play_turn(b, [game.Move(0, 0, "firespin", (1, 0))])
        self.assertIn("trapped", b.mon(1, 0).volatiles)
        game.play_turn(b, [game.Switch(0, 0, 1)])
        self.assertNotIn("trapped", b.mon(1, 0).volatiles)

    def test_trap_expires_after_its_turns(self):
        b = battle([{"species": "dragonite", "ability": "innerfocus", "moves": ["firespin", "protect"]}],
                   [{"species": "snorlax", "ability": "thickfat", "moves": ["protect"]}], {"trap_turns": [4]})
        game.play_turn(b, [game.Move(0, 0, "firespin", (1, 0))])
        for _ in range(3):
            self.assertIn("trapped", b.mon(1, 0).volatiles)
            game.play_turn(b, [])
        self.assertNotIn("trapped", b.mon(1, 0).volatiles)

    def test_ghost_can_switch_a_trapped_ghost_is_not_trapped(self):
        g = mon("gengar", "cursedbody", [])
        g.volatiles["trapped"] = {"by": "p1:x", "turns": None, "dmg": False}
        self.assertFalse(volatiles.is_trapped(g))


class LeechSeed(unittest.TestCase):
    def test_heals_whoever_is_in_the_seeders_slot(self):
        b = battle([{"species": "venusaur", "ability": "overgrow", "moves": ["leechseed"]},
                    {"species": "lucario", "ability": "innerfocus", "moves": ["bodyslam"], "hp": 50}],
                   [{"species": "snorlax", "ability": "thickfat", "moves": ["protect"]}])
        game.play_turn(b, [game.Move(0, 0, "leechseed", (1, 0))])
        game.play_turn(b, [game.Switch(0, 0, 1)])
        self.assertGreater(b.mon(0, 0).hp, 50)                     # Lucario got the drain


class Refusals(unittest.TestCase):
    def test_a_refused_turn_changes_nothing(self):
        b = battle([{"species": "snorlax", "ability": "thickfat", "moves": ["protect"],
                     "volatiles": {"trapped": {"by": "p2:clefable", "turns": 3, "dmg": True}}},
                    {"species": "lucario", "ability": "innerfocus", "moves": ["bodyslam"]}],
                   [{"species": "clefable", "ability": "unaware", "moves": ["protect"]}])
        n, before = b.turn, len(b.log)
        with self.assertRaises(ValueError):
            game.play_turn(b, [game.Switch(0, 0, 1)])
        self.assertEqual((b.turn, len(b.log)), (n, before))


if __name__ == "__main__":
    unittest.main()
