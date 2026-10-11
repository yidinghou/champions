"""Battle scenarios, one class per mechanic. Each test sets up its teams (and any forced dice), plays turns,
and asserts, all in the same method. Slots are p1a/p1b/p2a/p2b; team refs look like "p2:0" (side:index).
Add a test, watch it fail, then make the engine pass it. Run: python3 -m unittest tests.test_battle_cases -v"""
import unittest

from champions.battle import Battle
from champions.calc import damage

SELF_MOVES = {"trickroom", "tailwind", "protect"}  # no target
P1_FIRST = ["p1a:mudslap", "p2a:mudslap"]
P2_FIRST = ["p2a:mudslap", "p1a:mudslap"]


def mon(species, *moves, **keys):
    """A team entry: mon("incineroar", "fakeout", "mudslap", item="choicescarf", hp=1)."""
    return {"species": species, "moves": list(moves), **keys}


def use(move, target=None):
    return {"move": move} if target is None else {"move": move, "target": target}


def aim(move, target):
    return use(move, None if move in SELF_MOVES else target)


def duel(p1, p2, **kw):
    return Battle({"p1": [p1], "p2": [p2]}, **kw)


def exchange(b, p1_move, p2_move):
    """One 1v1 turn: p1a and p2a each use a move on the other (self/field moves take no target)."""
    return b.turn({"p1a": aim(p1_move, "p2a"), "p2a": aim(p2_move, "p1a")})


class BattleTest(unittest.TestCase):
    def assertDamaged(self, b, *refs):
        for ref in refs:
            self.assertLess(b.team_mon(ref).hp, b.team_mon(ref).max_hp, f"{ref} should be damaged")

    def assertFull(self, b, *refs):
        for ref in refs:
            self.assertEqual(b.team_mon(ref).hp, b.team_mon(ref).max_hp, f"{ref} should be at full HP")


class TurnOrder(BattleTest):
    """Faster mon moves first; Choice Scarf, stat stages and Tailwind scale Speed.
    https://bulbapedia.bulbagarden.net/wiki/Speed  .../Stat_modifier  .../Choice_Scarf
    https://www.smogon.com/dex/sv/moves/tailwind"""

    def test_faster_mon_moves_first(self):
        b = duel(mon("incineroar", "mudslap"), mon("dragapult", "mudslap"))
        self.assertEqual(exchange(b, "mudslap", "mudslap").order, P2_FIRST)

    def test_order_is_independent_of_which_side_is_listed_first(self):
        b = duel(mon("dragapult", "mudslap"), mon("incineroar", "mudslap"))
        self.assertEqual(exchange(b, "mudslap", "mudslap").order, P1_FIRST)

    def test_choice_scarf_lets_slower_rillaboom_outspeed_garchomp(self):
        b = duel(mon("rillaboom", "mudslap", item="choicescarf"), mon("garchomp", "mudslap"))
        self.assertEqual(exchange(b, "mudslap", "mudslap").order, P1_FIRST)

    def test_plus_1_speed_is_not_enough_for_incineroar_to_pass_garchomp(self):
        b = duel(mon("incineroar", "mudslap", boosts={"speed": 1}), mon("garchomp", "mudslap"))
        self.assertEqual(exchange(b, "mudslap", "mudslap").order, P2_FIRST)

    def test_plus_2_speed_lets_incineroar_outspeed_garchomp(self):
        b = duel(mon("incineroar", "mudslap", boosts={"speed": 2}), mon("garchomp", "mudslap"))
        self.assertEqual(exchange(b, "mudslap", "mudslap").order, P1_FIRST)

    def test_tailwind_doubles_speed_for_4_turns_including_the_cast_turn(self):
        b = duel(mon("incineroar", "tailwind", "mudslap"), mon("garchomp", "mudslap"))
        self.assertEqual(exchange(b, "tailwind", "mudslap").order, ["p2a:mudslap", "p1a:tailwind"])
        for _ in range(3):  # turns 2-4: incineroar outspeeds garchomp
            self.assertEqual(exchange(b, "mudslap", "mudslap").order, P1_FIRST)
        self.assertEqual(exchange(b, "mudslap", "mudslap").order, P2_FIRST)  # turn 5: expired
        self.assertEqual(b.field["tailwind_p1"], 0)

    def test_tailwind_on_the_opposing_side_lets_incineroar_outspeed_garchomp(self):
        b = duel(mon("garchomp", "mudslap"), mon("incineroar", "mudslap"), field={"tailwind_p2": 4})
        self.assertEqual(exchange(b, "mudslap", "mudslap").order, P2_FIRST)

    def test_doubles_four_mons_act_in_descending_speed(self):
        teams = {"p1": [mon("dragapult", "mudslap"), mon("incineroar", "mudslap")],
                 "p2": [mon("rillaboom", "mudslap"), mon("garchomp", "mudslap")]}
        got = Battle(teams, active=2).turn({"p1a": use("mudslap", "p2a"), "p1b": use("mudslap", "p2a"),
                                            "p2a": use("mudslap", "p1a"), "p2b": use("mudslap", "p1a")})
        self.assertEqual(got.order, ["p1a:mudslap", "p2b:mudslap", "p2a:mudslap", "p1b:mudslap"])


class Priority(BattleTest):
    """Priority bracket first, then Speed; switches go before moves.
    https://bulbapedia.bulbagarden.net/wiki/Priority"""

    def test_priority_move_beats_a_faster_mon(self):
        b = duel(mon("incineroar", "quickattack"), mon("dragapult", "mudslap"))
        self.assertEqual(exchange(b, "quickattack", "mudslap").order, ["p1a:quickattack", "p2a:mudslap"])

    def test_higher_priority_beats_lower_priority_regardless_of_speed(self):
        b = duel(mon("incineroar", "extremespeed"), mon("dragapult", "quickattack"))
        self.assertEqual(exchange(b, "extremespeed", "quickattack").order, ["p1a:extremespeed", "p2a:quickattack"])

    def test_negative_priority_moves_last_even_for_the_fastest_mon(self):
        b = duel(mon("dragapult", "trickroom"), mon("incineroar", "mudslap"))
        self.assertEqual(exchange(b, "trickroom", "mudslap").order, ["p2a:mudslap", "p1a:trickroom"])

    def test_switches_resolve_before_moves_so_the_attack_hits_the_replacement(self):
        b = Battle({"p1": [mon("incineroar", "mudslap"), mon("kingambit", "mudslap")],
                    "p2": [mon("dragapult", "mudslap")]})
        got = b.turn({"p1a": {"switch": 1}, "p2a": use("mudslap", "p1a")})
        self.assertEqual(got.order, ["p1a:switch", "p2a:mudslap"])
        self.assertEqual(b.mon("p1a").species, "kingambit")
        self.assertDamaged(b, "p1:1")
        self.assertFull(b, "p1:0")


class TrickRoom(BattleTest):
    """Trick Room reverses Speed order for 5 turns, cast at -7 priority.
    https://www.smogon.com/dex/sv/moves/trick-room"""

    def test_reverses_speed_order(self):
        b = duel(mon("incineroar", "mudslap"), mon("dragapult", "mudslap"), field={"trick_room": 5})
        self.assertEqual(exchange(b, "mudslap", "mudslap").order, P1_FIRST)

    def test_does_not_apply_the_turn_it_is_used(self):
        b = duel(mon("incineroar", "trickroom", "mudslap"), mon("garchomp", "mudslap"))
        self.assertEqual(exchange(b, "trickroom", "mudslap").order, ["p2a:mudslap", "p1a:trickroom"])
        self.assertEqual(exchange(b, "mudslap", "mudslap").order, P1_FIRST)

    def test_priority_still_beats_trick_room(self):
        b = duel(mon("garchomp", "quickattack"), mon("incineroar", "mudslap"), field={"trick_room": 5})
        self.assertEqual(exchange(b, "quickattack", "mudslap").order, ["p1a:quickattack", "p2a:mudslap"])

    def test_two_equal_priority_movers_slower_goes_first(self):
        b = duel(mon("garchomp", "quickattack"), mon("incineroar", "quickattack"), field={"trick_room": 5})
        self.assertEqual(exchange(b, "quickattack", "quickattack").order, ["p2a:quickattack", "p1a:quickattack"])

    def test_using_it_while_active_ends_it(self):
        b = duel(mon("incineroar", "trickroom"), mon("garchomp", "mudslap"), field={"trick_room": 3})
        self.assertEqual(exchange(b, "trickroom", "mudslap").order, ["p2a:mudslap", "p1a:trickroom"])
        self.assertEqual(b.field["trick_room"], 0)

    def test_lasts_5_turns_counting_the_turn_it_was_used(self):
        b = duel(mon("incineroar", "trickroom", "mudslap"), mon("garchomp", "mudslap"))
        self.assertEqual(exchange(b, "trickroom", "mudslap").order, ["p2a:mudslap", "p1a:trickroom"])
        for _ in range(4):  # turns 2-5: still reversed
            self.assertEqual(exchange(b, "mudslap", "mudslap").order, P1_FIRST)
        self.assertEqual(exchange(b, "mudslap", "mudslap").order, P2_FIRST)  # turn 6: over
        self.assertEqual(b.field["trick_room"], 0)

    def test_doubles_reverses_all_four(self):
        teams = {"p1": [mon("dragapult", "mudslap"), mon("incineroar", "mudslap")],
                 "p2": [mon("rillaboom", "mudslap"), mon("garchomp", "mudslap")]}
        got = Battle(teams, active=2, field={"trick_room": 5}).turn(
            {"p1a": use("mudslap", "p2a"), "p1b": use("mudslap", "p2a"),
             "p2a": use("mudslap", "p1a"), "p2b": use("mudslap", "p1a")})
        self.assertEqual(got.order, ["p1b:mudslap", "p2a:mudslap", "p2b:mudslap", "p1a:mudslap"])


class Paralysis(BattleTest):
    """Halves Speed; 25% chance (roll < 25) to be fully paralyzed.
    https://bulbapedia.bulbagarden.net/wiki/Paralysis_(status_condition)"""

    def test_halves_speed(self):
        b = duel(mon("garchomp", "mudslap", status="par"), mon("incineroar", "mudslap"))
        self.assertEqual(exchange(b, "mudslap", "mudslap").order, P2_FIRST)

    def test_stops_the_move_on_a_roll_under_25(self):
        b = duel(mon("garchomp", "mudslap", status="par"), mon("incineroar", "tailwind"), chance=[10])
        self.assertEqual(exchange(b, "mudslap", "tailwind").paralyzed, ["p1a"])
        self.assertFull(b, "p2:0")

    def test_moves_on_a_roll_of_25_or_more(self):
        b = duel(mon("garchomp", "mudslap", status="par"), mon("incineroar", "tailwind"), chance=[25])
        self.assertEqual(exchange(b, "mudslap", "tailwind").paralyzed, [])
        self.assertDamaged(b, "p2:0")


class Accuracy(BattleTest):
    """A move hits when the roll is below its accuracy; `chance` forces the rolls in order.
    https://bulbapedia.bulbagarden.net/wiki/Accuracy"""

    def _aquatail_vs_tailwind(self, chance):  # Aqua Tail is 90% accurate
        return duel(mon("garchomp", "aquatail"), mon("incineroar", "tailwind"), chance=chance)

    def test_90_percent_move_misses_on_a_high_roll(self):
        b = self._aquatail_vs_tailwind([95])
        got = exchange(b, "aquatail", "tailwind")
        self.assertEqual(got.order, ["p1a:aquatail", "p2a:tailwind"])
        self.assertEqual(got.missed, ["p1a"])
        self.assertFull(b, "p2:0")

    def test_90_percent_move_hits_on_a_low_roll(self):
        b = self._aquatail_vs_tailwind([10])
        self.assertEqual(exchange(b, "aquatail", "tailwind").missed, [])
        self.assertDamaged(b, "p2:0")

    def test_90_percent_move_hits_on_89_and_misses_on_90(self):
        b = self._aquatail_vs_tailwind([89, 90])
        self.assertEqual(exchange(b, "aquatail", "tailwind").missed, [])
        self.assertEqual(exchange(b, "aquatail", "tailwind").missed, ["p1a"])

    def test_moves_that_never_miss_ignore_accuracy(self):
        b = duel(mon("garchomp", "aerialace"), mon("incineroar", "tailwind"), chance=[99.9])
        self.assertEqual(exchange(b, "aerialace", "tailwind").missed, [])
        self.assertDamaged(b, "p2:0")


class SpreadMoves(BattleTest):
    """Spread moves roll accuracy per target; Earthquake also hits the ally.
    https://bulbapedia.bulbagarden.net/wiki/Damage#Number_of_targets
    https://bulbapedia.bulbagarden.net/wiki/Earthquake_(move)"""

    def _doubles(self, move, **kw):
        teams = {"p1": [mon("garchomp", move), mon("incineroar", "tailwind")],
                 "p2": [mon("kingambit", "tailwind"), mon("incineroar", "tailwind")]}
        b = Battle(teams, active=2, **kw)
        got = b.turn({"p1a": use(move), "p1b": use("tailwind"), "p2a": use("tailwind"), "p2b": use("tailwind")})
        return b, got

    def test_hits_both_foes(self):
        b, got = self._doubles("rockslide", chance=[10, 10])
        self.assertEqual(got.missed, [])
        self.assertDamaged(b, "p2:0", "p2:1")
        self.assertFull(b, "p1:1")

    def test_can_miss_one_foe_and_hit_the_other(self):
        b, got = self._doubles("rockslide", chance=[10, 95])
        self.assertEqual(got.missed, ["p1a"])
        self.assertDamaged(b, "p2:0")
        self.assertFull(b, "p2:1")

    def test_earthquake_hits_an_ally_in_doubles(self):
        b, _ = self._doubles("earthquake")
        self.assertDamaged(b, "p1:1", "p2:0", "p2:1")
        self.assertFull(b, "p1:0")


class FirstTurnMoves(BattleTest):
    """Fake Out and First Impression only work on the user's first turn out (switching back in resets it).
    https://www.smogon.com/dex/sv/moves/fake-out  .../first-impression"""

    def test_fake_out_flinches_a_slower_target(self):
        b = duel(mon("incineroar", "fakeout"), mon("arcanine", "mudslap"))
        got = exchange(b, "fakeout", "mudslap")
        self.assertEqual(got.order, ["p1a:fakeout", "p2a:mudslap"])
        self.assertEqual(got.flinched, ["p2a"])
        self.assertDamaged(b, "p2:0")
        self.assertFull(b, "p1:0")

    def test_fake_out_fails_after_the_users_first_turn_on_the_field(self):
        b = duel(mon("incineroar", "fakeout"), mon("arcanine", "mudslap"))
        self.assertEqual(exchange(b, "fakeout", "mudslap").flinched, ["p2a"])
        got = exchange(b, "fakeout", "mudslap")
        self.assertEqual(got.order, ["p1a:fakeout", "p2a:mudslap"])
        self.assertEqual(got.failed, ["p1a"])
        self.assertEqual(got.flinched, [])

    def test_fake_out_held_until_turn_2_fails(self):
        b = duel(mon("incineroar", "fakeout", "mudslap"), mon("arcanine", "mudslap"))
        self.assertEqual(exchange(b, "mudslap", "mudslap").order, ["p2a:mudslap", "p1a:mudslap"])
        got = exchange(b, "fakeout", "mudslap")
        self.assertEqual(got.order, ["p1a:fakeout", "p2a:mudslap"])
        self.assertEqual(got.failed, ["p1a"])

    def test_fake_out_vs_fake_out_the_faster_user_flinches_the_other(self):
        b = duel(mon("incineroar", "fakeout"), mon("arcanine", "fakeout"))
        got = exchange(b, "fakeout", "fakeout")
        self.assertEqual(got.order, ["p2a:fakeout", "p1a:fakeout"])
        self.assertEqual(got.flinched, ["p1a"])

    def test_doubles_fake_out_flinches_only_its_target(self):
        teams = {"p1": [mon("incineroar", "fakeout"), mon("kingambit", "mudslap")],
                 "p2": [mon("rillaboom", "mudslap"), mon("garchomp", "mudslap")]}
        got = Battle(teams, active=2).turn({"p1a": use("fakeout", "p2a"), "p1b": use("mudslap", "p2b"),
                                            "p2a": use("mudslap", "p1b"), "p2b": use("mudslap", "p1b")})
        self.assertEqual(got.order, ["p1a:fakeout", "p2b:mudslap", "p2a:mudslap", "p1b:mudslap"])
        self.assertEqual(got.flinched, ["p2a"])

    def test_a_replacement_can_fake_out_on_its_first_turn_out(self):
        b = Battle({"p1": [mon("incineroar", "quickattack", "mudslap")],
                    "p2": [mon("garchomp", "mudslap", hp=1), mon("arcanine", "fakeout")]})
        got = exchange(b, "quickattack", "mudslap")
        self.assertEqual(got.order, ["p1a:quickattack"])
        self.assertEqual(got.pending, ["p2a"])
        b.replace("p2a", 1)
        got = exchange(b, "mudslap", "fakeout")
        self.assertEqual(got.order, ["p2a:fakeout", "p1a:mudslap"])
        self.assertEqual(got.flinched, ["p1a"])

    def test_a_mon_that_switches_back_in_can_fake_out_again(self):
        b = Battle({"p1": [mon("incineroar", "fakeout", "mudslap"), mon("kingambit", "mudslap")],
                    "p2": [mon("garchomp", "mudslap")]})
        self.assertEqual(exchange(b, "fakeout", "mudslap").order, ["p1a:fakeout", "p2a:mudslap"])
        b.turn({"p1a": {"switch": 1}, "p2a": use("mudslap", "p1a")})
        b.turn({"p1a": {"switch": 0}, "p2a": use("mudslap", "p1a")})
        got = exchange(b, "fakeout", "mudslap")
        self.assertEqual(got.order, ["p1a:fakeout", "p2a:mudslap"])
        self.assertEqual(got.flinched, ["p2a"])
        self.assertEqual(got.failed, [])

    def test_a_mon_brought_in_by_replacement_can_fake_out_again(self):
        b = Battle({"p1": [mon("incineroar", "fakeout", "mudslap"), mon("kingambit", "mudslap", hp=1)],
                    "p2": [mon("garchomp", "protect", "quickattack", "mudslap")]})
        exchange(b, "fakeout", "protect")
        b.turn({"p1a": {"switch": 1}, "p2a": use("protect")})
        got = exchange(b, "mudslap", "quickattack")  # kingambit (1 HP) is KO'd
        self.assertEqual(got.order, ["p2a:quickattack"])
        self.assertEqual(got.pending, ["p1a"])
        b.replace("p1a", 0)
        got = exchange(b, "fakeout", "mudslap")
        self.assertEqual(got.order, ["p1a:fakeout", "p2a:mudslap"])
        self.assertEqual(got.flinched, ["p2a"])
        self.assertEqual(got.failed, [])

    def test_first_impression_fails_after_the_users_first_turn_out(self):
        b = duel(mon("incineroar", "firstimpression"), mon("garchomp", "mudslap"))
        got = exchange(b, "firstimpression", "mudslap")
        self.assertEqual(got.order, ["p1a:firstimpression", "p2a:mudslap"])
        self.assertEqual((got.failed, got.flinched), ([], []))
        self.assertEqual(exchange(b, "firstimpression", "mudslap").failed, ["p1a"])


class Protect(BattleTest):
    """https://www.smogon.com/dex/sv/moves/protect"""

    def test_blocks_fake_out_and_prevents_the_flinch(self):  # Protect +4 vs Fake Out +3
        b = duel(mon("incineroar", "fakeout"), mon("arcanine", "protect"))
        got = exchange(b, "fakeout", "protect")
        self.assertEqual(got.order, ["p2a:protect", "p1a:fakeout"])
        self.assertEqual(got.blocked, ["p1a"])
        self.assertFull(b, "p2:0")

    def test_only_lasts_the_turn_it_is_used(self):
        b = duel(mon("incineroar", "mudslap"), mon("dragapult", "protect", "mudslap"))
        got = exchange(b, "mudslap", "protect")
        self.assertEqual(got.order, ["p2a:protect", "p1a:mudslap"])
        self.assertEqual(got.blocked, ["p1a"])
        got = exchange(b, "mudslap", "mudslap")
        self.assertEqual(got.order, P2_FIRST)
        self.assertEqual(got.blocked, [])
        self.assertDamaged(b, "p2:0")


class Fainting(BattleTest):
    """A KO drops the fainted mon's queued move and asks for a replacement.
    https://bulbapedia.bulbagarden.net/wiki/Fainting  https://bulbapedia.bulbagarden.net/wiki/Target"""

    def test_ko_removes_the_queued_move_and_asks_for_a_replacement(self):
        b = Battle({"p1": [mon("incineroar", "quickattack")],
                    "p2": [mon("garchomp", "mudslap", hp=1), mon("kingambit", "mudslap")]})
        got = exchange(b, "quickattack", "mudslap")
        self.assertEqual(got.order, ["p1a:quickattack"])
        self.assertEqual(got.pending, ["p2a"])
        self.assertEqual(b.team_mon("p2:0").hp, 0)
        self.assertFull(b, "p1:0")
        self.assertIsNone(b.winner)

    def test_replacing_a_fainted_mon_puts_the_chosen_one_in_the_slot(self):
        b = Battle({"p1": [mon("incineroar", "quickattack")],
                    "p2": [mon("garchomp", "mudslap", hp=1), mon("kingambit", "mudslap")]})
        self.assertEqual(exchange(b, "quickattack", "mudslap").pending, ["p2a"])
        b.replace("p2a", 1)
        self.assertEqual(b.mon("p2a").species, "kingambit")
        self.assertIsNone(b.winner)

    def test_the_last_mon_fainting_ends_the_battle(self):
        b = duel(mon("incineroar", "quickattack"), mon("garchomp", "mudslap", hp=1))
        got = exchange(b, "quickattack", "mudslap")
        self.assertEqual(got.order, ["p1a:quickattack"])
        self.assertEqual(got.pending, [])
        self.assertEqual(b.winner, "p1")
        self.assertEqual(b.team_mon("p2:0").hp, 0)

    def test_a_mon_with_no_bench_leaves_its_doubles_slot_empty_and_the_battle_goes_on(self):
        teams = {"p1": [mon("dragapult", "quickattack", "mudslap"), mon("incineroar", "mudslap")],
                 "p2": [mon("garchomp", "mudslap", hp=1), mon("rillaboom", "mudslap")]}
        b = Battle(teams, active=2)
        got = b.turn({"p1a": use("quickattack", "p2a"), "p1b": use("mudslap", "p2b"),
                      "p2b": use("mudslap", "p1a"), "p2a": use("mudslap", "p1a")})
        self.assertEqual(got.order, ["p1a:quickattack", "p2b:mudslap", "p1b:mudslap"])
        self.assertEqual(got.pending, [])
        got = b.turn({"p1a": use("mudslap", "p2b"), "p1b": use("mudslap", "p2b"), "p2b": use("mudslap", "p1a")})
        self.assertEqual(got.order, ["p1a:mudslap", "p2b:mudslap", "p1b:mudslap"])
        self.assertIsNone(b.mon("p2a"))
        self.assertIsNone(b.winner)

    def test_doubles_a_move_aimed_at_a_fainted_foe_redirects_to_its_partner(self):
        teams = {"p1": [mon("dragapult", "quickattack"), mon("incineroar", "mudslap")],
                 "p2": [mon("garchomp", "mudslap", hp=1), mon("rillaboom", "mudslap")]}
        b = Battle(teams, active=2)
        got = b.turn({"p1a": use("quickattack", "p2a"), "p1b": use("mudslap", "p2a"),
                      "p2b": use("mudslap", "p1a"), "p2a": use("mudslap", "p1a")})
        self.assertEqual(got.order, ["p1a:quickattack", "p2b:mudslap", "p1b:mudslap"])
        self.assertDamaged(b, "p2:1")

    def test_doubles_a_move_aimed_at_a_fainted_ally_fails_instead_of_redirecting(self):
        teams = {"p1": [mon("kingambit", "mudslap", hp=1), mon("incineroar", "mudslap")],
                 "p2": [mon("garchomp", "quickattack", "mudslap"), mon("rillaboom", "mudslap")]}
        b = Battle(teams, active=2)
        got = b.turn({"p1a": use("mudslap", "p2a"), "p1b": use("mudslap", "p1a"),
                      "p2a": use("quickattack", "p1a"), "p2b": use("mudslap", "p1b")})
        self.assertEqual(got.order, ["p2a:quickattack", "p2b:mudslap", "p1b:mudslap"])
        self.assertFull(b, "p2:0", "p2:1")


class SpeedTies(unittest.TestCase):
    def test_tie_is_random_but_seeded(self):
        team = {"p1": [{"species": "garchomp", "moves": ["mudslap"]}],
                "p2": [{"species": "garchomp", "moves": ["mudslap"]}]}
        acts = {"p1a": {"move": "mudslap", "target": "p2a"}, "p2a": {"move": "mudslap", "target": "p1a"}}
        orders = {tuple(Battle(team, seed=s).turn(acts).order) for s in range(20)}
        self.assertEqual(len(orders), 2, "a speed tie should resolve both ways across seeds")
        self.assertEqual(Battle(team, seed=7).turn(acts).order, Battle(team, seed=7).turn(acts).order)


class SpreadDamage(unittest.TestCase):
    """The x0.75 spread modifier applies only while two or more targets are actually hit."""
    def _hp_lost(self, p2a_move):
        teams = {"p1": [{"species": "garchomp", "moves": ["rockslide"]}, {"species": "incineroar", "moves": ["tailwind"]}],
                 "p2": [{"species": "kingambit", "moves": ["protect", "tailwind"]},
                        {"species": "incineroar", "moves": ["tailwind"]}]}
        b = Battle(teams, active=2, rolls="max")
        b.turn({"p1a": {"move": "rockslide"}, "p1b": {"move": "tailwind"}, "p2a": {"move": p2a_move},
                "p2b": {"move": "tailwind"}})
        return b.team_mon("p2:1").max_hp - b.team_mon("p2:1").hp

    def test_two_targets_x075_and_one_target_x1(self):
        full = lambda spread: max(damage("garchomp", "rockslide", "incineroar", doubles=True, spread=spread)[0])
        self.assertEqual(self._hp_lost("tailwind"), full(True))
        self.assertEqual(self._hp_lost("protect"), full(False))
        self.assertGreater(full(False), full(True))


if __name__ == "__main__":
    unittest.main()
