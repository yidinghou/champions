import json
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from champions.live.server import serve

TEAM = Path(__file__).parents[1] / "teams" / "sample.json"


class LiveServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = serve(TEAM, 0)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, r.headers.get_content_type(), r.read()

    def post(self, body, raw=False):
        req = urllib.request.Request(self.base + "/api/scout", data=body if raw else json.dumps(body).encode(),
                                     method="POST")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_page_and_data(self):
        self.assertEqual(self.get("/")[:2], (200, "text/html"))
        d = json.loads(self.get("/api/dex")[2])
        self.assertIn("garchomp", d["species"])
        self.assertEqual(d["moves"]["fakeout"]["priority"], 3)
        t = json.loads(self.get("/api/team")[2])["team"]
        self.assertEqual([m["name"] for m in t][:2], ["incineroar", "rillaboom"])
        self.assertEqual(self.get("/sprites/garchomp.png")[:2], (200, "image/png"))

    def test_only_known_routes_and_sprites(self):
        for path in ("/nope", "/sprites/..%2f..%2fREADME.png", "/sprites/zzz.png", "/static/live.html"):
            with self.subTest(path), self.assertRaises(urllib.error.HTTPError) as c:
                self.get(path)
            self.assertEqual(c.exception.code, 404)

    def test_scout_a_board(self):
        code, r = self.post({"mine": [{"name": "garchomp"}], "foes": [{"name": "rillaboom"}]})
        self.assertEqual(code, 200)
        self.assertEqual({o["side"] for o in r["order"]}, {"me", "foe"})

    def test_errors_are_400_with_a_message(self):
        for body in ({"mine": []}, {"mine": [{"name": "nope"}]}):
            code, r = self.post(body)
            self.assertEqual(code, 400)
            self.assertTrue(r["error"])
        self.assertEqual(self.post(b"{not json", raw=True)[0], 400)

    def test_empty_foes_is_fine(self):
        self.assertEqual(self.post({"mine": [{"name": "garchomp"}], "foes": []})[0], 200)
