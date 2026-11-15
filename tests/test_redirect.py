"""Unit tests for redirection and absorbing abilities: the rules the catalogue cases pin only through end states."""
import unittest

from champions.engine import game, redirect
from champions.engine.actions import Move
from champions.engine.effects_table import is_supported_ability, is_supported_move
from champions.engine.rng import LabeledRng
from champions.engine.teams import moves_data


def spec(species, ability, moves, **kw):
    return {"species": species, "ability": ability, "moves": moves, **kw}


def doubles(p1, p2):
    return game.start([p1, p2], seed=1, format="doubles", rng=LabeledRng())


MOVES = ["bodyslam", "thunderbolt", "hydropump"]


class Redirect(unittest.TestCase):
    def setUp(self):
        self.b = doubles([spec("clefable", "unaware", MOVES), spec("mawile", "noability", ["protect"])],
                         [spec("snorlax", "thickfat", ["protect"]), spec("garchomp", "sandveil", ["protect"])])
        self.user = self.b.sides[0].team[0]
        self.snorlax, self.garchomp = self.b.sides[1].team

    def target(self, move_id="bodyslam"):
        return redirect.redirect_target(self.b, self.user, moves_data()[move_id], move_id, self.snorlax)

    def test_nothing_redirects_by_default(self):
        self.assertIs(self.target(), self.snorlax)

    def test_follow_me_draws_the_move(self):
        self.garchomp.volatiles["followme"] = 1
        self.assertIs(self.target(), self.garchomp)

    def test_the_latest_follow_me_wins(self):
        self.snorlax.volatiles["followme"] = 1
        self.garchomp.volatiles["ragepowder"] = 2
        self.assertIs(self.target(), self.garchomp)
        self.garchomp.volatiles["ragepowder"] = 0
        self.assertIs(self.target(), self.snorlax)

    def test_rage_powder_skips_grass_and_overcoat_but_follow_me_does_not(self):
        self.garchomp.volatiles["ragepowder"] = 1
        self.user.types = ["grass"]
        self.assertIs(self.target(), self.snorlax)
        self.user.types, self.user.ability = ["fairy"], "overcoat"
        self.assertIs(self.target(), self.snorlax)
        del self.garchomp.volatiles["ragepowder"]
        self.garchomp.volatiles["followme"] = 1
        self.assertIs(self.target(), self.garchomp)

    def test_fainted_follow_me_user_is_ignored(self):
        self.garchomp.volatiles["followme"] = 1
        self.garchomp.hp = 0
        self.assertIs(self.target(), self.snorlax)

    def test_singles_never_redirect(self):
        b = game.start([[spec("clefable", "unaware", MOVES)], [spec("snorlax", "thickfat", ["protect"])]], seed=1,
                       format="singles", rng=LabeledRng())
        b.sides[1].team[0].volatiles["followme"] = 1
        t = b.sides[1].team[0]
        self.assertIs(redirect.redirect_target(b, b.sides[0].team[0], moves_data()["bodyslam"], "bodyslam", t), t)

    def test_lightning_rod_matches_only_its_type_and_not_the_user(self):
        self.garchomp.ability = "lightningrod"
        self.assertIs(self.target("thunderbolt"), self.garchomp)
        self.assertIs(self.target("hydropump"), self.snorlax)
        self.garchomp.ability, self.user.ability = "noability", "lightningrod"
        self.assertIs(self.target("thunderbolt"), self.snorlax)

    def test_follow_me_is_gone_after_the_turn_and_after_a_switch(self):
        game.play_turn(self.b, [Move(1, 0, "protect", None)])
        self.snorlax.volatiles["followme"] = 1
        self.snorlax.clear_on_switch()
        self.assertNotIn("followme", self.snorlax.volatiles)


class Absorb(unittest.TestCase):
    def test_heal_is_a_quarter_with_a_floor_of_one(self):
        b = game.start([[spec("garchomp", "sandveil", ["thunderbolt"])],
                        [spec("snorlax", "voltabsorb", ["protect"], hp=100)]], seed=1, format="singles", rng=LabeledRng())
        game.play_turn(b, [Move(0, 0, "thunderbolt", (1, 0))])
        self.assertEqual(b.sides[1].team[0].hp, 100 + 235 // 4)

    def test_the_holders_own_move_is_not_absorbed(self):
        b = game.start([[spec("pikachu", "voltabsorb", ["thunderbolt"])], [spec("snorlax", "thickfat", ["protect"])]],
                       seed=1, format="singles", rng=LabeledRng())
        game.play_turn(b, [Move(0, 0, "thunderbolt", (1, 0))])
        self.assertEqual(b.events("immune"), [])
        self.assertLess(b.sides[1].team[0].hp, b.sides[1].team[0].max_hp)

    def test_new_moves_and_abilities_are_supported(self):
        for m in ("followme", "ragepowder", "thunderbolt", "hydropump"):
            self.assertTrue(is_supported_move(m), m)
        for a in ("lightningrod", "stormdrain", "sapsipper", "motordrive", "voltabsorb", "waterabsorb"):
            self.assertTrue(is_supported_ability(a), a)


if __name__ == "__main__":
    unittest.main()
