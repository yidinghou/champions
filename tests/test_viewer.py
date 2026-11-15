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

    def test_writes_self_contained_html(self):
        with tempfile.TemporaryDirectory() as t:
            html = write_html(REPLAYS[0], Path(t) / "x.html").read_text()
            self.assertIn("const DATA =", html)
            self.assertNotIn("__DATA__", html)
            self.assertNotIn('src="http', html)


if __name__ == "__main__":
    unittest.main()
