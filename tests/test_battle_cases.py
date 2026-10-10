"""Data-driven battle scenarios. Add cases to data/battle_cases.json (schema: docs/BATTLE_CASES.md);
run: python3 -m unittest tests.test_battle_cases -v"""
import json
import random
import unittest

from champions.battle import Battle
from champions.calc import damage
from champions.lookup import DATA

CASES = json.loads((DATA / "battle_cases.json").read_text())["cases"]


class BattleCases(unittest.TestCase):
    def test_cases(self):
        for c in CASES:
            with self.subTest(c["name"]):
                if c.get("skip"):
                    self.skipTest("parked")
                b = Battle(c["teams"], active=c.get("active", 1), field=c.get("field"), seed=c.get("seed", 0),
                           chance=c.get("chance"))
                want = c["expect"]
                for i, actions in enumerate(c["turns"]):
                    if "_replace" in actions:  # forced-switch step after a KO
                        for slot, idx in actions["_replace"].items():
                            b.replace(slot, idx)
                        continue
                    got = b.turn(actions)
                    ctx = f"{c['name']} [{c['source']}] turn {i + 1}; log: {got.log}"
                    if i >= len(want["turns"]):
                        continue
                    for key, val in want["turns"][i].items():
                        self.assertEqual(getattr(got, key), val, f"{key}: {ctx}")
                final = want.get("final", {})
                for slot, species in final.get("active", {}).items():
                    got_mon = b.mon(slot)
                    self.assertEqual(got_mon.species if got_mon else None, species, f"active {slot}")
                if "winner" in final:
                    self.assertEqual(b.winner, final["winner"], "winner")
                for ref in final.get("fainted", []):
                    self.assertEqual(b.team_mon(ref).hp, 0, f"{ref} should have fainted")
                for ref in final.get("damaged", []):
                    self.assertLess(b.team_mon(ref).hp, b.team_mon(ref).max_hp, f"{ref} should be damaged")
                for ref in final.get("full", []):
                    self.assertEqual(b.team_mon(ref).hp, b.team_mon(ref).max_hp, f"{ref} should be at full HP")
                for key, val in final.get("field", {}).items():
                    self.assertEqual(b.field[key], val, f"field {key}")


class SpeedTies(unittest.TestCase):
    def test_tie_is_random_but_seeded(self):
        team = {"p1": [{"species": "garchomp", "moves": ["mudslap"]}],
                "p2": [{"species": "garchomp", "moves": ["mudslap"]}]}
        acts = {"p1a": {"move": "mudslap", "target": "p2a"}, "p2a": {"move": "mudslap", "target": "p1a"}}
        orders = {tuple(Battle(team, seed=s).turn(acts).order) for s in range(20)}
        self.assertEqual(len(orders), 2, "a speed tie should resolve both ways across seeds")
        self.assertEqual(Battle(team, seed=7).turn(acts).order, Battle(team, seed=7).turn(acts).order)


class SpreadDamage(unittest.TestCase):
    """The x0.75 spread modifier applies only while two or more targets are actually hit."""
    def _hp_lost(self, p2a_move):
        teams = {"p1": [{"species": "garchomp", "moves": ["rockslide"]}, {"species": "incineroar", "moves": ["tailwind"]}],
                 "p2": [{"species": "kingambit", "moves": ["protect", "tailwind"]},
                        {"species": "incineroar", "moves": ["tailwind"]}]}
        b = Battle(teams, active=2, rolls="max")
        b.turn({"p1a": {"move": "rockslide"}, "p1b": {"move": "tailwind"}, "p2a": {"move": p2a_move},
                "p2b": {"move": "tailwind"}})
        return b.team_mon("p2:1").max_hp - b.team_mon("p2:1").hp

    def test_two_targets_x075_and_one_target_x1(self):
        full = lambda spread: max(damage("garchomp", "rockslide", "incineroar", doubles=True, spread=spread)[0])
        self.assertEqual(self._hp_lost("tailwind"), full(True))
        self.assertEqual(self._hp_lost("protect"), full(False))
        self.assertGreater(full(False), full(True))


if __name__ == "__main__":
    unittest.main()
