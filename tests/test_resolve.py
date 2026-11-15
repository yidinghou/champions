import dataclasses
import unittest

from champions.engine import game
from champions.engine import resolve as R
from champions.engine.state import Battle, Mon, Side


def sp(s, m, a=None):
    return dict(species=s, moves=m, ability=a)


def battle():
    return game.start([[sp("incineroar", ["flamethrower"], "blaze"), sp("garchomp", ["earthquake"], "sandveil")],
                       [sp("gengar", ["shadowball"], "cursedbody"), sp("dragonite", ["dragonclaw"], "innerfocus")]],
                      seed=1, format="doubles")


class StateKey(unittest.TestCase):
    def test_every_state_field_is_accounted_for(self):
        """If this fails, a field was added to the battle state: decide whether it belongs in state_key."""
        def names(cls):
            return {f.name for f in dataclasses.fields(cls)}
        self.assertEqual(names(Mon), set(R.MON_KEYED) | set(R.MON_FIXED))
        self.assertEqual(names(Side), set(R.SIDE_KEYED) | set(R.SIDE_FIXED))
        self.assertEqual(names(Battle), set(R.BATTLE_KEYED) | set(R.BATTLE_IGNORED))

    def test_key_changes_with_each_keyed_field(self):
        base = R.state_key(battle())
        for mutate in (lambda b: setattr(b.sides[0].team[0], "hp", 1),
                       lambda b: setattr(b.sides[0].team[0], "status", "par"),
                       lambda b: b.sides[0].team[0].stages.__setitem__("atk", 2),
                       lambda b: b.sides[0].team[0].volatiles.__setitem__("taunt", 3),
                       lambda b: b.sides[0].conditions.__setitem__("tailwind", 3),
                       lambda b: b.arena.__setitem__("trick_room", 3),
                       lambda b: setattr(b, "turn", 5)):
            b = battle()
            mutate(b)
            self.assertNotEqual(R.state_key(b), base)

    def test_key_ignores_the_log_and_is_stable(self):
        a, b = battle(), battle()
        b.log_event("noise")
        self.assertEqual(R.state_key(a), R.state_key(b))
        self.assertEqual(R.state_key(a), R.state_key(a.clone()))
        hash(R.state_key(a))


if __name__ == "__main__":
    unittest.main()
