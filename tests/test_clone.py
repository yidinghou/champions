import copy
import unittest

from champions.engine import game
from champions.engine.rng import ForcedRng, LabeledRng


def sp(s, m, a=None):
    return dict(species=s, moves=m, ability=a)


TEAMS = [[sp("incineroar", ["fakeout", "flamethrower", "protect", "toxic"]),
          sp("garchomp", ["earthquake", "dragonclaw", "trickroom", "encore"]),
          sp("venusaur", ["gigadrain", "sleeppowder", "leechseed", "protect"])],
         [sp("garchomp", ["earthquake", "dragonclaw", "protect", "taunt"]),
          sp("incineroar", ["fakeout", "flamethrower", "protect", "yawn"]),
          sp("venusaur", ["gigadrain", "sleeppowder", "protect", "toxic"])]]


def snapshot(b):
    return ([(m.hp, m.status, m.status_turns, dict(m.stages), repr(sorted(m.volatiles.items())))
             for s in b.sides for m in s.team], b.arena.copy(), b.turn, b.winner,
            [dict(s.conditions) for s in b.sides])


class Clone(unittest.TestCase):
    def test_same_future_as_original(self):
        for seed in range(20):
            a = game.start(TEAMS, seed=seed)
            c = a.clone()
            for _ in range(3):
                for b in (a, c):
                    if b.winner is None:
                        ch = [game.legal_choices(b, 0)[seed % 5], game.legal_choices(b, 1)[seed % 7]]
                        ch = [x for x in ch if x.slot is not None]
                        by_slot = {(x.side, x.slot): x for x in ch}
                        extra = [game.legal_choices(b, s)[-1] for s in (0, 1)]
                        for x in extra:
                            by_slot.setdefault((x.side, x.slot), x)
                        game.play_turn(b, list(by_slot.values()))
            self.assertEqual(snapshot(a), snapshot(c), seed)
            self.assertEqual(a.rng.getstate(), c.rng.getstate())

    def test_clone_is_independent(self):
        a = game.start(TEAMS, seed=3)
        before = snapshot(a)
        c = a.clone()
        c.sides[0].team[0].take(10)
        c.sides[0].team[0].stages["atk"] = 2
        c.sides[0].team[0].volatiles["x"] = {"n": 1}
        c.sides[1].conditions["tailwind"] = 4
        c.arena["trick_room"] = 5
        c.sides[0].active[0] = 1
        c.rng.randint(0, 10)
        self.assertEqual(snapshot(a), before)

    def test_record_flag_stops_logging(self):
        a = game.start(TEAMS, seed=1)
        n = len(a.log)
        q = a.clone(record=False)
        game.play_turn(q, [game.legal_choices(q, 0)[0], game.legal_choices(q, 1)[0]])
        self.assertEqual(q.log, [])
        self.assertEqual(len(a.log), n)

    def test_recording_clone_logs_to_itself(self):
        a = game.start(TEAMS, seed=1)
        c = a.clone()
        game.play_turn(c, [game.legal_choices(c, 0)[0], game.legal_choices(c, 1)[0]])
        self.assertGreater(len(c.log), len(a.log))

    def test_rng_override_and_forced_clones(self):
        a = game.start(TEAMS, seed=1)
        r = ForcedRng([1, 2], default=0)
        self.assertIs(a.clone(rng=r).rng, r)
        f = ForcedRng([5, 6]).clone()
        self.assertEqual(f.values, [5, 6])
        l = LabeledRng({"crit": [True]})
        l2 = l.clone()
        l2.rolls["crit"].pop()
        self.assertEqual(l.rolls["crit"], [True])


if __name__ == "__main__":
    unittest.main()
