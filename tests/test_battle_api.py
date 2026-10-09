"""Engine surface the UI relies on: legal actions, snapshots, per-action frames, forced replacements, dex."""
import unittest

from champions.battle import Battle
from champions.battle.dex import dex
from champions.battle.moves import is_supported

M = "mudslap"


def mon(sp, moves=(M,), **kw):
    return dict({"species": sp, "moves": list(moves)}, **kw)


def duel(**kw):
    return Battle({"p1": [mon("incineroar", ["fakeout", M, "protect", "swordsdance"]), mon("kingambit")],
                   "p2": [mon("garchomp", hp=1), mon("arcanine")]}, **kw)


class Supported(unittest.TestCase):
    def test_whitelist(self):
        for ok in ("mudslap", "fakeout", "protect", "trickroom", "tailwind", "electroball", "gyroball", "quickattack"):
            self.assertTrue(is_supported(ok), ok)
        for bad in ("swordsdance", "solarbeam", "electroshot", "hyperbeam", "earthquake", "heavyslam", "seismictoss", "counter"):
            self.assertFalse(is_supported(bad), bad)  # status/charge/recharge/spread/variable-power are not modeled yet


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

    def test_bad_switch_target(self):
        with self.assertRaises(ValueError):
            duel().turn({"p1a": {"switch": 0}, "p2a": {"move": M, "target": "p1a"}})  # already active

    def test_turn_blocked_while_replacement_pending_and_after_the_end(self):
        b = duel()
        b.turn({"p1a": {"move": M, "target": "p2a"}, "p2a": {"move": M, "target": "p1a"}})
        self.assertEqual(b.pending_replacements(), ["p2a"])
        with self.assertRaises(ValueError):
            b.turn({"p1a": {"move": M, "target": "p2a"}, "p2a": {"move": M, "target": "p1a"}})
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
