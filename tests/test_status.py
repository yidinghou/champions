"""Unit tests for major status: numbers the catalogue cases only pin indirectly."""
import unittest

from champions.calc.damage import damage
from champions.engine import game
from champions.engine.rng import LabeledRng
from champions.engine.status import residual_damage
from champions.engine.teams import build_mon, moves_data


def mon(species, ability, moves, **kw):
    return build_mon({"species": species, "ability": ability, "moves": moves, **kw})


class BurnDamage(unittest.TestCase):
    def dmg(self, move, status):
        a = mon("snorlax", "thickfat", [move], status=status)
        d = mon("clefable", "unaware", ["protect"])
        return damage(a, d, moves_data()[move], crit=False, roll=100, spread=False)

    def test_burn_halves_physical(self):
        plain, burned = self.dmg("bodyslam", None), self.dmg("bodyslam", "brn")
        self.assertEqual(burned, plain // 2)

    def test_burn_keeps_special(self):
        self.assertEqual(self.dmg("shadowball", "brn"), self.dmg("shadowball", None))


class Residual(unittest.TestCase):
    def test_amounts(self):
        m = mon("snorlax", "thickfat", [], status="brn")
        self.assertEqual(residual_damage(m), m.max_hp // 16)
        m.status = "psn"
        self.assertEqual(residual_damage(m), m.max_hp // 8)
        m.status = None
        self.assertEqual(residual_damage(m), 0)

    def test_toxic_grows_and_caps(self):
        m = mon("snorlax", "thickfat", [], status="tox")
        got = [residual_damage(m) for _ in range(17)]
        self.assertEqual(got[:3], [m.max_hp // 16 * n for n in (1, 2, 3)])
        self.assertEqual(got[-1], m.max_hp // 16 * 15)

    def test_toxic_restarts_on_switch_but_status_stays(self):
        m = mon("snorlax", "thickfat", [], status="tox", status_turns=3)
        m.clear_on_switch()
        self.assertEqual((m.status, m.status_turns), ("tox", 0))

    def test_sleep_counter_kept_on_switch(self):
        m = mon("snorlax", "thickfat", [], status="slp", status_turns=2)
        m.clear_on_switch()
        self.assertEqual((m.status, m.status_turns), ("slp", 2))


class SleepAndFreeze(unittest.TestCase):
    def play(self, status, turns, rolls):
        b = game.start([[{"species": "snorlax", "ability": "thickfat", "moves": ["bodyslam"],
                          "status": status, "status_turns": turns}],
                        [{"species": "clefable", "ability": "unaware", "moves": ["protect"]}]],
                       seed=1, format="singles", rng=LabeledRng(rolls))
        game.play_turn(b, [game.Move(0, 0, "bodyslam", (1, 0))])
        return b

    def test_sleeper_wakes_when_counter_hits_zero_and_acts(self):
        b = self.play("slp", 1, {})
        self.assertIsNone(b.mon(0, 0).status)
        self.assertEqual(len(b.events("move", mon="p1:snorlax")), 1)

    def test_frozen_thaws_on_roll_and_acts(self):
        b = self.play("frz", 0, {"thaw": [True]})
        self.assertIsNone(b.mon(0, 0).status)
        self.assertEqual(len(b.events("move", mon="p1:snorlax")), 1)


if __name__ == "__main__":
    unittest.main()
