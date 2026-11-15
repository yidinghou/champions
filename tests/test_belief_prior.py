import unittest
from datetime import datetime, timezone

from champions.belief import load_priors, reference as R
from champions.belief import factors as F
from champions.belief.names import NameIndex
from champions.belief.prior import build_prior
from champions.stats import MAX_SP_PER_STAT, MAX_SP_TOTAL

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)

GARCHOMP = {
    "moves": {"Earthquake": 90, "Dragon Claw": 80, "Rock Slide": 70, "Protect": 60, "Stone Edge": 40, "Power Gem": 30},
    "items": {"Life Orb": 50, "Choice Scarf": 30, "Garchompite Z": 20},
    "abilities": {"Rough Skin": 60, "Sand Veil": 40},
    "natures": {"Jolly": 60, "Adamant": 40},
    "spreads": {"0/32/0/0/2/32": 70, "0/0/0/32/2/32": 20, "99/99/0/0/0/0": 10},
    "as_of": "November 10, 2026 at 12:00 UTC",
}


def snapshot(pokemon, as_of_free=False, fetched="2026-11-14T00:00:00+00:00"):
    if as_of_free:
        for e in pokemon.values():
            e.pop("as_of", None)
    return {"source": "x", "format": "doubles", "fetched_at": fetched, "pokemon": pokemon}


def loader_for(**snaps):
    return lambda site, fmt: snaps.get(f"{site}-{fmt}")


class Names(unittest.TestCase):
    def setUp(self):
        self.n = NameIndex()

    def test_forms_and_aliases(self):
        self.assertEqual(self.n.resolve("ninetalesalola"), "ninetales-alola")
        self.assertEqual(self.n.resolve("Mr. Rime"), "mr-rime")
        self.assertEqual(self.n.resolve("garchompmegaz"), "garchomp-mega-z")
        self.assertEqual(self.n.resolve("mimikyu"), "mimikyu-disguised")          # base name -> default form
        self.assertEqual(self.n.resolve("indeedeef"), "indeedee-female")
        self.assertEqual(self.n.resolve("taurospaldeablaze"), "tauros-paldea-blaze-breed")

    def test_unknown_and_suggest(self):
        self.assertIsNone(self.n.resolve("notapokemon"))
        self.assertIn("garchomp", self.n.suggest("garchomq"))

    def test_every_munchstats_name_resolves(self):
        from champions.sources import common
        snap = common.load("munchstats", "doubles")
        self.assertEqual([k for k in snap["pokemon"] if self.n.resolve(k) is None], [])


class Reference(unittest.TestCase):
    def test_mega_forms(self):
        self.assertEqual(R.mega_form_for("garchomp", "Garchompite Z"), "garchomp-mega-z")
        self.assertEqual(R.mega_form_for("charizard", "charizarditex"), "charizard-mega-x")
        self.assertEqual(R.mega_form_for("charizard", "charizarditey"), "charizard-mega-y")
        self.assertIsNone(R.mega_form_for("garchomp", "lifeorb"))

    def test_legality(self):
        self.assertIn("roughskin", R.legal_abilities("garchomp"))
        self.assertNotIn("intimidate", R.legal_abilities("garchomp"))
        self.assertTrue(R.can_learn("garchomp", "Earthquake"))
        self.assertFalse(R.can_learn("garchomp", "moonblast"))


class BuildPrior(unittest.TestCase):
    def setUp(self):
        self.p = build_prior("garchomp", dict(GARCHOMP), "munchstats")

    def test_factors_are_distributions(self):
        for f in (self.p.moves, self.p.ia, self.p.ns):
            self.assertAlmostEqual(sum(f.values()), 1.0, places=9)

    def test_move_marginals_follow_usage_order(self):
        inc = F.inclusion_of(self.p.moves)
        self.assertAlmostEqual(sum(inc.values()), 4.0, places=6)
        order = sorted(inc, key=lambda m: -inc[m])
        self.assertEqual(order[:3], ["earthquake", "dragonclaw", "rockslide"])

    def test_tails(self):
        self.assertAlmostEqual(self.p.tails["moves"], (400 - 370) / 400)
        self.assertAlmostEqual(self.p.tails["spreads"], 0.0)          # listed 100, but one entry is invalid -> renormalized
        self.assertAlmostEqual(self.p.tails["items"], 0.0)

    def test_invalid_spread_dropped_and_noted(self):
        spreads = {s for _, s in self.p.ns}
        self.assertNotIn("99/99/0/0/0/0", spreads)
        self.assertTrue(any("spread" in n for n in self.p.notes))
        for s in spreads:
            v = [int(x) for x in s.split("/")]
            self.assertLessEqual(sum(v), MAX_SP_TOTAL)
            self.assertLessEqual(max(v), MAX_SP_PER_STAT)

    def test_mega_stone_forces_mega_ability(self):
        mega = [k for k in self.p.ia if k[0] == "garchompitez"]
        self.assertEqual(mega, [("garchompitez", "levitate", "garchomp-mega-z")])
        self.assertAlmostEqual(self.p.ia[mega[0]], 0.2)
        self.assertTrue(all(a in ("roughskin", "sandveil") for (i, a, m) in self.p.ia if m is None))

    def test_illegal_ability_dropped(self):
        e = dict(GARCHOMP, abilities={"Rough Skin": 60, "Intimidate": 40})
        p = build_prior("garchomp", e, "munchstats")
        self.assertEqual({a for (_, a, m) in p.ia if m is None}, {"roughskin"})
        self.assertTrue(any("ability" in n for n in p.notes))

    def test_defaults_are_flagged(self):
        e = {"moves": GARCHOMP["moves"]}
        p = build_prior("garchomp", e, "pikalytics")
        self.assertEqual(set(p.defaulted), {"ability", "item", "nature", "spread"})
        self.assertNotIn("moves", p.tails)                             # pikalytics scale gives no tail
        self.assertEqual(list(p.ns), [("hardy", "0/0/0/0/0/0")])

    def test_no_moves_gives_none(self):
        self.assertIsNone(build_prior("garchomp", {"items": {"Life Orb": 100}}, "munchstats"))

    def test_few_moves_single_set(self):
        p = build_prior("garchomp", {"moves": {"Earthquake": 90, "Protect": 80}}, "munchstats")
        self.assertEqual(list(p.moves), [("earthquake", "protect")])


class LoadPriors(unittest.TestCase):
    def book(self, primary, fallback=None, **kw):
        return load_priors("munchstats-doubles", "pikalytics-doubles" if fallback is not None else None,
                           loader=loader_for(**{"munchstats-doubles": primary, "pikalytics-doubles": fallback}),
                           now=NOW, **kw)

    def test_fresh_data_has_no_warning(self):
        b = self.book(snapshot({"garchomp": dict(GARCHOMP)}))
        self.assertEqual(b.warnings, [])
        self.assertIsNotNone(b.get("Garchomp"))

    def test_stale_data_warns(self):
        e = dict(GARCHOMP, as_of="October 06, 2026 at 12:07 UTC")
        b = self.book(snapshot({"garchomp": e}))
        self.assertTrue(any("days old" in w for w in b.warnings))

    def test_falls_back_to_fetch_date_then_warns_when_undated(self):
        b = self.book(snapshot({"garchomp": dict(GARCHOMP)}, as_of_free=True, fetched="2026-08-01T00:00:00+00:00"))
        self.assertTrue(any("fetch date" in w and "days old" in w for w in b.warnings))
        b = self.book(snapshot({"garchomp": dict(GARCHOMP)}, as_of_free=True, fetched=None))
        self.assertTrue(any("no usable date" in w for w in b.warnings))

    def test_naive_fetch_timestamp_is_read_as_utc(self):
        b = self.book(snapshot({"garchomp": dict(GARCHOMP)}, as_of_free=True, fetched="2026-08-01T12:00:00"))
        self.assertTrue(any("fetch date" in w and "days old" in w for w in b.warnings))

    def test_future_date_warns(self):
        e = dict(GARCHOMP, as_of="December 25, 2026 at 12:00 UTC")
        self.assertTrue(any("future" in w for w in self.book(snapshot({"garchomp": e})).warnings))

    def test_missing_snapshot_warns(self):
        b = load_priors(loader=lambda *a: None, now=NOW)
        self.assertEqual(b.species(), [])
        self.assertTrue(any("no snapshot" in w for w in b.warnings))

    def test_fallback_only_fills_missing_species_and_skips_megas(self):
        prim = snapshot({"garchomp": dict(GARCHOMP)})
        fb = snapshot({"garchomp": {"moves": {"Earthquake": 10, "Protect": 20, "Rock Slide": 5, "Stone Edge": 5, "Dragon Claw": 5}},
                       "rotom": {"moves": {"Thunderbolt": 50, "Protect": 40, "Shadow Ball": 30, "Volt Switch": 20, "Will-O-Wisp": 10}},
                       "garchompmegaz": {"moves": {"Earthquake": 90, "Protect": 90, "Rock Slide": 5, "Stone Edge": 5, "Dragon Claw": 5}},
                       "notapokemon": {"moves": {"Protect": 5}}})
        b = self.book(prim, fb)
        self.assertEqual(b.get("garchomp").source, "munchstats")           # primary wins
        self.assertEqual(b.get("rotom").source, "pikalytics")
        self.assertIn("nature", b.get("rotom").defaulted)
        self.assertIsNone(b.get("garchomp-mega-z"))                        # fallback Mega keys skipped
        self.assertTrue(any("used for 1 species" in w for w in b.warnings))
        self.assertTrue(any("did not resolve" in w and "notapokemon" in w for w in b.warnings))

    def test_name_only_entries_skipped(self):
        b = self.book(snapshot({"garchomp": dict(GARCHOMP), "incineroar": {"name": "Incineroar"}}))
        self.assertEqual(b.species(), ["garchomp"])


class CommittedSnapshot(unittest.TestCase):
    """Structural checks on the real MunchStats data. Nothing here depends on exact numbers or freshness."""

    @classmethod
    def setUpClass(cls):
        cls.book = load_priors(now=NOW)

    def test_every_prior_builds_and_is_a_distribution(self):
        self.assertGreater(len(self.book.species()), 200)
        for s in self.book.species():
            p = self.book.get(s)
            self.assertIsNotNone(p, s)
            for f in (p.moves, p.ia, p.ns):
                self.assertAlmostEqual(sum(f.values()), 1.0, places=6, msg=s)
            for _, spread in p.ns:
                v = [int(x) for x in spread.split("/")]
                self.assertTrue(len(v) == 6 and sum(v) <= MAX_SP_TOTAL and max(v) <= MAX_SP_PER_STAT, (s, spread))
            for t in p.tails.values():
                self.assertTrue(-1e-9 <= t <= 1 + 1e-9, (s, p.tails))

    def test_garchomp_looks_right(self):
        p = self.book.get("garchomp")
        inc = F.inclusion_of(p.moves)
        self.assertGreater(inc["protect"], 0.8)
        mega = sum(w for (i, a, m), w in p.ia.items() if m)
        self.assertGreater(mega, 0.4)


if __name__ == "__main__":
    unittest.main()
