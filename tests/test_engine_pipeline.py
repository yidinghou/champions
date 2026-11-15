"""Unit tests for pipeline pieces whose behavior the catalogue cases cannot pin exactly."""
import unittest
from types import SimpleNamespace as NS

from champions.catalogue.runner import Result, run_case
from champions.engine import game, teams
from champions.engine.actions import Move
from champions.engine.pipeline import accuracy, hit
from champions.engine.rng import ForcedRng, LabeledRng, Rng


def spec(species, moves=(), ability="noability", **kw):
    return dict(species=species, moves=list(moves), ability=ability, **kw)


class Accuracy(unittest.TestCase):
    def test_stage_multipliers(self):
        self.assertAlmostEqual(accuracy.multiplier(0), 1)
        self.assertAlmostEqual(accuracy.multiplier(1), 4 / 3)
        self.assertAlmostEqual(accuracy.multiplier(6), 3)
        self.assertAlmostEqual(accuracy.multiplier(-1), 3 / 4)
        self.assertAlmostEqual(accuracy.multiplier(-6), 1 / 3)

    def test_final_accuracy_from_stage_difference(self):
        u, t = NS(stages={"acc": 1}, item=None), NS(stages={"eva": 0}, item=None, ability=None)
        self.assertEqual(accuracy.final_accuracy(u, t, 80), 106)       # 80 x 4/3
        t.stages["eva"] = 1
        self.assertEqual(accuracy.final_accuracy(u, t, 80), 80)        # +1 acc and +1 eva cancel
        u.stages["acc"] = 0
        self.assertEqual(accuracy.final_accuracy(u, t, 50), 37)        # 50 x 3/4
        u.stages["acc"] = 6
        t.stages["eva"] = -6
        self.assertEqual(accuracy.final_accuracy(u, t, 50), 150)       # difference is capped at +6


class Crit(unittest.TestCase):
    def test_chance_by_stage(self):
        pct = lambda stage: hit.crit_pct(NS(effects={"crit_stage": stage}, user=NS(item=None)))
        self.assertAlmostEqual(pct(0), 100 / 24)
        self.assertEqual([pct(1), pct(2), pct(3), pct(7)], [12.5, 50, 100, 100])


class HitCount(unittest.TestCase):
    def count(self, mh, roll):
        ctx = NS(move={"multihit": mh}, battle=NS(rng=ForcedRng([roll])), user=NS(ability=None))
        return hit.hit_count(ctx)

    def test_fixed(self):
        self.assertEqual((self.count(None, 1), self.count(2, 1), self.count(3, 1), self.count(10, 1)), (1, 2, 3, 10))

    def test_two_to_five_bands(self):
        got = [self.count([2, 5], r) for r in (1, 35, 36, 70, 71, 85, 86, 100)]
        self.assertEqual(got, [2, 2, 3, 3, 4, 4, 5, 5])


class Handlers(unittest.TestCase):
    def play(self, a, b, turns, rng=None, fmt="singles"):
        bt = game.start([a, b], format=fmt, rng=rng or LabeledRng())
        for t in turns:
            game.play_turn(bt, t)
        return bt

    def test_recoil_minimum_one(self):
        b = self.play([spec("snorlax", ["doubleedge"])], [spec("garchomp", ["dragonclaw"], hp=2)], [[Move(0, 0, "doubleedge", (1, 0))]])
        self.assertEqual(b.events("recoil")[0].data["amount"], 1)      # 2 damage dealt, 2 // 3 = 0, floored up to 1

    def test_drain_capped_by_remaining_hp(self):
        b = self.play([spec("gengar", ["gigadrain"], hp=1)], [spec("incineroar", ["dragonclaw"], hp=10)], [[Move(0, 0, "gigadrain", (1, 0))]])
        self.assertEqual(b.events("heal")[0].data["amount"], 5)        # 10 HP dealt, not the full hit

    def test_guard_dog_flips_to_plus_one(self):
        b = game.start([[spec("incineroar", ability="intimidate")], [spec("mabosstiff", ability="guarddog")]], format="singles")
        self.assertEqual(b.mon(1, 0).stages["atk"], 1)

    def test_intimidate_stacks_and_floors_at_minus_six(self):
        b = game.start([[spec("incineroar", ability="intimidate")], [spec("garchomp", ability="sandveil")]], format="singles")
        b.mon(1, 0).stages["atk"] = -6
        from champions.engine.stages import change_stat
        self.assertEqual(change_stat(b, b.mon(1, 0), "atk", -1, source=b.mon(0, 0), cause="intimidate"), 0)

    def test_protect_chain_resets_after_another_move(self):
        b = self.play([spec("garchomp", ["dragonclaw"])], [spec("incineroar", ["protect", "dragonclaw"], "blaze")],
                      [[Move(1, 0, "protect")], [Move(1, 0, "dragonclaw", (0, 0))], [Move(1, 0, "protect")]],
                      rng=LabeledRng({"protect": [False]}))
        self.assertEqual(b.events("fail", reason="protect_chain"), [])  # chain was reset by the Dragon Claw

    def test_mega_choice_needs_the_stone(self):
        b = game.start([[spec("garchomp", ["dragonclaw"])], [spec("incineroar", ["protect"], "blaze")]], format="singles")
        with self.assertRaises(ValueError):
            game.play_turn(b, [Move(0, 0, "dragonclaw", (1, 0), mega=True)])


class Runner(unittest.TestCase):
    def test_case_without_checks_fails(self):
        owner = {"id": "x"}
        case = {"id": "y", "kind": "positive", "status": "ok", "setup": "s", "expect": "e",
                "run": {"format": "singles", "teams": [[spec("garchomp")], [spec("incineroar", ability="blaze")]]}}
        self.assertFalse(run_case(owner, case).passed)

    def test_broken_handler_gives_a_readable_failure(self):
        from champions.catalogue.runner import format_failure
        from champions.engine import hooks
        owner = {"id": "self-drop", "source": ["showdown: x"]}
        case = {"id": "immune-no-drop", "kind": "control", "status": "ok", "setup": "CC into Gengar", "expect": "no drop",
                "run": {"format": "singles", "teams": [[spec("sneasler", ["closecombat"])], [spec("gengar", ["protect"])]],
                        "turns": [[{"side": 0, "slot": 0, "move": "closecombat", "target": [1, 0]}]],
                        "check": [{"mon": "p1:sneasler", "stage": "def", "eq": 0}]}}
        self.assertTrue(run_case(owner, case).passed)
        # break the immunity stage: the self-drop now fires on an immune target
        import champions.engine.pipeline as pl
        saved = list(pl.STAGES)
        pl.STAGES[:] = [s for s in saved if s.__module__.rsplit(".", 1)[-1] != "immunity"]
        try:
            res = run_case(owner, case)
        finally:
            pl.STAGES[:] = saved
        self.assertFalse(res.passed)
        text = format_failure(res)
        for needle in ("self-drop::immune-no-drop", "expect:  no drop", "FAILED check", "actual: -1", "event log", "boost"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
