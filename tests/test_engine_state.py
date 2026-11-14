import unittest

from champions import stats
from champions.engine import teams
from champions.engine.actions import Move, Switch, from_dict
from champions.engine.rng import ForcedRng, Rng
from champions.engine.state import STAGE_MAX, STAGE_MIN


def garchomp():
    return teams.build_mon({"species": "garchomp", "ability": "Rough Skin"})


class Build(unittest.TestCase):
    def test_stats_match_level50(self):
        m = garchomp()
        # same numbers tests/test_data.py pins: 183/150/115/100/105/122
        self.assertEqual([m.stats[k] for k in ("hp", "atk", "def", "spa", "spd", "spe")],
                         [183, 150, 115, 100, 105, 122])
        self.assertEqual(m.hp, m.max_hp)
        self.assertEqual(m.ability, "roughskin")

    def test_stat_points_and_nature(self):
        m = teams.build_mon({"species": "garchomp", "nature": "jolly", "sp": "0/0/0/0/0/32"})
        base = stats.level50(teams._species()["garchomp"]["stats"], "jolly", {"speed": 32})
        self.assertEqual(m.stats["spe"], base["speed"])

    def test_shorthand_and_default_ability(self):
        self.assertEqual(teams.build_mon("lucario:innerfocus").ability, "innerfocus")
        self.assertEqual(teams.build_mon("incineroar").ability, "blaze")

    def test_battle_has_leads(self):
        b = teams.build_battle([["incineroar", "rillaboom", "garchomp"], ["lucario"]], seed=1)
        self.assertEqual(b.sides[0].active, [0, 1])
        self.assertEqual(b.sides[1].active, [0, None])


class MonState(unittest.TestCase):
    def setUp(self):
        self.b = teams.build_battle([["garchomp"], ["lucario"]], seed=1)
        self.m = self.b.mon(0, 0)

    def test_boost_clamps(self):
        self.assertEqual(self.m.boost("atk", -1), -1)
        self.assertEqual(self.m.boost("atk", 20), STAGE_MAX - (-1))
        self.assertEqual(self.m.stages["atk"], STAGE_MAX)
        self.assertEqual(self.m.boost("atk", 1), 0)
        self.m.stages["def"] = STAGE_MIN
        self.assertEqual(self.m.boost("def", -1), 0)

    def test_take_floors_at_zero_and_logs_faint(self):
        dealt = self.m.take(10_000)
        self.assertEqual(dealt, self.m.max_hp)
        self.assertEqual(self.m.hp, 0)
        self.assertTrue(self.b.events("faint", mon="p1:garchomp"))

    def test_heal_capped(self):
        self.m.take(10)
        self.assertEqual(self.m.heal(500), 10)

    def test_clear_on_switch(self):
        self.m.boost("atk", 2)
        self.m.add_volatile("flinch")
        self.m.clear_on_switch()
        self.assertEqual(self.m.stages["atk"], 0)
        self.assertEqual(self.m.volatiles, {})


class RngAndActions(unittest.TestCase):
    def test_same_seed_same_draws(self):
        a, b = Rng(7), Rng(7)
        self.assertEqual([a.randint(0, 99) for _ in range(5)], [b.randint(0, 99) for _ in range(5)])

    def test_chance_100_consumes_nothing(self):
        r = Rng(7)
        state = r.getstate()
        self.assertTrue(r.chance(100))
        self.assertEqual(r.getstate(), state)

    def test_rng_state_roundtrip(self):
        a = Rng(3)
        a.randint(0, 9)
        b = Rng(0)
        b.setstate(a.getstate())
        self.assertEqual(a.randint(0, 99), b.randint(0, 99))

    def test_draws_are_logged(self):
        b = teams.build_battle([["garchomp"], ["lucario"]], seed=1)
        b.rng.randint(1, 6, "roll")
        self.assertEqual(len(b.events("rng")), 1)

    def test_forced_rng(self):
        r = ForcedRng([True, 3])
        self.assertTrue(r.chance(30))
        self.assertEqual(r.randint(1, 5), 3)
        with self.assertRaises(AssertionError):
            r.chance(30)

    def test_actions_roundtrip(self):
        for a in (Move(0, 1, "fakeout", (1, 0)), Move(0, 0, "protect", None, mega=True), Switch(1, 0, 2)):
            self.assertEqual(from_dict(a.to_dict()), a)


if __name__ == "__main__":
    unittest.main()
