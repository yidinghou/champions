"""Data-driven damage checks. Add real hits to data/damage_cases.json; run: python3 -m unittest test_damage_cases -v"""
import json
import unittest
from pathlib import Path

from calc import damage

CASES = json.loads((Path(__file__).parent / "data" / "damage_cases.json").read_text())["cases"]


class DamageCases(unittest.TestCase):
    def test_cases(self):
        for c in CASES:
            with self.subTest(c["name"]):
                if c.get("skip"):
                    self.skipTest("parked")
                rolls, hp, notes, _ = damage(c["attacker"], c["move"], c["defender"], **c.get("opts", {}))
                if "expected" in c:
                    got, want = [min(rolls), max(rolls)], c["expected"]
                else:  # percentages: allow the game's rounding to whole percent
                    got = [round(min(rolls) / hp * 100), round(max(rolls) / hp * 100)]
                    want = c["expected_pct"]
                self.assertEqual(got, want, f"{c['name']} [{c['source']}] applied: {'; '.join(notes)}")
                if "rolls" in c:
                    self.assertEqual(sorted(rolls), c["rolls"], f"{c['name']}: all 16 rolls")


if __name__ == "__main__":
    unittest.main()
