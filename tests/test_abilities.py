"""Numbers for the Mega-form abilities that the catalogue cases do not count."""
import unittest

from champions.calc import abilities as cab
from champions.calc.damage import damage
from champions.calc.field import modify
from champions.engine import arena, game
from champions.engine.actions import Move
from champions.engine.rng import LabeledRng
from champions.engine.teams import build_mon, moves_data


def mon(species, ability="noability", moves=(), **kw):
    return build_mon({"species": species, "ability": ability, "moves": list(moves), **kw})


def dmg(a, d, move_id, move=None, **kw):
    kw.setdefault("crit", False)
    return damage(a, d, move or moves_data()[move_id], roll=100, spread=False, **kw)


class Numbers(unittest.TestCase):
    def setUp(self):
        self.d = mon("snorlax", "noability")

    def test_sheer_force_boost_needs_the_mark(self):
        move = moves_data()["flamethrower"]
        a = mon("clefable", "sheerforce", ["flamethrower"])
        self.assertEqual(cab.base_power_mod(a, move), 4096)
        self.assertEqual(cab.base_power_mod(a, {**move, "sheer": True}), 5325)
        self.assertGreater(dmg(a, self.d, "flamethrower", {**move, "sheer": True}), dmg(a, self.d, "flamethrower"))

    def test_parental_bond_second_hit_is_a_quarter_power(self):
        a = mon("clefable", "parentalbond", ["bodyslam"])
        full, second = dmg(a, self.d, "bodyslam"), dmg(a, self.d, "bodyslam", hit_mod=1024)
        self.assertLess(second, full // 3)
        self.assertGreater(second, 0)

    def test_fire_mane_and_fairy_aura(self):
        a = mon("clefable", "firemane", ["flamethrower"])
        self.assertEqual(cab.base_power_mod(a, moves_data()["flamethrower"]), 6144)
        self.assertEqual(cab.base_power_mod(a, moves_data()["bodyslam"]), 4096)
        plain = mon("clefable", "noability", ["bodyslam"])
        fairy = {**moves_data()["bodyslam"], "type": "Fairy"}
        self.assertEqual(cab.base_power_mod(plain, fairy, fairy_aura=True), 5448)
        self.assertGreater(dmg(plain, self.d, "bodyslam", fairy, fairy_aura=True), dmg(plain, self.d, "bodyslam", fairy))
        self.assertEqual(cab.base_power_mod(plain, moves_data()["bodyslam"], fairy_aura=True), 4096)

    def test_aura_guard_halves_contact_only(self):
        a = mon("clefable", "noability", ["bodyslam", "flamethrower"])
        guard = mon("snorlax", "auraguard")
        self.assertEqual(dmg(a, guard, "bodyslam"), modify(dmg(a, self.d, "bodyslam"), 2048))
        self.assertEqual(dmg(a, guard, "flamethrower"), dmg(a, self.d, "flamethrower"))

    def test_mold_breaker_ignores_damage_abilities(self):
        mb = mon("gyarados", "moldbreaker", ["flamethrower"])
        plain = mon("gyarados", "noability", ["flamethrower"])
        for ab in ("thickfat", "multiscale", "filter"):
            target_with, target_without = mon("rillaboom", ab), mon("rillaboom", "noability")
            self.assertEqual(dmg(mb, target_with, "flamethrower"), dmg(mb, target_without, "flamethrower"), ab)
        self.assertLess(dmg(plain, mon("snorlax", "thickfat"), "flamethrower"), dmg(plain, self.d, "flamethrower"))
        self.assertFalse(cab.breaks(plain, mon("snorlax", "thickfat")))
        self.assertTrue(cab.breaks(mb, mon("snorlax", "thickfat")))
        self.assertFalse(cab.breaks(mb, mon("snorlax", "magicguard")))


def start(p1, p2):
    return game.start([p1, p2], seed=1, format="singles", rng=LabeledRng())


def spec(species, ability, moves, **kw):
    return {"species": species, "ability": ability, "moves": moves, **kw}


class InBattle(unittest.TestCase):
    def test_parental_bond_second_hit_does_less_in_a_real_battle(self):
        b = start([spec("clefable", "parentalbond", ["bodyslam"])], [spec("snorlax", "noability", ["protect"])])
        game.play_turn(b, [Move(0, 0, "bodyslam", (1, 0))])
        first, second = [e.data["amount"] for e in b.events("damage", mon="p2:snorlax")]
        self.assertLess(second, first // 3)

    def test_protean_gets_stab_on_the_move_it_changes_for(self):
        def hit(ability):
            b = start([spec("clefable", ability, ["flamethrower"])], [spec("snorlax", "noability", ["protect"])])
            game.play_turn(b, [Move(0, 0, "flamethrower", (1, 0))])
            return b.events("damage", mon="p2:snorlax")[0].data["amount"]
        self.assertEqual(hit("protean"), hit("noability") * 3 // 2)

    def test_mega_sol_sees_sun(self):
        b = start([spec("clefable", "megasol", ["moonlight", "flamethrower"], hp=1)], [spec("snorlax", "noability", ["protect"])])
        self.assertEqual(arena.weather_for(b, b.sides[0].team[0]), "sun")
        self.assertIsNone(arena.weather_for(b, b.sides[1].team[0]))
        m = b.sides[0].team[0]
        game.play_turn(b, [Move(0, 0, "moonlight", None)])
        self.assertEqual(m.hp, 1 + arena.heal_amount(m.max_hp, "sun"))

    def test_prankster_priority_is_reread_after_the_ability_changes(self):
        from champions.engine.turn import move_priority
        m = mon("banette", "prankster", ["willowisp", "bodyslam"])
        self.assertEqual(move_priority(None, m, "willowisp"), 1)
        self.assertEqual(move_priority(None, m, "bodyslam"), 0)
        m.ability = "noability"
        self.assertEqual(move_priority(None, m, "willowisp"), 0)

    def test_every_mega_form_is_playable(self):
        from champions.engine import mega
        from champions.engine.effects_table import is_supported_ability
        self.assertTrue(all(is_supported_ability(mega.form_ability(n)) for n in mega._forms()))


if __name__ == "__main__":
    unittest.main()
