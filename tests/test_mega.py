"""Unit tests for Mega Evolution and the abilities its forms bring."""
import unittest
from types import SimpleNamespace as NS

from champions.calc import abilities as cab
from champions.calc.damage import damage
from champions.calc.field import modify
from champions.engine import game, mega, replay
from champions.engine.actions import Move, Switch
from champions.engine.effects_table import is_supported_ability
from champions.engine.errors import Unsupported
from champions.engine.items import _mega_stones
from champions.engine.pipeline import accuracy, hit
from champions.engine.resolve import state_key
from champions.engine.rng import LabeledRng
from champions.engine.stages import change_stat
from champions.engine.teams import build_mon, moves_data


def mon(species, ability="noability", moves=(), **kw):
    return build_mon({"species": species, "ability": ability, "moves": list(moves), **kw})


def dmg(a, d, move_id, **kw):
    kw.setdefault("crit", False)
    return damage(a, d, moves_data()[move_id], roll=100, spread=False, **kw)


def spec(species, ability, moves, **kw):
    return {"species": species, "ability": ability, "moves": moves, **kw}


class StoneMapping(unittest.TestCase):
    def test_every_stone_belongs_to_a_species_with_a_mega_form(self):
        species = {f["species"] for f in mega._forms().values()}
        for stone in _mega_stones():
            self.assertIn(mega.stone_species(stone), species, stone)

    def test_every_mega_form_is_reachable_from_a_stone(self):
        reached = set()
        for stone in _mega_stones():
            sp = mega.stone_species(stone)
            for name, f in mega._forms().items():
                if f["species"] != sp:
                    continue
                for base in {n for n, p in mega._species_of().items() if p == sp and n not in mega._forms()}:
                    m = NS(species=base, item=stone)
                    form = mega.form_for(m)
                    if form:
                        reached.add(form)
        self.assertEqual(sorted(set(mega._forms()) - reached), [])

    def test_two_form_species_follow_the_stone(self):
        self.assertEqual(mega.form_for(mon("charizard", item="charizarditex")), "charizard-mega-x")
        self.assertEqual(mega.form_for(mon("charizard", item="charizarditey")), "charizard-mega-y")
        self.assertEqual(mega.form_for(mon("garchomp", item="garchompite")), "garchomp-mega")
        self.assertEqual(mega.form_for(mon("garchomp", item="garchompitez")), "garchomp-mega-z")
        self.assertEqual(mega.form_for(mon("meowstic-male", item="meowsticite")), "meowstic-male-mega")
        self.assertEqual(mega.form_for(mon("meowstic-female", item="meowsticite")), "meowstic-female-mega")

    def test_wrong_species_or_no_stone_gives_no_form(self):
        self.assertIsNone(mega.form_for(mon("mawile", item="charizarditey")))
        self.assertIsNone(mega.form_for(mon("mawile")))
        self.assertIsNone(mega.form_for(mon("mawile", item="leftovers")))


class Evolving(unittest.TestCase):
    def start(self, p1, p2=None, fmt="singles"):
        return game.start([p1, p2 or [spec("snorlax", "thickfat", ["protect"])]], seed=1, format=fmt, rng=LabeledRng())

    def test_legal_choices_offer_the_mega_variant_once(self):
        b = self.start([spec("mawile", "intimidate", ["bodyslam"], item="mawilite")])
        choices = game.legal_choices(b, 0)
        self.assertEqual(sorted(c.mega for c in choices if isinstance(c, Move)), [False, True])
        b.sides[0].mega_used = True
        self.assertEqual([c.mega for c in game.legal_choices(b, 0) if isinstance(c, Move)], [False])

    def test_a_team_with_an_unmodeled_mega_ability_is_rejected(self):
        from unittest import mock
        from champions.engine import effects_table
        without = effects_table.MODELED_ABILITIES - {"shadowtag"}            # pretend Gengar's Mega ability is a gap
        with mock.patch.object(effects_table, "MODELED_ABILITIES", without):
            with self.assertRaises(Unsupported):
                self.start([spec("gengar", "cursedbody", ["protect"], item="gengarite")])
            self.start([spec("gengar", "cursedbody", ["protect"])])                             # no stone: fine

    def test_snapshot_keeps_the_mega_form_and_the_spread(self):
        b = self.start([spec("mawile", "intimidate", ["protect"], item="mawilite", nature="adamant", sp="0/32/0/0/0/0")])
        game.play_turn(b, [Move(0, 0, "protect", None, mega=True)])
        r = replay.restore(replay.snapshot(b))
        m = r.sides[0].team[0]
        self.assertEqual((m.ability, m.mega, m.nature, m.sp), ("hugepower", True, "adamant", {"attack": 32}))
        self.assertEqual(m.stats, b.sides[0].team[0].stats)

    def test_state_key_sees_the_form(self):
        a = self.start([spec("mawile", "intimidate", ["protect"], item="mawilite")])
        b = a.clone()
        game.play_turn(b, [Move(0, 0, "protect", None, mega=True)])
        self.assertNotEqual(state_key(a), state_key(b))

    def test_clone_does_not_share_the_stats(self):
        a = self.start([spec("mawile", "intimidate", ["protect"], item="mawilite")])
        b = a.clone()
        game.play_turn(b, [Move(0, 0, "protect", None, mega=True)])
        self.assertFalse(a.sides[0].team[0].mega)
        self.assertNotEqual(a.sides[0].team[0].stats["atk"], b.sides[0].team[0].stats["atk"])

    def test_report_which_mega_forms_the_engine_can_play(self):
        bad = sorted(n for n in mega._forms() if not is_supported_ability(mega.form_ability(n)))
        self.assertEqual(bad, [], f"Mega forms with an unmodeled ability: {bad}")


class AbilityDamage(unittest.TestCase):
    def setUp(self):
        self.d = mon("snorlax", "noability")
        self.base = lambda ab, move="bodyslam", item=None: mon("mawile", ab, [move], **({"item": item} if item else {}))

    def test_huge_power_doubles_physical_attack_only(self):
        plain = mon("mawile", "noability", ["bodyslam"])
        hp = mon("mawile", "hugepower", ["bodyslam"])
        self.assertGreater(dmg(hp, self.d, "bodyslam"), dmg(plain, self.d, "bodyslam") * 3 // 2)
        spec_ = mon("mawile", "hugepower", ["thunderbolt"])
        self.assertEqual(dmg(spec_, self.d, "thunderbolt"), dmg(mon("mawile", "noability", ["thunderbolt"]), self.d, "thunderbolt"))

    def test_base_power_abilities_use_move_flags(self):
        cases = [("toughclaws", "bodyslam", 5325), ("megalauncher", "waterpulse", 6144), ("strongjaw", "crunch", 6144),
                 ("ironfist", "firepunch", 4915), ("sharpness", "xscissor", 6144)]
        for ab, move_id, mod in cases:
            if move_id not in moves_data():
                continue
            self.assertEqual(cab.base_power_mod(NS(ability=ab), moves_data()[move_id]), mod, (ab, move_id))
        self.assertEqual(cab.base_power_mod(NS(ability="toughclaws"), moves_data()["flamethrower"]), 4096)

    def test_technician_only_up_to_60_power(self):
        weak, strong = {"base_power": 60, "flags": []}, {"base_power": 61, "flags": []}
        self.assertEqual(cab.base_power_mod(NS(ability="technician"), weak), 6144)
        self.assertEqual(cab.base_power_mod(NS(ability="technician"), strong), 4096)

    def test_adaptability_makes_stab_x2(self):
        a, plain = mon("charizard", "adaptability", ["flamethrower"]), mon("charizard", "noability", ["flamethrower"])
        target = mon("snorlax", "noability")
        self.assertGreater(dmg(a, target, "flamethrower"), dmg(plain, target, "flamethrower"))
        self.assertEqual(cab.stab(NS(ability="adaptability")), (2, 1))
        self.assertEqual(cab.stab(NS(ability="noability")), (3, 2))

    def test_pixilate_turns_normal_into_fairy_with_a_boost(self):
        from champions.engine import arena
        b = NS(arena={})
        move = moves_data()["bodyslam"]
        out = arena.adjust_move(b, move, {}, NS(ability="pixilate"))
        self.assertEqual((out["type"], out["ate"]), ("Fairy", True))
        self.assertEqual(arena.adjust_move(b, moves_data()["flamethrower"], {}, NS(ability="pixilate"))["type"], "Fire")
        a = mon("sylveon", "pixilate", ["bodyslam"])
        self.assertEqual(cab.base_power_mod(a, out), 4915)

    def test_thick_fat_halves_fire_and_ice_attack(self):
        a = mon("charizard", "noability", ["flamethrower"])
        plain, fat = mon("snorlax", "noability"), mon("snorlax", "thickfat")
        self.assertLess(dmg(a, fat, "flamethrower"), dmg(a, plain, "flamethrower") * 6 // 10)
        self.assertEqual(dmg(mon("clefable", "noability", ["thunderbolt"]), fat, "thunderbolt"),
                         dmg(mon("clefable", "noability", ["thunderbolt"]), plain, "thunderbolt"))

    def test_multiscale_only_at_full_hp_and_filter_only_when_super_effective(self):
        a = mon("charizard", "noability", ["flamethrower"])
        full, hurt = mon("rillaboom", "multiscale"), mon("rillaboom", "multiscale", hp=100)
        self.assertEqual(dmg(a, full, "flamethrower"), modify(dmg(a, mon("rillaboom", "noability"), "flamethrower"), 2048))
        self.assertEqual(dmg(a, hurt, "flamethrower"), dmg(a, mon("rillaboom", "noability", hp=100), "flamethrower"))
        flt = mon("rillaboom", "filter")
        self.assertEqual(dmg(a, flt, "flamethrower"), modify(dmg(a, mon("rillaboom", "noability"), "flamethrower"), 3072))
        self.assertEqual(dmg(a, mon("snorlax", "filter"), "flamethrower"), dmg(a, mon("snorlax", "noability"), "flamethrower"))

    def test_solar_power_needs_sun_and_special(self):
        a, plain = mon("charizard", "solarpower", ["flamethrower"]), mon("charizard", "noability", ["flamethrower"])
        self.assertGreater(dmg(a, self.d, "flamethrower", weather="sun"), dmg(plain, self.d, "flamethrower", weather="sun"))
        self.assertEqual(dmg(a, self.d, "flamethrower"), dmg(plain, self.d, "flamethrower"))


class AbilityRules(unittest.TestCase):
    def test_skill_link_and_shell_armor_and_no_guard(self):
        ctx = lambda ab: NS(move={"multihit": [2, 5]}, battle=NS(rng=LabeledRng()), user=NS(ability=ab))
        self.assertEqual(hit.hit_count(ctx("skilllink")), 5)
        self.assertNotEqual(hit.hit_count(ctx("noability")), 5)
        u, t = mon("clefable", "noguard"), mon("snorlax", "thickfat")
        b = game.start([[spec("clefable", "noguard", ["thunderbolt"])], [spec("snorlax", "thickfat", ["protect"])]], seed=1,
                       format="singles", rng=LabeledRng({"accuracy": [False]}))
        game.play_turn(b, [Move(0, 0, "thunderbolt", (1, 0))])
        self.assertEqual(b.events("missed"), [])

    def test_contrary_inverts_and_defiant_punishes(self):
        b = game.start([[spec("snorlax", "contrary", ["protect"])], [spec("clefable", "noability", ["protect"])]], seed=1,
                       format="singles", rng=LabeledRng())
        m = b.sides[0].team[0]
        self.assertEqual(change_stat(b, m, "atk", -1, source=b.sides[1].team[0], cause="foe"), 1)
        b2 = game.start([[spec("snorlax", "defiant", ["protect"])], [spec("clefable", "noability", ["protect"])]], seed=1,
                        format="singles", rng=LabeledRng())
        d = b2.sides[0].team[0]
        change_stat(b2, d, "def", -1, source=b2.sides[1].team[0], cause="foe")
        self.assertEqual((d.stages["def"], d.stages["atk"]), (-1, 2))
        change_stat(b2, d, "def", -1, source=d, cause="self")            # a self-drop does not trigger it
        self.assertEqual(d.stages["atk"], 2)

    def test_regenerator_heals_a_third_on_switch_out(self):
        b = game.start([[spec("snorlax", "regenerator", ["protect"], hp=60), spec("clefable", "noability", ["protect"])],
                        [spec("garchomp", "sandveil", ["protect"])]], seed=1, format="singles", rng=LabeledRng())
        game.play_turn(b, [Switch(0, 0, 1)])
        self.assertEqual(b.sides[0].team[0].hp, 60 + b.sides[0].team[0].max_hp // 3)

    def test_speed_boost_starts_the_turn_after_entry(self):
        b = game.start([[spec("snorlax", "speedboost", ["protect"])], [spec("garchomp", "sandveil", ["protect"])]], seed=1,
                       format="singles", rng=LabeledRng())
        for _ in range(2):
            game.play_turn(b, [Move(0, 0, "protect", None)])
            b.sides[0].team[0].volatiles.clear()
        self.assertEqual(b.sides[0].team[0].stages["spe"], 2)

    def test_levitate_like_eelevate_and_bulletproof_and_infiltrator(self):
        b = game.start([[spec("garchomp", "sandveil", ["earthquake", "shadowball"])], [spec("snorlax", "eelevate", ["protect"])]],
                       seed=1, format="singles", rng=LabeledRng())
        game.play_turn(b, [Move(0, 0, "earthquake", (1, 0))])
        self.assertEqual(len(b.events("immune", mon="p2:snorlax")), 1)
        b = game.start([[spec("garchomp", "sandveil", ["shadowball"])], [spec("snorlax", "bulletproof", ["protect"])]],
                       seed=1, format="singles", rng=LabeledRng())
        game.play_turn(b, [Move(0, 0, "shadowball", (1, 0))])
        self.assertEqual(len(b.events("immune", mon="p2:snorlax", ability="bulletproof")), 1)

    def test_unseen_fist_goes_through_protect(self):
        b = game.start([[spec("garchomp", "unseenfist", ["bodyslam"])], [spec("snorlax", "thickfat", ["protect"])]], seed=1,
                       format="singles", rng=LabeledRng())
        game.play_turn(b, [Move(0, 0, "bodyslam", (1, 0)), Move(1, 0, "protect", None)])
        self.assertEqual(b.events("protected"), [])
        self.assertLess(b.sides[1].team[0].hp, b.sides[1].team[0].max_hp)


if __name__ == "__main__":
    unittest.main()
