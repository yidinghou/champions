"""Unit tests for held items: the damage and accuracy numbers, and rules the catalogue cases only pin indirectly."""
import unittest
from types import SimpleNamespace as NS

from champions.calc import items as citems
from champions.calc.damage import damage
from champions.calc.field import modify
from champions.engine import game, items
from champions.engine.actions import Move
from champions.engine.errors import Unsupported
from champions.engine.effects_table import is_supported_move
from champions.engine.pipeline import accuracy, hit
from champions.engine.resolve import resolve, state_key
from champions.engine.rng import ForcedRng, LabeledRng
from champions.engine.teams import build_mon, moves_data


def mon(species, ability="noability", moves=(), **kw):
    return build_mon({"species": species, "ability": ability, "moves": list(moves), **kw})


def dmg(a, d, move_id, **kw):
    return damage(a, d, moves_data()[move_id], crit=False, roll=100, spread=False, **kw)


def base(bp, a, d):
    return 22 * bp * a // d // 50 + 2


class DamageItems(unittest.TestCase):
    def setUp(self):
        self.target = mon("snorlax", "noability")      # Thick Fat would halve Fire damage

    def test_type_item_boosts_only_its_type_through_4096ths(self):
        plain = mon("clefable", "unaware", ["flamethrower"])
        coal = mon("clefable", "unaware", ["flamethrower"], item="charcoal")
        bp = moves_data()["flamethrower"]["base_power"]
        self.assertEqual(dmg(coal, self.target, "flamethrower"),
                         base(modify(bp, 4915), plain.stats["spa"], self.target.stats["spd"]))
        self.assertGreater(dmg(coal, self.target, "flamethrower"), dmg(plain, self.target, "flamethrower"))
        wrong = mon("clefable", "unaware", ["flamethrower"], item="mysticwater")
        self.assertEqual(dmg(wrong, self.target, "flamethrower"), dmg(plain, self.target, "flamethrower"))

    def test_every_type_item_boosts_its_type(self):
        d = mon("snorlax", "thickfat")
        for item, t in citems.TYPE_BOOST.items():
            with_item = NS(item=item, species="x", category=None)
            self.assertEqual(citems.base_power_mod(with_item, {"type": t, "category": "Physical"}), 4915, item)
            other = "Water" if t != "Water" else "Fire"
            self.assertEqual(citems.base_power_mod(with_item, {"type": other, "category": "Physical"}), 4096, item)

    def test_muscle_band_and_wise_glasses_split_by_category(self):
        mb, wg = NS(item="muscleband"), NS(item="wiseglasses")
        phys, spec = {"type": "Normal", "category": "Physical"}, {"type": "Normal", "category": "Special"}
        self.assertEqual((citems.base_power_mod(mb, phys), citems.base_power_mod(mb, spec)), (4505, 4096))
        self.assertEqual((citems.base_power_mod(wg, phys), citems.base_power_mod(wg, spec)), (4096, 4505))

    def test_life_orb_is_a_final_modifier(self):
        plain = mon("clefable", "unaware", ["flamethrower"])
        orb = mon("clefable", "unaware", ["flamethrower"], item="lifeorb")
        self.assertEqual(dmg(orb, self.target, "flamethrower"), modify(dmg(plain, self.target, "flamethrower"), 5324))

    def test_expert_belt_needs_super_effective(self):
        belt = mon("charizard", "blaze", ["flamethrower"], item="expertbelt")
        plain = mon("charizard", "blaze", ["flamethrower"])
        grass = mon("rillaboom", "overgrow")
        self.assertEqual(dmg(belt, grass, "flamethrower"), modify(dmg(plain, grass, "flamethrower"), 4915))
        self.assertEqual(dmg(belt, self.target, "flamethrower"), dmg(plain, self.target, "flamethrower"))

    def test_light_ball_only_for_pikachu(self):
        pika = mon("pikachu", "noability", ["thunderbolt"], item="lightball")
        plain = mon("pikachu", "noability", ["thunderbolt"])
        self.assertEqual(dmg(pika, self.target, "thunderbolt"),
                         dmg(NS(**{**plain.__dict__, "stats": {**plain.stats, "spa": plain.stats["spa"] * 2}}), self.target, "thunderbolt"))
        other = mon("clefable", "unaware", ["thunderbolt"], item="lightball")
        self.assertEqual(dmg(other, self.target, "thunderbolt"), dmg(mon("clefable", "unaware", ["thunderbolt"]), self.target, "thunderbolt"))

    def test_item_and_terrain_modifiers_chain_before_rounding(self):
        a = mon("pikachu", "noability", ["thunderbolt"], item="magnet")
        bp = moves_data()["thunderbolt"]["base_power"]
        chained = citems.chain(4915, 5325)
        self.assertEqual(dmg(a, self.target, "thunderbolt", terrain="electric"),
                         base(modify(bp, chained), a.stats["spa"], self.target.stats["spd"]) * 3 // 2)

    def test_resist_berry_halves_the_super_effective_hit_and_chilan_any_normal_hit(self):
        for berry, t in citems.RESIST_BERRY.items():
            if berry == "chilanberry":
                self.assertTrue(citems.berry_halves(berry, "Normal", 1.0))
                continue
            self.assertTrue(citems.berry_halves(berry, t, 2.0), berry)
            self.assertFalse(citems.berry_halves(berry, t, 1.0), berry)
            self.assertFalse(citems.berry_halves(berry, "Normal" if t != "Normal" else "Fire", 2.0), berry)
        d = mon("rillaboom", "overgrow")
        a = mon("charizard", "blaze", ["flamethrower"])
        plain = dmg(a, d, "flamethrower")
        berried = dmg(a, mon("rillaboom", "overgrow", item="occaberry"), "flamethrower")
        self.assertEqual(berried, modify(plain, 2048))
        self.assertEqual(dmg(a, mon("rillaboom", "overgrow", item="occaberry"), "flamethrower", berry_ok=False), plain)

    def test_confusion_self_hit_ignores_items(self):
        orb = mon("clefable", "unaware", item="lifeorb")
        plain = mon("clefable", "unaware")
        self.assertEqual(dmg(orb, orb, "bodyslam"), dmg(plain, plain, "bodyslam"))

    def test_life_orb_and_berry_chain_together(self):
        a = mon("charizard", "blaze", ["flamethrower"], item="lifeorb")
        d = mon("rillaboom", "overgrow", item="occaberry")
        plain = mon("charizard", "blaze", ["flamethrower"])
        self.assertEqual(dmg(a, d, "flamethrower"),
                         modify(dmg(plain, mon("rillaboom", "overgrow"), "flamethrower"), citems.chain(5324, 2048)))


class Accuracy(unittest.TestCase):
    def setUp(self):
        self.u, self.t = mon("clefable", "unaware"), mon("snorlax", "thickfat")

    def acc(self, user_item=None, target_item=None, moved=False, base=100):
        self.u.item, self.t.item = user_item, target_item
        return accuracy.final_accuracy(self.u, self.t, base, None, moved)

    def test_lenses_and_bright_powder(self):
        self.assertEqual(self.acc(), 100)
        self.assertEqual(self.acc("widelens"), 110)
        self.assertEqual(self.acc("zoomlens", moved=True), 120)
        self.assertEqual(self.acc("zoomlens", moved=False), 100)
        self.assertEqual(self.acc(target_item="brightpowder"), 90)
        self.assertEqual(self.acc("widelens", "brightpowder"), 99)       # chained 4505 x 3686, rounded once

    def test_scope_lens_adds_a_crit_stage(self):
        ctx = lambda item, stage=0: NS(effects={"crit_stage": stage}, user=NS(item=item))
        self.assertAlmostEqual(hit.crit_pct(ctx(None)), 100 / 24)
        self.assertEqual(hit.crit_pct(ctx("scopelens")), 12.5)
        self.assertEqual(hit.crit_pct(ctx("scopelens", 1)), 50)


def start(p1, p2, rolls=None):
    return game.start([p1, p2], seed=1, format="singles", rng=LabeledRng(rolls))


def spec(species, ability, moves, **kw):
    return {"species": species, "ability": ability, "moves": moves, **kw}


class Support(unittest.TestCase):
    def test_supported_and_inert_items(self):
        for item in ("leftovers", "sitrusberry", "occaberry", "lightclay", "charizarditex", "terrainextender", "heatrock", None, ""):
            self.assertTrue(items.is_supported_item(item), item)

    def test_unmodeled_items_are_rejected_at_start(self):
        for item in ("leek", "metronome", "normalgem", "madeupitem"):
            with self.assertRaises(Unsupported, msg=item):
                start([spec("snorlax", "thickfat", ["protect"], item=item)], [spec("clefable", "unaware", ["protect"])])

    def test_every_modeled_item_exists_in_the_data(self):
        known = set(items._item_data())
        self.assertEqual(sorted(items.MODELED_ITEMS - known), [])
        self.assertEqual(sorted((items.INERT_ITEMS | items.UNMODELED_ITEMS) - known), [])

    def test_every_item_in_the_data_is_classified(self):
        """A new item in items.json must be modeled, inert, a Mega Stone or a known gap, not silently unclassified."""
        unclassified = [i for i in items._item_data()
                        if not items.is_supported_item(i) and i not in items.UNMODELED_ITEMS]
        self.assertEqual(unclassified, [])


class State(unittest.TestCase):
    def test_item_use_is_part_of_the_state_key_and_the_snapshot(self):
        from champions.engine import replay
        b = start([spec("snorlax", "thickfat", ["protect"], item="sitrusberry", hp=100)], [spec("clefable", "unaware", ["protect"])])
        self.assertIsNone(b.sides[0].team[0].item)                      # eaten at battle start
        c = start([spec("snorlax", "thickfat", ["protect"], item="sitrusberry")], [spec("clefable", "unaware", ["protect"])])
        self.assertNotEqual(state_key(b), state_key(c))
        self.assertIsNone(replay.restore(replay.snapshot(b)).sides[0].team[0].item)

    def test_clone_keeps_the_item(self):
        b = start([spec("snorlax", "thickfat", ["protect"], item="leftovers")], [spec("clefable", "unaware", ["protect"])])
        c = b.clone()
        c.sides[0].team[0].item = None
        self.assertEqual(b.sides[0].team[0].item, "leftovers")

    def test_resolve_branches_on_a_focus_band_roll(self):
        b = start([spec("garchomp", "sandveil", ["dragonclaw"])], [spec("pikachu", "noability", ["protect"], item="focusband")])
        b.sides[0].team[0].stages["atk"] = 6
        out = resolve(b, [Move(0, 0, "dragonclaw", (1, 0))])
        self.assertEqual(sorted(round(p, 4) for p, _ in out), [0.1, 0.9])
        survived = [c for p, c in out if round(p, 4) == 0.1][0]
        self.assertEqual(survived.sides[1].team[0].hp, 1)

    def test_big_root_boosts_drain(self):
        b = start([spec("venusaur", "overgrow", ["gigadrain"], item="bigroot", hp=100)], [spec("snorlax", "thickfat", ["protect"])])
        game.play_turn(b, [Move(0, 0, "gigadrain", (1, 0))])
        dealt = b.sides[1].team[0].max_hp - b.sides[1].team[0].hp
        healed = b.events("heal", mon="p1:venusaur")[0].data["amount"]
        self.assertEqual(healed, max(1, dealt // 2) * 5324 // 4096)

    def test_switched_out_mon_loses_its_queued_move(self):
        """Eject Button pulls Snorlax out before it moves; its replacement must not use Snorlax's choice."""
        b = start([spec("clefable", "unaware", ["bodyslam"])],
                  [spec("snorlax", "thickfat", ["bodyslam"], item="ejectbutton"), spec("garchomp", "sandveil", ["protect"])])
        game.play_turn(b, [Move(0, 0, "bodyslam", (1, 0)), Move(1, 0, "bodyslam", (0, 0))])
        self.assertEqual(b.events("move", mon="p2:snorlax"), [])
        self.assertEqual(b.events("move", mon="p2:garchomp"), [])
        self.assertEqual(b.events("switch", mon="p2:garchomp")[0].data["slot"], 0)

    def test_unmodeled_effect_still_gated_for_solar_beam(self):
        self.assertFalse(is_supported_move("solarbeam"))


if __name__ == "__main__":
    unittest.main()
