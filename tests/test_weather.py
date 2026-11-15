"""Unit tests for weather and terrain: the damage maths, accuracy, healing and state handling that the
catalogue cases (data/mechanics.json: weather, terrain) only pin indirectly."""
import unittest

from champions.calc.damage import damage
from champions.calc.field import is_grounded, modify
from champions.engine import arena, game
from champions.engine.actions import Move
from champions.engine.effects_table import is_supported_ability, is_supported_move
from champions.engine.pipeline import accuracy
from champions.engine.resolve import resolve
from champions.engine.rng import LabeledRng
from champions.engine.teams import build_mon, moves_data


def mon(species, ability="noability", moves=(), **kw):
    return build_mon({"species": species, "ability": ability, "moves": list(moves), **kw})


def dmg(attacker, defender, move_id, **kw):
    return damage(attacker, defender, moves_data()[move_id], crit=False, roll=100, spread=False, **kw)


def by_hand(bp, a, d, *steps):
    """Showdown's order at level 50 with roll 100, applying (kind, value) steps after the base damage."""
    x = 22 * bp * a // d // 50 + 2
    for kind, v in steps:
        x = {"weather": lambda x: modify(x, v), "stab": lambda x: x * 3 // 2}[kind](x)
    return x


class WeatherDamage(unittest.TestCase):
    def setUp(self):
        self.fire = mon("charizard", "blaze", ["flamethrower"])       # Fire/Flying, STAB on Flamethrower
        self.target = mon("snorlax", "thickfat")

    def test_sun_boosts_fire_and_rain_halves_it(self):
        a, d, bp = self.fire.stats["spa"], self.target.stats["spd"], moves_data()["flamethrower"]["base_power"]
        self.assertEqual(dmg(self.fire, self.target, "flamethrower", weather="sun"), by_hand(bp, a, d, ("weather", 6144), ("stab", 0)))
        self.assertEqual(dmg(self.fire, self.target, "flamethrower", weather="rain"), by_hand(bp, a, d, ("weather", 2048), ("stab", 0)))
        self.assertEqual(dmg(self.fire, self.target, "flamethrower"), by_hand(bp, a, d, ("stab", 0)))

    def test_rain_boosts_water_and_sun_halves_it(self):
        w = mon("vaporeon", "waterabsorb", ["surf"])
        a, d, bp = w.stats["spa"], self.target.stats["spd"], moves_data()["surf"]["base_power"]
        self.assertEqual(dmg(w, self.target, "surf", weather="rain"), by_hand(bp, a, d, ("weather", 6144), ("stab", 0)))
        self.assertEqual(dmg(w, self.target, "surf", weather="sun"), by_hand(bp, a, d, ("weather", 2048), ("stab", 0)))

    def test_other_types_ignore_sun_and_rain(self):
        m = mon("clefable", "unaware", ["shadowball"])
        base = dmg(m, self.target, "shadowball")
        self.assertEqual(dmg(m, self.target, "shadowball", weather="sun"), base)
        self.assertEqual(dmg(m, self.target, "shadowball", weather="rain"), base)

    def test_sand_raises_rock_special_defense_only(self):
        rock = mon("tyranitar", "noability")
        m = mon("clefable", "unaware", ["thunderbolt", "bodyslam"])     # neutral into Rock/Dark, no STAB
        d = rock.stats["spd"]
        bp = moves_data()["thunderbolt"]["base_power"]
        self.assertEqual(dmg(m, rock, "thunderbolt", weather="sand"), by_hand(bp, m.stats["spa"], d * 3 // 2))
        self.assertEqual(dmg(m, rock, "bodyslam", weather="sand"), dmg(m, rock, "bodyslam"))     # Defense unchanged
        self.assertEqual(dmg(m, self.target, "thunderbolt", weather="sand"), dmg(m, self.target, "thunderbolt"))   # not Rock

    def test_snow_raises_ice_defense_only(self):
        ice = mon("glaceon", "noability")
        m = mon("snorlax", "thickfat", ["bodyslam", "shadowball"])
        bp = moves_data()["bodyslam"]["base_power"]
        self.assertEqual(dmg(m, ice, "bodyslam", weather="snow"),
                         by_hand(bp, m.stats["atk"], ice.stats["def"] * 3 // 2, ("stab", 0)))
        self.assertEqual(dmg(m, ice, "shadowball", weather="snow"), dmg(m, ice, "shadowball"))

    def test_sand_force_boosts_rock_ground_steel_in_sand_only(self):
        a = mon("excadrill", "sandforce", ["earthquake", "ironhead"])
        d = mon("snorlax", "thickfat")
        self.assertGreater(dmg(a, d, "earthquake", weather="sand"), dmg(a, d, "earthquake"))
        self.assertGreater(dmg(a, d, "ironhead", weather="sand"), dmg(a, d, "ironhead"))
        self.assertEqual(dmg(a, d, "earthquake", weather="rain"), dmg(a, d, "earthquake"))
        b = mon("excadrill", "noability", ["earthquake"])
        self.assertEqual(dmg(b, d, "earthquake", weather="sand"), dmg(b, d, "earthquake"))


class TerrainDamage(unittest.TestCase):
    def test_terrain_boost_is_on_base_power_and_needs_a_grounded_attacker(self):
        a = mon("pikachu", "static", ["thunderbolt"])
        d = mon("snorlax", "thickfat")
        bp = moves_data()["thunderbolt"]["base_power"]
        boosted = modify(bp, 5325)
        self.assertEqual(boosted, 117)
        self.assertEqual(dmg(a, d, "thunderbolt", terrain="electric"),
                         by_hand(boosted, a.stats["spa"], d.stats["spd"], ("stab", 0)))
        self.assertEqual(dmg(a, d, "thunderbolt", terrain="grassy"), dmg(a, d, "thunderbolt"))   # wrong terrain
        flier = mon("rotom-wash", "levitate", ["thunderbolt"])                                   # Levitate: not grounded
        self.assertEqual(dmg(flier, d, "thunderbolt", terrain="electric"), dmg(flier, d, "thunderbolt"))

    def test_each_terrain_boosts_its_own_type(self):
        d = mon("snorlax", "thickfat")
        for terrain, species, move in [("grassy", "venusaur", "gigadrain"), ("psychic", "alakazam", "psychic")]:
            if move not in moves_data():
                continue
            a = mon(species, "noability", [move])
            self.assertGreater(dmg(a, d, move, terrain=terrain), dmg(a, d, move), (terrain, move))

    def test_misty_halves_dragon_into_grounded_only(self):
        a = mon("dragonite", "innerfocus", ["dragonclaw"])
        ground, flier = mon("snorlax", "thickfat"), mon("corviknight", "noability")
        self.assertLess(dmg(a, ground, "dragonclaw", terrain="misty"), dmg(a, ground, "dragonclaw"))
        self.assertEqual(dmg(a, flier, "dragonclaw", terrain="misty"), dmg(a, flier, "dragonclaw"))

    def test_grassy_halves_earthquake_into_grounded_only(self):
        a = mon("garchomp", "noability", ["earthquake"])
        ground, flier = mon("snorlax", "thickfat"), mon("corviknight", "noability")
        self.assertLess(dmg(a, ground, "earthquake", terrain="grassy"), dmg(a, ground, "earthquake"))
        self.assertEqual(dmg(a, flier, "earthquake", terrain="grassy"), dmg(a, flier, "earthquake"))

    def test_grounded(self):
        self.assertTrue(is_grounded(mon("snorlax", "thickfat")))
        self.assertFalse(is_grounded(mon("corviknight", "noability")))
        self.assertFalse(is_grounded(mon("hydreigon", "levitate")))


class Accuracy(unittest.TestCase):
    def test_sand_veil_and_snow_cloak_cut_accuracy_in_their_weather(self):
        a = mon("clefable", "unaware")
        veil, cloak = mon("garchomp", "sandveil"), mon("glaceon", "snowcloak")
        self.assertEqual(accuracy.final_accuracy(a, veil, 100, "sand"), 80)
        self.assertEqual(accuracy.final_accuracy(a, veil, 70, "sand"), 56)
        self.assertEqual(accuracy.final_accuracy(a, veil, 100, "snow"), 100)
        self.assertEqual(accuracy.final_accuracy(a, veil, 100, None), 100)
        self.assertEqual(accuracy.final_accuracy(a, cloak, 100, "snow"), 80)
        self.assertEqual(accuracy.final_accuracy(a, cloak, 100, "sand"), 100)


class Healing(unittest.TestCase):
    def test_heal_fractions_follow_showdown_rounding(self):
        self.assertEqual(arena.heal_amount(200, None), 100)
        self.assertEqual(arena.heal_amount(200, "sun"), 133)
        self.assertEqual(arena.heal_amount(205, "sun"), 137)     # 0.667 through 4096ths, not 2/3 floored (136)
        self.assertEqual(arena.heal_amount(200, "rain"), 50)
        self.assertEqual(arena.heal_amount(135, "sand"), 34)     # 1/4 rounds up when max HP % 4 == 3
        self.assertEqual(arena.heal_amount(135, "snow"), 34)


class Support(unittest.TestCase):
    def test_new_moves_and_abilities_are_supported(self):
        for m in ("sunnyday", "raindance", "sandstorm", "snowscape", "electricterrain", "grassyterrain", "mistyterrain",
                  "psychicterrain", "weatherball", "thunder", "hurricane", "blizzard", "moonlight", "synthesis", "morningsun"):
            self.assertTrue(is_supported_move(m), m)
        for a in ("drizzle", "drought", "sandstream", "snowwarning", "electricsurge", "grassysurge", "mistysurge",
                  "psychicsurge", "swiftswim", "chlorophyll", "sandrush", "slushrush", "surgesurfer", "sandforce",
                  "sandveil", "snowcloak", "overcoat", "raindish", "icebody"):
            self.assertTrue(is_supported_ability(a), a)

    def test_solar_beam_is_still_rejected_until_the_charge_turn_exists(self):
        self.assertFalse(is_supported_move("solarbeam"))


def start(p1, p2, **kw):
    return game.start([p1, p2], seed=1, format="singles", rng=LabeledRng(kw.get("rolls")))


class State(unittest.TestCase):
    def spec(self, species, ability, moves, **kw):
        return {"species": species, "ability": ability, "moves": moves, **kw}

    def test_clone_does_not_share_the_arena(self):
        b = start([self.spec("pelipper", "drizzle", ["protect"])], [self.spec("snorlax", "thickfat", ["protect"])])
        c = b.clone()
        c.arena["weather"] = "sun"
        self.assertEqual(b.arena["weather"], "rain")

    def test_outcomes_with_different_weather_are_not_merged(self):
        """state_key must see weather and terrain, or resolve() would merge two different futures."""
        b = start([self.spec("clefable", "unaware", ["sunnyday"])], [self.spec("snorlax", "thickfat", ["protect"])])
        out = resolve(b, [Move(0, 0, "sunnyday", None)])
        self.assertEqual([c.arena["weather"] for _, c in out], ["sun"])
        other = start([self.spec("clefable", "unaware", ["sunnyday"])], [self.spec("snorlax", "thickfat", ["protect"])])
        other.arena.update(weather="rain", weather_turns=5)
        k1 = __import__("champions.engine.resolve", fromlist=["state_key"]).state_key(out[0][1])
        k2 = __import__("champions.engine.resolve", fromlist=["state_key"]).state_key(other)
        self.assertNotEqual(k1, k2)

    def test_snapshot_round_trip_keeps_weather_and_terrain(self):
        from champions.engine import replay
        b = start([self.spec("pelipper", "drizzle", ["protect"])], [self.spec("rillaboom", "grassysurge", ["protect"])])
        r = replay.restore(replay.snapshot(b))
        self.assertEqual((r.arena["weather"], r.arena["terrain"]), ("rain", "grassy"))

    def test_weather_survives_a_switch_and_ends_on_schedule(self):
        b = start([self.spec("pelipper", "drizzle", ["protect"])], [self.spec("snorlax", "thickfat", ["protect"])])
        left = []
        for _ in range(5):
            game.play_turn(b, [Move(0, 0, "protect", None)])
            left.append(b.arena.get("weather_turns"))
            b.sides[0].team[0].volatiles.clear()          # keep Protect's chain from failing it
        self.assertEqual(left, [4, 3, 2, 1, None])
        self.assertNotIn("weather", b.arena)

    def test_fainting_mon_does_not_take_a_second_hit_from_the_residual(self):
        b = start([self.spec("snorlax", "thickfat", ["protect"], hp=1, status="brn")],
                  [self.spec("clefable", "unaware", ["protect"])])
        b.arena.update(weather="sand", weather_turns=3)
        game.play_turn(b, [Move(1, 0, "protect", None)])
        self.assertEqual(len(b.events("faint", mon="p1:snorlax")), 1)
        self.assertEqual(len(b.events("damage", mon="p1:snorlax")), 1)


if __name__ == "__main__":
    unittest.main()
