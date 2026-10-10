"""Engine surface the UI relies on: legal actions, snapshots, per-action frames, forced replacements, dex."""
import unittest

from champions.battle import Battle
from champions.calc import damage
from champions.battle.dex import dex
from champions.battle.moves import is_supported

M = "mudslap"


def mon(species, moves=(M,), **kw):
    return dict({"species": species, "moves": list(moves)}, **kw)


def duel(**kw):
    return Battle({"p1": [mon("incineroar", ["fakeout", M, "protect", "swordsdance"]), mon("kingambit")],
                   "p2": [mon("garchomp", hp=1), mon("arcanine")]}, **kw)


class Supported(unittest.TestCase):
    def test_whitelist(self):
        for ok in ("mudslap", "fakeout", "protect", "trickroom", "tailwind", "electroball", "gyroball", "quickattack", "earthquake", "rockslide"):
            self.assertTrue(is_supported(ok), ok)
        for bad in ("swordsdance", "solarbeam", "electroshot", "hyperbeam", "heavyslam", "seismictoss", "counter"):
            self.assertFalse(is_supported(bad), bad)  # status/charge/recharge/variable-power are not modeled yet

    def test_spread_moves_have_no_target_choice(self):
        b = Battle({"p1": [mon("incineroar", ["earthquake"]), mon("kingambit")], "p2": [mon("garchomp"), mon("arcanine")]}, active=2)
        self.assertIsNone(b.legal_actions("p1a")["moves"][0]["targets"])


class LegalActions(unittest.TestCase):
    def test_moves_targets_and_switches(self):
        b = duel()
        la = b.legal_actions("p1a")
        self.assertEqual([m["move"] for m in la["moves"]], ["fakeout", M, "protect"], "swordsdance is unsupported")
        self.assertEqual(la["moves"][0]["targets"], ["p2a"])
        self.assertIsNone(la["moves"][2]["targets"], "Protect has no target")
        self.assertEqual(la["switches"], [1])

    def test_doubles_targets_include_ally(self):
        b = Battle({"p1": [mon("incineroar"), mon("kingambit")], "p2": [mon("garchomp"), mon("arcanine")]}, active=2)
        self.assertEqual(b.legal_actions("p1a")["moves"][0]["targets"], ["p1b", "p2a", "p2b"])

    def test_fainted_or_empty_slot_has_none(self):
        b = duel()
        b.turn({"p1a": {"move": "quickattack" if False else M, "target": "p2a"}, "p2a": {"move": M, "target": "p1a"}})
        self.assertEqual(b.legal_actions("p2a"), {"moves": [], "switches": []})

    def test_unsupported_move_is_rejected_cleanly(self):
        with self.assertRaises(ValueError):
            duel().turn({"p1a": {"move": "swordsdance"}, "p2a": {"move": M, "target": "p1a"}})


class Validation(unittest.TestCase):
    def test_missing_action(self):
        with self.assertRaises(ValueError):
            duel().turn({"p1a": {"move": M, "target": "p2a"}})

    def test_bad_targets(self):
        for target in ("p1a", "p9z", None):  # self, unknown slot, missing
            with self.assertRaises(ValueError, msg=repr(target)):
                duel().turn({"p1a": {"move": M, "target": target}, "p2a": {"move": M, "target": "p1a"}})

    def test_both_sides_wiped_out_is_a_draw(self):
        b = Battle({"p1": [mon("incineroar")], "p2": [mon("garchomp")]})
        b.team_mon("p1:0").hp = b.team_mon("p2:0").hp = 0
        b._settle()  # no supported move can KO both sides yet (needs recoil or self-KO), so settle is driven directly
        self.assertEqual(b.winner, "draw")

    def test_bad_switch_target(self):
        with self.assertRaises(ValueError):
            duel().turn({"p1a": {"switch": 0}, "p2a": {"move": M, "target": "p1a"}})  # already active

    def test_turn_blocked_while_replacement_pending_and_after_the_end(self):
        b = duel()
        b.turn({"p1a": {"move": M, "target": "p2a"}, "p2a": {"move": M, "target": "p1a"}})
        self.assertEqual(b.pending_replacements(), ["p2a"])
        with self.assertRaisesRegex(ValueError, "replacement"):
            b.turn({"p1a": {"move": M, "target": "p2a"}})  # only the living slot acts, so only the pending check can reject it
        with self.assertRaises(ValueError):
            b.replace("p1a", 1)  # p1a has not fainted
        b.replace("p2a", 1)
        self.assertEqual(b.pending_replacements(), [])
        solo = Battle({"p1": [mon("incineroar")], "p2": [mon("garchomp", hp=1)]})
        solo.turn({"p1a": {"move": M, "target": "p2a"}, "p2a": {"move": M, "target": "p1a"}})
        self.assertEqual(solo.winner, "p1")
        with self.assertRaises(ValueError):
            solo.turn({"p1a": {"move": M, "target": "p2a"}})

    def test_replace_requires_a_living_benched_mon(self):
        b = Battle({"p1": [mon("incineroar")], "p2": [mon("garchomp", hp=1), mon("arcanine", hp=1)]})
        b.team_mon("p2:1").hp = 0
        b.turn({"p1a": {"move": M, "target": "p2a"}, "p2a": {"move": M, "target": "p1a"}})
        self.assertEqual(b.winner, "p1", "no living reserve means the battle is over")


class SnapshotAndFrames(unittest.TestCase):
    def test_snapshot_shape(self):
        s = duel().snapshot()
        self.assertEqual(s["turn"], 0)
        a = s["slots"]["p1a"]
        for key in ("species", "types", "hp", "max_hp", "status", "boosts", "item", "ability", "speed", "turns_out"):
            self.assertIn(key, a)
        self.assertEqual(s["field"]["trick_room"], 0)
        self.assertEqual([m["species"] for m in s["bench"]["p1"]], ["kingambit"])
        self.assertIsNone(s["winner"])

    def test_frames_one_per_action_plus_start_and_end(self):
        b = Battle({"p1": [mon("incineroar", ["trickroom", M])], "p2": [mon("garchomp")]})
        r = b.turn({"p1a": {"move": "trickroom"}, "p2a": {"move": M, "target": "p1a"}})
        self.assertEqual(len(r.frames), 4)  # start, garchomp, incineroar (Trick Room is -7), end of turn
        self.assertEqual([f["actor"] for f in r.frames], [None, "p2a", "p1a", None])
        self.assertEqual(r.frames[0]["state"]["field"]["trick_room"], 0)
        self.assertEqual(r.frames[2]["state"]["field"]["trick_room"], 5)
        self.assertEqual(r.frames[3]["state"]["field"]["trick_room"], 4)
        self.assertEqual(r.frames[1]["target"], "p1a")
        self.assertLess(r.frames[1]["state"]["slots"]["p1a"]["hp"], r.frames[0]["state"]["slots"]["p1a"]["hp"])


class DamageWiring(unittest.TestCase):
    """HP loss must be one of calc.damage's 16 rolls, with nature, Stat Points and item passed through."""
    ATT = mon("garchomp", ["dragonclaw"], nature="adamant", sp={"attack": 32, "speed": 32}, item="lifeorb")
    DEF = mon("incineroar", [M], nature="bold", sp={"hp": 32, "defense": 32})
    CALC = dict(atk_nature="adamant", atk_sp="attack=32,speed=32", item="lifeorb",
                def_nature="bold", def_sp="hp=32,defense=32")

    def hit(self, **battle_kw):
        b = Battle({"p1": [self.ATT], "p2": [self.DEF]}, **battle_kw)
        b.turn({"p1a": {"move": "dragonclaw", "target": "p2a"}, "p2a": {"move": M, "target": "p1a"}})
        d = b.mon("p2a")
        return d.max_hp - d.hp, d.max_hp

    def test_damage_is_always_one_of_the_calc_rolls(self):
        rolls, hp, _, _ = damage("garchomp", "dragonclaw", "incineroar", **self.CALC)
        seen = set()
        for seed in range(10):
            dealt, max_hp = self.hit(seed=seed)
            self.assertEqual(max_hp, hp, "defender HP must match the calc's defender HP")
            self.assertIn(dealt, rolls, f"seed {seed}: {dealt} is not a calc roll; range {min(rolls)}-{max(rolls)}")
            seen.add(dealt)
        self.assertGreater(len(seen), 1, "10 seeds should not all roll the same damage")

    def test_forced_rolls_hit_the_ends_of_the_range(self):
        rolls, _, _, _ = damage("garchomp", "dragonclaw", "incineroar", **self.CALC)
        self.assertLess(max(rolls), self.hit()[1], "test setup must not KO, or the HP clamp hides the roll")
        self.assertEqual(self.hit(rolls="max")[0], max(rolls))
        self.assertEqual(self.hit(rolls="min")[0], min(rolls))


class Dex(unittest.TestCase):
    def test_dex_only_lists_supported_moves(self):
        d = dex()
        g = d["species"]["garchomp"]
        self.assertIn("types", g)
        self.assertTrue(g["moves"], "garchomp should have supported moves")
        for m in g["moves"]:
            self.assertTrue(is_supported(m), m)
        self.assertIn("fakeout", d["moves"])
        self.assertIn("choicescarf", d["items"])
        self.assertIn("jolly", d["natures"])


if __name__ == "__main__":
    unittest.main()
