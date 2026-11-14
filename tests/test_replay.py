import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from champions import cli
from champions.engine import game, replay
from champions.engine.actions import Move
from champions.engine.replay import ReplayError

REPLAYS = Path(__file__).parent / "replays"


class Determinism(unittest.TestCase):
    def test_every_committed_replay_is_deterministic(self):
        paths = sorted(REPLAYS.glob("*.json"))
        self.assertTrue(paths)
        for p in paths:
            self.assertEqual(replay.log_to_list(replay.replay(p)), replay.log_to_list(replay.replay(p)), p.name)

    def test_different_seed_can_differ(self):
        r = replay.load_replay(REPLAYS / "fakeout_turn.json")
        a = replay.log_to_list(replay.play_replay(r))
        r2 = dict(r, seed=r["seed"] + 1)
        self.assertNotEqual(a, replay.log_to_list(replay.play_replay(r2)))

    def test_sample_replay_flinches_garchomp(self):
        b = replay.replay(REPLAYS / "fakeout_turn.json")
        self.assertEqual(b.events("fail", mon="p2:garchomp", reason="flinch")[0].turn, 1)


class SaveLoad(unittest.TestCase):
    def test_save_then_load_roundtrip(self):
        teams = [[dict(species="incineroar", ability="blaze", moves=["fakeout"])],
                 [dict(species="garchomp", ability="sandveil", moves=["dragonclaw"])]]
        turns = [[Move(0, 0, "fakeout", (1, 0)), Move(1, 0, "dragonclaw", (0, 0))]]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.json"
            replay.save_replay(p, teams, 9, turns, "singles")
            r = replay.load_replay(p)
            self.assertEqual(r["turns"][0][0]["move"], "fakeout")
            b = replay.play_replay(r)
            replay.save_log(Path(d) / "log.json", b)
            self.assertEqual(json.loads((Path(d) / "log.json").read_text()), replay.log_to_list(b))

    def test_version_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.json"
            r = json.loads((REPLAYS / "fakeout_turn.json").read_text())
            r["version"] = 99
            p.write_text(json.dumps(r))
            with self.assertRaisesRegex(ReplayError, "version"):
                replay.load_replay(p)

    def test_missing_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.json"
            p.write_text(json.dumps({"version": 1}))
            with self.assertRaises(ReplayError):
                replay.load_replay(p)


class Snapshot(unittest.TestCase):
    def mid_battle(self):
        r = replay.load_replay(REPLAYS / "fakeout_turn.json")
        b = game.start(r["teams"], r["seed"], r["format"])
        from champions.engine.actions import from_dict
        game.play_turn(b, [from_dict(c) for c in r["turns"][0]])
        return b, r

    def test_roundtrip_equals_original(self):
        b, _ = self.mid_battle()
        snap = replay.snapshot(b)
        self.assertEqual(replay.snapshot(replay.restore(copy.deepcopy(snap))), snap)

    def test_snapshot_is_json_serialisable(self):
        b, _ = self.mid_battle()
        snap = replay.snapshot(b)
        self.assertEqual(json.loads(json.dumps(snap)), snap)

    def test_restored_battle_continues_identically(self):
        from champions.engine.actions import from_dict
        b, r = self.mid_battle()
        clone = replay.restore(json.loads(json.dumps(replay.snapshot(b))))
        second = [from_dict(c) for c in r["turns"][1]]
        game.play_turn(b, second)
        game.play_turn(clone, second)
        self.assertEqual(replay.log_to_list(b), replay.log_to_list(clone))


class Cli(unittest.TestCase):
    def test_sim_replay_prints_log(self):
        out = io.StringIO()
        with redirect_stdout(out):
            import sys
            old = sys.argv
            try:
                cli.main(["sim", "replay", str(REPLAYS / "fakeout_turn.json")])
            finally:
                sys.argv = old
        self.assertIn("reason=flinch", out.getvalue())


if __name__ == "__main__":
    unittest.main()
