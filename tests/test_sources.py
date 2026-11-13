"""Parser checks for champions.sources, on real saved pages (tests/fixtures, no network)."""
import gzip
import unittest
from pathlib import Path

from champions.sources import common, championslab, munchstats, pikalytics

FIXTURES = Path(__file__).parent / "fixtures"


def page(name):
    return gzip.decompress((FIXTURES / f"{name}.html.gz").read_bytes()).decode("utf-8")


class SourcesTests(unittest.TestCase):
    def test_key(self):
        self.assertEqual(common.key("Mr. Rime"), common.key("mr-rime"))
        self.assertEqual(common.key("Garchomp-Mega-Z"), "garchompmegaz")

    def test_munchstats_garchomp(self):
        html = page("munchstats-garchomp")
        e = munchstats.parse(html)
        self.assertEqual(list(e["moves"].items())[:3], [("Protect", 80.9), ("Power Gem", 42.7), ("Rock Slide", 39.3)])
        self.assertEqual(list(e["items"].items())[:2], [("Garchompite Z", 51.6), ("Life Orb", 22.1)])
        self.assertEqual(e["abilities"], {"Rough Skin": 96.7, "Sand Veil": 3.3})
        self.assertEqual(list(e["spreads"].items())[:2], [("2/32/0/0/0/32", 22.4), ("2/0/0/32/0/32", 21.4)])
        self.assertEqual(list(e["natures"].items())[:2], [("Modest", 40.3), ("Jolly", 26.2)])
        self.assertEqual((e["rank"], e["as_of"]), (6, "October 06, 2026 at 12:07 UTC"))
        self.assertEqual(e["teammate_ranks"][:3], ["Rillaboom", "Incineroar", "Sneasler"])
        # internal consistency: four moves per set, one item/ability/nature each
        self.assertLessEqual(sum(e["moves"].values()), 400)
        self.assertGreater(sum(e["moves"].values()), 300)
        for f in ("items", "abilities", "natures"):
            self.assertAlmostEqual(sum(e[f].values()), 100, delta=5, msg=f)

    def test_munchstats_roster(self):
        r = munchstats.roster(page("munchstats-garchomp"))
        self.assertEqual(len(r), 260)
        self.assertEqual(list(r.items())[:3], [("Rillaboom", 1), ("Sneasler", 2), ("Incineroar", 3)])

    def test_pikalytics_garchomp(self):
        html = page("pikalytics-garchomp")
        e = pikalytics.parse(html)
        self.assertEqual(list(e["moves"].items())[:3], [("Protect", 29.158), ("Earthquake", 21.688), ("Rock Slide", 17.053)])
        self.assertEqual(list(e["teammates"].items())[:2], [("Incineroar", 38.075), ("Charizard", 34.451)])
        self.assertEqual(list(e["items"].items())[:2], [("Garchompite Z", 53.348), ("Life Orb", 33.361)])
        self.assertEqual(list(e["abilities"].items())[:2], [("Rough Skin", 92.741), ("Levitate", 3.21)])
        self.assertEqual((e["usage"], e["rank"], e["winrate"]), (21.0, 4, 49.651))
        self.assertAlmostEqual(sum(e["items"].values()), 100, delta=1)
        self.assertAlmostEqual(sum(e["abilities"].values()), 100, delta=1)
        self.assertEqual(len(pikalytics.roster(html)), 27)

    def test_championslab_meta(self):
        d = championslab.parse(page("championslab-meta"))
        self.assertEqual(len(d["usage"]), 20)
        self.assertEqual(d["usage"][0], {"rank": 1, "name": "Garchomp", "usage": 46.32, "winrate": 52.8})
        self.assertEqual(len(d["teams"]), 8)
        self.assertTrue(all(len(t["team"]) == 6 for t in d["teams"]))
        self.assertEqual(d["teams"][0]["player"], "LexiconVGC")

    def test_championslab_empty_page(self):
        d = championslab.parse("<html></html>")
        self.assertEqual((d["usage"], d["teams"]), ([], []))


if __name__ == "__main__":
    unittest.main()
