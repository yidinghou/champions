"""Unit tests for screens and Speed re-reading: the damage numbers and ordering the catalogue pins indirectly."""
import unittest

from champions.calc import items as citems
from champions.calc.damage import damage
from champions.calc.field import modify
from champions.engine import game
from champions.engine.actions import Move
from champions.engine.rng import LabeledRng
from champions.engine.teams import build_mon, moves_data


def mon(species, ability="noability", moves=(), **kw):
    return build_mon({"species": species, "ability": ability, "moves": list(moves), **kw})


def dmg(a, d, move_id, **kw):
    kw.setdefault("crit", False)
    return damage(a, d, moves_data()[move_id], roll=100, spread=False, **kw)


class ScreenDamage(unittest.TestCase):
    def setUp(self):
        self.a = mon("clefable", "unaware", ["bodyslam", "flamethrower"])
        self.d = mon("snorlax", "thickfat")
        self.phys = dmg(self.a, self.d, "bodyslam")
        self.spec = dmg(self.a, self.d, "flamethrower")

    def test_reflect_halves_physical_only(self):
        self.assertEqual(dmg(self.a, self.d, "bodyslam", screens=("reflect",)), modify(self.phys, 2048))
        self.assertEqual(dmg(self.a, self.d, "flamethrower", screens=("reflect",)), self.spec)

    def test_light_screen_halves_special_only(self):
        self.assertEqual(dmg(self.a, self.d, "flamethrower", screens=("lightscreen",)), modify(self.spec, 2048))
        self.assertEqual(dmg(self.a, self.d, "bodyslam", screens=("lightscreen",)), self.phys)

    def test_aurora_veil_covers_both(self):
        self.assertEqual(dmg(self.a, self.d, "bodyslam", screens=("auroraveil",)), modify(self.phys, 2048))
        self.assertEqual(dmg(self.a, self.d, "flamethrower", screens=("auroraveil",)), modify(self.spec, 2048))

    def test_doubles_use_two_thirds(self):
        self.assertEqual(dmg(self.a, self.d, "bodyslam", screens=("reflect",), doubles=True), modify(self.phys, 2732))

    def test_a_crit_ignores_the_screen(self):
        crit = dmg(self.a, self.d, "bodyslam", crit=True)
        self.assertEqual(dmg(self.a, self.d, "bodyslam", crit=True, screens=("reflect",)), crit)

    def test_screens_do_not_stack(self):
        self.assertEqual(dmg(self.a, self.d, "bodyslam", screens=("reflect", "auroraveil")),
                         dmg(self.a, self.d, "bodyslam", screens=("reflect",)))

    def test_screen_chains_with_life_orb_and_a_resist_berry(self):
        a = mon("charizard", "blaze", ["flamethrower"], item="lifeorb")
        d = mon("rillaboom", "overgrow", item="occaberry")
        base = dmg(mon("charizard", "blaze", ["flamethrower"]), mon("rillaboom", "overgrow"), "flamethrower")
        chain = citems.chain(citems.chain(2048, 5324), 2048)
        self.assertEqual(dmg(a, d, "flamethrower", screens=("lightscreen",)), modify(base, chain))

    def test_confusion_self_hit_ignores_the_screen(self):
        self.assertEqual(dmg(self.d, self.d, "bodyslam", screens=("reflect",)), dmg(self.d, self.d, "bodyslam"))


def start(p1, p2, fmt="singles"):
    return game.start([p1, p2], seed=1, format=fmt, rng=LabeledRng())


def spec(species, ability, moves, **kw):
    return {"species": species, "ability": ability, "moves": moves, **kw}


class InBattle(unittest.TestCase):
    def test_reflect_cuts_a_real_hit_in_a_battle(self):
        def hit_with(reflect):
            b = start([spec("clefable", "unaware", ["bodyslam"])], [spec("snorlax", "thickfat", ["protect"])])
            if reflect:
                b.sides[1].conditions["reflect"] = 3
            game.play_turn(b, [Move(0, 0, "bodyslam", (1, 0))])
            return b.events("damage", mon="p2:snorlax")[0].data["amount"]
        self.assertEqual(hit_with(True), modify(hit_with(False), 2048))

    def test_doubles_battle_uses_the_two_thirds_rule(self):
        def hit_with(reflect):
            b = start([spec("clefable", "unaware", ["bodyslam"])], [spec("snorlax", "thickfat", ["protect"])], "doubles")
            if reflect:
                b.sides[1].conditions["reflect"] = 3
            game.play_turn(b, [Move(0, 0, "bodyslam", (1, 0))])
            return b.events("damage", mon="p2:snorlax")[0].data["amount"]
        self.assertEqual(hit_with(True), modify(hit_with(False), 2732))

    def test_light_clay_is_a_modeled_item(self):
        from champions.engine import items
        self.assertIn("lightclay", items.MODELED_ITEMS)

    def test_paralysis_mid_turn_reorders_the_rest_of_the_turn(self):
        """Doubles: Garchomp (122) paralyzes Mawile (70 -> 35) before it moves, so Mawile now moves after Snorlax (50)."""
        teams = [[spec("garchomp", "sandveil", ["thunderwave"]), spec("clefable", "unaware", ["bodyslam"])],
                 [spec("mawile", "noability", ["bodyslam"]), spec("snorlax", "thickfat", ["bodyslam"])]]
        b = game.start(teams, seed=1, format="doubles", rng=LabeledRng({"fullpara": [False]}))
        game.play_turn(b, [Move(0, 0, "thunderwave", (1, 0)), Move(0, 1, "bodyslam", (1, 1)),
                           Move(1, 0, "bodyslam", (0, 0)), Move(1, 1, "bodyslam", (0, 1))])
        order = [e.data["mon"] for e in b.events("move")]
        self.assertLess(order.index("p2:snorlax"), order.index("p2:mawile"))

    def test_speed_is_reread_for_the_remaining_actions_only(self):
        """A mon that has already moved is not moved again when the order is recomputed."""
        teams = [[spec("garchomp", "sandveil", ["tailwind", "bodyslam"]), spec("mawile", "noability", ["bodyslam"])],
                 [spec("clefable", "unaware", ["bodyslam"]), spec("snorlax", "thickfat", ["bodyslam"])]]
        b = game.start(teams, seed=1, format="doubles", rng=LabeledRng())
        game.play_turn(b, [Move(0, 0, "tailwind", None), Move(0, 1, "bodyslam", (1, 1)),
                           Move(1, 0, "bodyslam", (0, 0)), Move(1, 1, "bodyslam", (0, 1))])
        mons = [e.data["mon"] for e in b.events("move")]
        self.assertEqual(len(mons), len(set(mons)), mons)
        self.assertEqual(len(mons), 4)


if __name__ == "__main__":
    unittest.main()
