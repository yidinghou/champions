import json
import unittest
from pathlib import Path

from champions.live import scout

TEAM = json.loads((Path(__file__).parents[1] / "teams" / "sample.json").read_text())


def run(**kw):
    kw.setdefault("mine", [{"name": "incineroar"}, {"name": "garchomp"}])
    kw.setdefault("foes", [{"name": "rillaboom"}, {"name": "pelipper"}])
    return scout.scout(kw, TEAM)


def order(r):
    return [o["name"] for o in r["order"]]


class Speed(unittest.TestCase):
    def test_fastest_first(self):
        r = run(foes=[{"name": "rillaboom"}], mine=[{"name": "garchomp"}, {"name": "incineroar"}])
        self.assertEqual(order(r), ["garchomp", "rillaboom", "incineroar"])

    def test_trick_room_reverses(self):
        self.assertEqual(order(run(trick_room=True))[0], order(run())[-1])

    def test_tailwind_doubles_a_side(self):
        r = run(mine=[{"name": "incineroar"}], foes=[{"name": "rillaboom"}], tailwind=["me"])
        base = run(mine=[{"name": "incineroar"}], foes=[{"name": "rillaboom"}])
        mine = lambda x: next(o["now"] for o in x["order"] if o["side"] == "me")
        self.assertEqual(mine(r), 2 * mine(base))

    def test_paralysis_and_stages(self):
        base = run()["order"]
        par = run(mine=[{"name": "garchomp", "status": "par"}, {"name": "incineroar"}])["order"]
        g = lambda o: next(x["now"] for x in o if x["name"] == "garchomp")
        self.assertEqual(g(par), g(base) // 2)
        up = run(mine=[{"name": "garchomp", "boosts": {"spe": 1}}, {"name": "incineroar"}])["order"]
        self.assertEqual(g(up), g(base) * 3 // 2)

    def test_foe_speed_is_a_range(self):
        o = next(x for x in run()["order"] if x["name"] == "pelipper")
        self.assertLess(o["lo"], o["hi"])

    def test_weather_from_the_setter(self):
        self.assertEqual(run()["weather"], "rain")                  # Pelipper's usual ability is Drizzle
        self.assertIsNone(run(weather="none")["weather"])


class Calc(unittest.TestCase):
    def test_range_is_ordered_and_names_the_ko(self):
        r = run()
        c = next(x for x in r["calc"] if x["move"] == "earthquake" and x["target"]["name"] == "rillaboom")
        self.assertLess(c["lo"], c["hi"])

    def test_low_hp_target_is_ohko(self):
        r = run(foes=[{"name": "rillaboom", "hp": 0.05}])
        c = next(x for x in r["calc"] if x["move"] == "earthquake")
        self.assertEqual((c["ko"], c["chance"]), ("OHKO", "sure"))

    def test_watch_out_lists_only_foe_attacks(self):
        self.assertTrue(run()["threats"])
        self.assertTrue(all(t["foe"]["side"] == "foe" for t in run()["threats"]))


class Errors(unittest.TestCase):
    def test_bad_boards(self):
        for kw in ({"mine": []}, {"mine": [{"name": "mew"}]}, {"foes": [{"name": "nope"}]},
                   {"mine": [{"name": "garchomp", "hp": 2}]}, {"mine": [{"name": "garchomp", "status": "x"}]},
                   {"mine": [{"name": "garchomp", "boosts": {"spe": 9}}]}, {"weather": "fog"}):
            with self.subTest(kw), self.assertRaises(scout.BadBoard):
                run(**kw)

    def test_seen_moves_are_pinned(self):
        r = run(foes=[{"name": "pelipper", "seen": ["tailwind"]}])
        card = next(c for c in r["board"] if c["name"] == "pelipper")
        self.assertEqual(card["moves"][0]["id"], "tailwind")


class MoveFlow(unittest.TestCase):
    def test_certain_effects_are_auto_and_chances_are_asked(self):
        from champions.live.moveflow import flow
        self.assertEqual(flow("sleeppowder")["auto"], [{"kind": "status", "status": "slp"}])
        self.assertEqual(flow("sleeppowder")["acc"], 75)
        self.assertEqual(flow("fakeout")["auto"], [{"kind": "flinch"}])
        self.assertEqual(flow("icebeam")["ask"], [{"chance": 10, "kind": "status", "status": "frz"}])
        self.assertEqual(flow("rockslide")["ask"], [{"chance": 30, "kind": "flinch"}])
        self.assertEqual(flow("swordsdance")["auto"], [{"kind": "stat", "who": "user", "stats": {"atk": 2}}])
        self.assertEqual(flow("closecombat")["auto"], [{"kind": "stat", "who": "user", "stats": {"def": -1, "spd": -1}}])
        self.assertTrue(flow("uturn")["pivot"] and flow("partingshot")["pivot"])
        self.assertEqual(flow("woodhammer")["recoil"], [33, 100])
        self.assertEqual(flow("trickroom")["auto"], [{"kind": "field", "what": "trick_room"}])
        self.assertEqual((flow("earthquake")["target"], flow("rockslide")["target"], flow("protect")["target"]),
                         ("all", "foes", "none"))

    def test_every_move_parses(self):
        from champions.engine import teams
        from champions.live.moveflow import flow
        for mid in teams.moves_data():
            self.assertIn(flow(mid)["target"], ("one", "foes", "all", "none"))


class Forms(unittest.TestCase):
    def test_gendered_and_form_names_find_their_usage(self):
        for name in ("basculegion-male", "basculegion-female", "aegislash-shield", "meowstic-male"):
            self.assertTrue(scout.usage_moves(name), name)
        self.assertIn("wavecrash", [m["id"] for m in scout.usage_moves("basculegion-male")])

    def test_the_dex_learnset_follows_the_form_name(self):
        from champions.live.server import dex
        self.assertIn("wavecrash", dex()["species"]["basculegion-male"]["learnset"])
