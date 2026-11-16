import tempfile
import unittest
from pathlib import Path

from champions.engine.replay import load_replay
from champions.engine.viewer import build_frames, write_html

REPLAYS = sorted(Path(__file__).parent.glob("replays/*.json"))


class ViewerTests(unittest.TestCase):
    def test_every_replay_ends_on_the_engines_final_state(self):
        for p in REPLAYS:
            with self.subTest(p.name):
                d = build_frames(load_replay(p))
                self.assertEqual(d["frames"][0]["kind"], "start")
                last = {**d["frames"][-1]["state"], "turn": 0}
                self.assertEqual(last, {**d["final"], "turn": 0})

    def test_move_frames_name_their_targets_and_outcomes(self):
        d = build_frames(load_replay(Path(__file__).parent / "replays" / "spread_doubles.json"))
        eq = next(f for f in d["frames"] if f["kind"] == "move" and f["data"]["move"] == "earthquake")
        self.assertTrue(eq["spread"])
        self.assertEqual(eq["mtype"], "ground")
        self.assertEqual({(t["mon"], t["outcome"]) for t in eq["targets"]},
                         {("p2:charizard", "immune"), ("p2:garchomp", "missed"), ("p1:tyranitar", "hit")})

    def test_frames_are_grouped_into_actions_that_start_on_their_move(self):
        for p in REPLAYS:
            with self.subTest(p.name):
                fr = build_frames(load_replay(p))["frames"]
                groups = [f["group"] for f in fr]
                self.assertEqual(groups, sorted(groups))                      # never goes back to an earlier action
                for n, f in enumerate(fr):
                    if f["kind"] == "move":
                        self.assertTrue(n == 0 or fr[n - 1]["group"] != f["group"] or fr[n - 1]["kind"] == "mega")

    def test_a_crit_and_its_damage_share_the_moves_action(self):
        fr = build_frames(load_replay(Path(__file__).parent / "replays" / "trick_room.json"))["frames"]
        crit = next(f for f in fr if f["kind"] == "crit")
        move = [f for f in fr if f["kind"] == "move" and f["group"] == crit["group"]]
        self.assertEqual(len(move), 1)
        self.assertEqual(move[0]["data"]["move"], "surf")

    def test_writes_self_contained_html(self):
        with tempfile.TemporaryDirectory() as t:
            html = write_html(REPLAYS[0], Path(t) / "x.html").read_text()
            self.assertIn("const DATA =", html)
            self.assertNotIn("__DATA__", html)
            self.assertNotIn('src="http', html)


if __name__ == "__main__":
    unittest.main()
