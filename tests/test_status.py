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

    def test_sleep_lasts_two_or_three_attempts(self):
        """Champions: asleep on turn 1, 1/3 chance to wake on turn 2, certain on turn 3."""
        for roll, turns in ((True, 2), (False, 3)):
            b = game.start([[{"species": "snorlax", "ability": "thickfat", "moves": ["bodyslam"]}],
                            [{"species": "clefable", "ability": "unaware", "moves": ["protect"]}]],
                           seed=1, format="singles", rng=LabeledRng({"sleep_turns": [roll]}))
            from champions.engine.status import try_set_status
            try_set_status(b, b.mon(0, 0), "slp")
            self.assertEqual(b.mon(0, 0).status_turns, turns)

    def test_freeze_thaws_by_the_third_attempt(self):
        b = game.start([[{"species": "snorlax", "ability": "thickfat", "moves": ["bodyslam"], "status": "frz"}],
                        [{"species": "clefable", "ability": "unaware", "moves": ["protect"]}]],
                       seed=1, format="singles", rng=LabeledRng({"thaw": [False, False, False]}))
        for _ in range(2):
            game.play_turn(b, [game.Move(0, 0, "bodyslam", (1, 0))])
            self.assertEqual(b.mon(0, 0).status, "frz")
        game.play_turn(b, [game.Move(0, 0, "bodyslam", (1, 0))])
        self.assertIsNone(b.mon(0, 0).status)

    def test_full_paralysis_is_one_in_eight(self):
        from champions.engine import status
        self.assertEqual(status.FULL_PARA_PCT, 12.5)
        b = self.play("par", 0, {"fullpara": [True]})
        self.assertEqual(len(b.events("move", mon="p1:snorlax")), 0)
        self.assertEqual(len(b.events("fail", mon="p1:snorlax", reason="paralyzed")), 1)


if __name__ == "__main__":
    unittest.main()


class GutsAndMagicGuard(unittest.TestCase):
    def dmg(self, status, ability):
        a = mon("heracross", ability, ["bodyslam"], status=status)
        d = mon("clefable", "unaware", ["protect"])
        return damage(a, d, moves_data()["bodyslam"], crit=False, roll=100, spread=False)

    def test_guts_boosts_attack_and_ignores_burn(self):
        base = self.dmg(None, "swarm")
        guts_burned = self.dmg("brn", "guts")
        self.assertGreater(guts_burned, base)                     # about x1.5, and not halved
        self.assertAlmostEqual(guts_burned / base, 1.5, delta=0.05)

    def test_guts_needs_a_status(self):
        self.assertEqual(self.dmg(None, "guts"), self.dmg(None, "swarm"))

    def test_guts_ignores_special_moves(self):
        a = mon("heracross", "guts", ["shadowball"], status="brn")
        b = mon("heracross", "swarm", ["shadowball"])
        d = mon("clefable", "unaware", [])
        mv = moves_data()["shadowball"]
        self.assertEqual(damage(a, d, mv, roll=100), damage(b, d, mv, roll=100))

    def test_magic_guard_blocks_all_status_damage(self):
        for status in ("brn", "psn", "tox"):
            m = mon("clefable", "magicguard", [], status=status)
            self.assertEqual(residual_damage(m), 0, status)

    def test_magic_guard_toxic_counter_still_ticks(self):
        m = mon("clefable", "magicguard", [], status="tox")
        residual_damage(m)
        self.assertEqual(m.status_turns, 1)


class Yawn(unittest.TestCase):
    def test_switching_out_cancels_yawn(self):
        m = mon("jolteon", "quickfeet", [])
        m.volatiles["yawn"] = 1
        m.clear_on_switch()
        self.assertNotIn("yawn", m.volatiles)


class RestAndBell(unittest.TestCase):
    def test_sleeper_cannot_act_so_rest_does_not_run(self):
        b = game.start([[{"species": "snorlax", "ability": "thickfat", "moves": ["rest"],
                          "status": "slp", "status_turns": 5, "hp": 100}],
                        [{"species": "clefable", "ability": "unaware", "moves": ["protect"]}]],
                       seed=1, format="singles", rng=LabeledRng({}))
        b.mon(0, 0).status_turns = 5
        game.play_turn(b, [game.Move(0, 0, "rest", None)])
        # asleep mons cannot act at all, so Rest never ran; the counter just dropped
        self.assertEqual(b.mon(0, 0).status, "slp")
        self.assertEqual(b.mon(0, 0).status_turns, 4)
