"""Hand-computed checks for calc.py. Run: python3 -m unittest tests.test_calc"""
import unittest

from champions.calc import chain, poke_round, rolls, stage, type_multiplier
from champions.lookup import load


class DamageMath(unittest.TestCase):
    def test_base_damage_and_rolls(self):
        # Level 50, power 100, A=200, D=100: floor(22*100*200/100)=4400; //50 = 88; +2 = 90.
        base = (22 * 100 * 200 // 100) // 50 + 2
        self.assertEqual(base, 90)
        r = rolls(base, [("random", None)])
        self.assertEqual((min(r), max(r), len(r)), (76, 90, 16))  # floor(90*85/100)=76

    def test_modifier_order_floors_each_step(self):
        # 90 -> spread x0.75 = 67.5 rounds half down to 67 -> roll 100% = 67 -> STAB x1.5 = 100.5 -> 100
        r = rolls(90, [("spread", 3072), ("random", None), ("stab", 6144)])
        self.assertEqual(max(r), 100)

    def test_poke_round_is_half_down(self):
        self.assertEqual(poke_round(90, 3072), 67)   # 67.5 rounds down
        self.assertEqual(poke_round(91, 3072), 68)   # 68.25 -> 68
        self.assertEqual(poke_round(3, 2048), 1)     # 1.5 rounds down

    def test_stages(self):
        self.assertEqual(stage(1), 1.5)
        self.assertEqual(stage(-2), 0.5)
        self.assertEqual(stage(0), 1)

    def test_type_chart(self):
        chart = load("types.json")["chart"]
        self.assertEqual(type_multiplier("Ground", ["flying"], chart), 0)
        self.assertEqual(type_multiplier("Ice", ["dragon", "flying"], chart), 4)
        self.assertEqual(type_multiplier("Fire", ["water", "rock"], chart), 0.25)


class Chain(unittest.TestCase):
    def test_single_modifier_is_unchanged(self):
        self.assertEqual(chain([5324]), 5324)

    def test_two_modifiers_round_once(self):
        # Showdown chainModify: (m1 * m2 + 2048) >> 12; 0.5 * 0.75 = 1536
        self.assertEqual(chain([2048, 3072]), 1536)
        self.assertEqual(chain([]), 4096)


if __name__ == "__main__":
    unittest.main()
