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
