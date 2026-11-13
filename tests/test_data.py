"""Is the committed data right? Known facts plus cross-file consistency (no network)."""
import json
import re
import unittest
from pathlib import Path

from champions import stats
from champions.sources import common

DATA = Path(__file__).parent.parent / "src" / "champions" / "data"


def load(name, key):
    return json.loads((DATA / f"{name}.json").read_text())[key]


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


POKEMON = {p["name"]: p for p in load("champions", "pokemon")}
MOVES = load("moves", "moves")
CHART = load("types", "chart")
LEARNSETS = load("learnsets", "learnsets")
ABILITIES = load("abilities", "abilities")


class KnownFacts(unittest.TestCase):
    def test_garchomp(self):
        g = POKEMON["garchomp"]
        self.assertEqual(g["types"], ["dragon", "ground"])
        self.assertEqual(g["stats"], {"hp": 108, "attack": 130, "defense": 95, "special-attack": 80,
                                      "special-defense": 85, "speed": 102})
        self.assertIn("rough-skin", g["abilities"])

    def test_megas_are_flagged(self):
        self.assertTrue(POKEMON["garchomp-mega"]["is_mega"])
        self.assertFalse(POKEMON["garchomp"]["is_mega"])

    def test_earthquake(self):
        m = MOVES["earthquake"]
        self.assertEqual((m["type"], m["category"], m["base_power"], m["accuracy"]), ("Ground", "Physical", 100, 100))

    def test_type_chart(self):
        self.assertEqual(len(CHART), 18)
        # attacker -> defender
        for atk, dfn, mult in [("Fire", "Grass", 2), ("Water", "Fire", 2), ("Fire", "Water", 0.5),
                               ("Normal", "Ghost", 0), ("Electric", "Ground", 0), ("Ground", "Flying", 0),
                               ("Dragon", "Fairy", 0), ("Fairy", "Dragon", 2), ("Normal", "Normal", 1)]:
            self.assertEqual(CHART[atk][dfn], mult, f"{atk} -> {dfn}")

    def test_level50_stats(self):
        # Garchomp at level 50, 31 IV, no Stat Points, neutral nature: 183/150/115/100/105/122
        base = POKEMON["garchomp"]["stats"]
        self.assertEqual(list(stats.level50(base).values()), [183, 150, 115, 100, 105, 122])
        # Jolly (+Spe, -SpA)
        self.assertEqual(stats.level50(base, "jolly")["speed"], 134)
        self.assertEqual(stats.level50(base, "jolly")["special-attack"], 90)
        # Stat Points add 1:1 on top, and the limits are enforced
        self.assertEqual(stats.level50(base, sp={"attack": 32})["attack"], 182)
        with self.assertRaises(ValueError):
            stats.level50(base, sp={"attack": 33})
        with self.assertRaises(ValueError):
            stats.level50(base, "silly")


class Consistency(unittest.TestCase):
    def test_every_type_is_in_the_chart(self):
        used = {t.capitalize() for p in POKEMON.values() for t in p["types"]}
        self.assertLessEqual(used, set(CHART))

    def test_every_pokemon_has_a_learnset(self):
        self.assertEqual(set(LEARNSETS), set(POKEMON))

    def test_every_learnset_move_exists(self):
        known = {norm(k) for k in MOVES}
        missing = {(mon, mv) for mon, mvs in LEARNSETS.items() for mv in mvs if norm(mv) not in known}
        self.assertEqual(missing, set())

    def test_every_ability_exists(self):
        known = {norm(k) for k in ABILITIES}
        missing = {(n, a) for n, p in POKEMON.items() for a in p["abilities"] if norm(a) not in known}
        self.assertEqual(missing, set())

    def test_base_stats_are_sane(self):
        for n, p in POKEMON.items():
            self.assertEqual(len(p["stats"]), 6, n)
            self.assertTrue(all(1 <= v <= 255 for v in p["stats"].values()), n)

    def test_snapshots_have_the_expected_shape(self):
        for src, fmt in [("munchstats", "doubles"), ("pikalytics", "doubles"), ("championslab", "doubles"), ("opgg", "singles")]:
            snap = common.load(src, fmt)
            self.assertTrue(snap and snap["pokemon"], f"{src}-{fmt} missing or empty")
            for k in ("source", "format", "url", "fetched_at"):
                self.assertIn(k, snap)


if __name__ == "__main__":
    unittest.main()
