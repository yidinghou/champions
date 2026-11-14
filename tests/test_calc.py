import unittest

from champions.calc import damage as dmg
from champions.calc import typechart
from champions.engine import teams


def mons():
    a = teams.build_mon({"species": "garchomp", "ability": "sandveil"})
    d = teams.build_mon({"species": "incineroar", "ability": "blaze"})
    d.stats["def"] = 100
    return a, d


class TypeChart(unittest.TestCase):
    def test_fighting_into_ghost_is_zero(self):
        self.assertEqual(typechart.effectiveness("Fighting", ["ghost"]), 0)
        self.assertTrue(typechart.is_immune("Fighting", ["ghost", "poison"]))

    def test_scrappy_override(self):
        self.assertEqual(typechart.effectiveness("Fighting", ["ghost"], ("ghost",)), 1)

    def test_super_effective_and_resisted(self):
        self.assertEqual(typechart.effectiveness("Fire", ["grass", "steel"]), 4)
        self.assertEqual(typechart.effectiveness("Fire", ["water"]), 0.5)


class Damage(unittest.TestCase):
    MOVE = {"type": "Dragon", "category": "Physical", "base_power": 80}

    def test_known_value(self):
        a, d = mons()
        # Atk 150, Def 100, bp 80: 22*80*150//100//50 + 2 = 54; STAB x1.5 = 81; neutral
        self.assertEqual(dmg.damage(a, d, self.MOVE, roll=100), 81)

    def test_roll_scales(self):
        a, d = mons()
        self.assertEqual(dmg.damage(a, d, self.MOVE, roll=85), 54 * 85 // 100 * 3 // 2)

    def test_immune_is_zero(self):
        a, d = mons()
        g = teams.build_mon({"species": "gengar"})
        fight = {"type": "Fighting", "category": "Physical", "base_power": 120}
        self.assertEqual(dmg.damage(a, g, fight), 0)

    def test_stages_and_crit(self):
        a, d = mons()
        a.stages["atk"] = -2
        base = dmg.damage(a, d, self.MOVE)
        self.assertLess(base, 81)
        self.assertGreater(dmg.damage(a, d, self.MOVE, crit=True), 81)  # crit ignores the drop

    def test_spread_and_burn(self):
        a, d = mons()
        self.assertLess(dmg.damage(a, d, self.MOVE, spread=True), 81)
        a.status = "brn"
        self.assertLess(dmg.damage(a, d, self.MOVE), 81)

    def test_status_move_is_zero_and_minimum_one(self):
        a, d = mons()
        self.assertEqual(dmg.damage(a, d, {"type": "Normal", "category": "Status", "base_power": 0}), 0)
        d.stats["def"] = 10_000
        self.assertEqual(dmg.damage(a, d, self.MOVE, roll=85), 1)


if __name__ == "__main__":
    unittest.main()
