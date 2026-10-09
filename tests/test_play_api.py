"""`champions play`: Session (config + action history) and the JSON API over a real local server."""
import json
import threading
import unittest
import urllib.error
import urllib.request

from champions.play.server import make_server
from champions.play.session import Session

M = "mudslap"


def mon(species, moves=(M,), **kw):
    return dict({"species": species, "moves": list(moves)}, **kw)


def config(**kw):
    cfg = {"teams": {"p1": [mon("incineroar", [M, "fakeout", "protect"]), mon("kingambit")],
                     "p2": [mon("garchomp", hp=1), mon("arcanine")]}, "active": 1, "seed": 7}
    cfg.update(kw)
    return cfg


def both(a="p1a", b="p2a"):
    return {a: {"move": M, "target": b}, b: {"move": M, "target": a}}


def hps(view):
    return {s: (m and m["hp"]) for s, m in view["snapshot"]["slots"].items()}


class SessionTests(unittest.TestCase):
    def test_new_returns_snapshot_and_legal_actions(self):
        s = Session()
        v = s.new(config(active=2, teams={"p1": [mon("incineroar"), mon("kingambit")],
                                          "p2": [mon("garchomp"), mon("arcanine")]}))
        self.assertEqual(sorted(v["snapshot"]["slots"]), ["p1a", "p1b", "p2a", "p2b"])
        self.assertEqual(v["legal"]["p1a"]["moves"][0]["move"], M)
        self.assertEqual(v["history"], 0)

    def test_turn_returns_frames_and_replays_identically(self):
        s = Session()
        s.new(config(teams={"p1": [mon("incineroar")], "p2": [mon("arcanine")]}))
        v = s.turn(both())
        self.assertEqual(len(v["frames"]), 4)  # start, two actions, end of turn
        self.assertEqual(v["history"], 1)
        s2 = Session()
        s2.new(s.config)
        self.assertEqual(hps(s2.turn(both())), hps(v), "same config and history must replay to the same state")

    def test_undo_and_restart_rebuild_from_history(self):
        s = Session()
        start = s.new(config(teams={"p1": [mon("incineroar")], "p2": [mon("arcanine")]}))
        s.turn(both())
        after_two = s.turn(both())
        self.assertEqual(after_two["history"], 2)
        undone = s.undo()
        self.assertEqual(undone["history"], 1)
        self.assertEqual(undone["snapshot"]["turn"], 1)
        again = s.turn(both())
        self.assertEqual(hps(again), hps(after_two), "redoing the undone turn gives the same damage")
        restarted = s.restart()
        self.assertEqual(restarted["history"], 0)
        self.assertEqual(hps(restarted), hps(start))

    def test_undo_with_nothing_to_undo(self):
        s = Session()
        s.new(config())
        with self.assertRaisesRegex(ValueError, "undo"):
            s.undo()

    def test_replace_after_ko_and_undo_across_it(self):
        s = Session()
        s.new(config())
        v = s.turn(both())
        self.assertEqual(v["pending"], ["p2a"])
        v = s.replace({"p2a": 1})
        self.assertEqual(v["pending"], [])
        self.assertEqual(v["snapshot"]["slots"]["p2a"]["species"], "arcanine")
        self.assertEqual(v["history"], 2)
        self.assertEqual(s.undo()["pending"], ["p2a"], "undoing the replacement restores the pending KO")
        self.assertEqual(s.undo()["snapshot"]["turn"], 0)

    def test_failed_actions_are_not_recorded(self):
        s = Session()
        s.new(config())
        for bad in ({"p1a": {"move": M, "target": "p2a"}},  # missing p2a
                    {"p1a": {"move": "swordsdance"}, "p2a": {"move": M, "target": "p1a"}},
                    {"p1a": {"move": M}, "p2a": {"move": M, "target": "p1a"}},  # no target
                    {"p1a": "mudslap", "p2a": {"move": M, "target": "p1a"}},
                    {"p1a": {"target": "p2a"}, "p2a": {"move": M, "target": "p1a"}},  # no move
                    ["p1a"], None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                s.turn(bad)
        self.assertEqual(s.view()["history"], 0)
        s.turn(both())
        with self.assertRaises(ValueError):
            s.turn(both("p1a", "p2a"))  # replacement pending
        with self.assertRaises(ValueError):
            s.replace({"p1a": 1})
        with self.assertRaises(ValueError):
            s.replace({"p2a": 5})
        self.assertEqual(s.view()["history"], 1)

    def test_bad_config(self):
        for bad in (None, {}, {"teams": {"p1": [mon("incineroar")]}},
                    config(teams={"p1": [], "p2": [mon("arcanine")]}),
                    config(teams={"p1": [mon("nosuchmon")], "p2": [mon("arcanine")]}),
                    config(teams={"p1": [mon("incineroar", ["nosuchmove"])], "p2": [mon("arcanine")]}),
                    config(teams={"p1": ["incineroar"], "p2": [mon("arcanine")]}),
                    config(active=3), config(active="x"), config(seed="x"), config(field={"bogus": 1})):
            with self.assertRaises(ValueError, msg=repr(bad)):
                Session().new(bad)

    def test_no_game_yet(self):
        s = Session()
        self.assertEqual(s.view(), {"started": False})
        for call in (lambda: s.turn(both()), lambda: s.replace({"p1a": 0}), s.undo, s.restart):
            with self.assertRaisesRegex(ValueError, "no game"):
                call()

    def test_failed_new_keeps_the_running_game(self):
        s = Session()
        s.new(config())
        s.turn(both())
        with self.assertRaises(ValueError):
            s.new({"teams": {}})
        self.assertEqual(s.view()["history"], 1)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(0)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def call(self, path, body=None, method=None, raw=None):
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        req = urllib.request.Request(self.base + path, data=data, method=method or ("POST" if data is not None else "GET"))
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def api(self, path, body=None, **kw):
        status, _, payload = self.call(path, body, **kw)
        return status, json.loads(payload)

    def test_full_game_flow(self):
        status, v = self.api("/api/new", config())
        self.assertEqual(status, 200)
        self.assertEqual(v["snapshot"]["slots"]["p1a"]["species"], "incineroar")
        status, v = self.api("/api/turn", {"actions": both()})
        self.assertEqual((status, v["pending"]), (200, ["p2a"]))
        self.assertGreaterEqual(len(v["frames"]), 3)
        status, v = self.api("/api/replace", {"replacements": {"p2a": 1}})
        self.assertEqual((status, v["snapshot"]["slots"]["p2a"]["species"]), (200, "arcanine"))
        status, v = self.api("/api/undo", {})
        self.assertEqual((status, v["pending"]), (200, ["p2a"]))
        status, v = self.api("/api/restart", {})
        self.assertEqual((status, v["history"], v["snapshot"]["turn"]), (200, 0, 0))
        status, v = self.api("/api/state")
        self.assertEqual((status, v["history"]), (200, 0))

    def test_doubles_new(self):
        teams = {"p1": [mon("incineroar"), mon("kingambit")], "p2": [mon("garchomp"), mon("arcanine")]}
        status, v = self.api("/api/new", {"teams": teams, "active": 2})
        self.assertEqual((status, sorted(v["snapshot"]["slots"])), (200, ["p1a", "p1b", "p2a", "p2b"]))

    def test_dex(self):
        status, d = self.api("/api/dex")
        self.assertEqual(status, 200)
        self.assertTrue(d["species"]["garchomp"]["moves"])
        self.assertIn("fakeout", d["moves"])
        self.assertIn("choicescarf", d["items"])
        self.assertIn("jolly", d["natures"])

    def test_bad_input_is_a_400_with_error_json(self):
        self.api("/api/new", config())
        cases = [("/api/new", None, b"{not json"), ("/api/new", None, b""), ("/api/new", None, b"[1,2]"),
                 ("/api/new", {"teams": {"p1": [mon("nosuchmon")], "p2": [mon("arcanine")]}}, None),
                 ("/api/turn", None, b"null"), ("/api/turn", {}, None), ("/api/turn", {"actions": {}}, None),
                 ("/api/turn", {"actions": {"p1a": {"move": M, "target": "p9z"}, "p2a": {"move": M, "target": "p1a"}}}, None),
                 ("/api/replace", {"replacements": {"p1a": 1}}, None), ("/api/replace", {"replacements": "x"}, None),
                 ("/api/undo", {}, None)]
        for path, body, raw in cases:
            status, payload = self.api(path, body, raw=raw)
            self.assertEqual(status, 400, (path, body, raw))
            self.assertIsInstance(payload["error"], str)
            self.assertNotIn("Traceback", payload["error"])

    def test_unsupported_move_cannot_crash_the_server(self):
        self.api("/api/new", config(teams={"p1": [mon("incineroar", ["swordsdance", M])], "p2": [mon("arcanine")]}))
        status, payload = self.api("/api/turn", {"actions": {"p1a": {"move": "swordsdance"},
                                                             "p2a": {"move": M, "target": "p1a"}}})
        self.assertEqual(status, 400)
        self.assertIn("not implemented", payload["error"])
        self.assertEqual(self.api("/api/state")[0], 200, "server still answers")

    def test_unknown_route_and_wrong_method(self):
        self.assertEqual(self.api("/api/nope")[0], 404)
        self.assertEqual(self.api("/api/nope", {})[0], 404)
        self.assertEqual(self.api("/api/dex", {})[0], 404)  # POST to a GET route

    def test_page_is_served(self):
        status, headers, body = self.call("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"<html", body.lower())


if __name__ == "__main__":
    unittest.main()
