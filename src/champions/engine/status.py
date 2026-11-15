"""Major status: applying it, the numbers that drive it, and what it does at the start of a move.

The numbers below are Showdown's. Champions may differ (the plan's open question 1), so each is
named once here and flagged `verify` in the catalogue until checked.
"""
from __future__ import annotations

from . import arena

SLEEP_TURNS = (1, 3)         # verify: Champions sleep length
FREEZE_THAW_PCT = 20         # verify: Champions freeze thaw chance per turn
STATUS_NAMES = {"brn": "burned", "psn": "poisoned", "tox": "badly poisoned", "par": "paralyzed",
                "slp": "asleep", "frz": "frozen"}
# Types that cannot get a status.
IMMUNE_TYPES = {"brn": ("fire",), "psn": ("poison", "steel"), "tox": ("poison", "steel"),
                "par": ("electric",), "frz": ("ice",)}
# End-of-turn damage as (numerator, denominator) of max HP.
RESIDUAL = {"brn": (1, 16), "psn": (1, 8)}
TOXIC_CAP = 15
REST_TURNS = 3               # sleeps through 2 turns, wakes on the 3rd attempt
YAWN_TURNS = 2               # sleep arrives at the end of the next turn


def try_set_status(battle, target, status, user=None, move_id=None, announce=True):
    """Give `target` a major status if it can have one. Returns True if it did.

    A failure is logged (`fail`/`immune`) only when `announce` is set, which is for status moves.
    A secondary effect that cannot apply stays silent.
    """
    if target.fainted:
        return False
    if target.status:
        if announce:
            battle.log_event("fail", mon=target.ref, move=move_id, reason="already_status")
        return False
    reason = arena.blocks_status(battle, target, status)
    if reason:
        if announce:
            battle.log_event("fail", mon=target.ref, move=move_id, reason=reason)
        return False
    if any(t in IMMUNE_TYPES.get(status, ()) for t in target.types):
        if announce:
            battle.log_event("immune", mon=target.ref, move=move_id)
        return False
    turns = battle.rng.randint(*SLEEP_TURNS, "sleep_turns") if status == "slp" else 0
    target.set_status(status, turns)
    return True


def before_move(battle, mon, move):
    """Sleep and freeze can stop a move. Returns a reason string if the mon cannot act, else None."""
    if mon.status == "slp":
        mon.status_turns -= 1
        if mon.status_turns <= 0:
            mon.cure_status()                      # wakes up and acts this turn
            return None
        return "asleep"
    if mon.status == "frz":
        if move.get("thaws") or battle.rng.chance(FREEZE_THAW_PCT, "thaw"):
            mon.cure_status()
            return None
        return "frozen"
    return None


def residual_damage(mon):
    """HP lost to burn, poison or Toxic at end of turn (0 if none). Toxic grows by 1/16 each turn."""
    if mon.ability == "magicguard":
        if mon.status == "tox":
            mon.status_turns = min(mon.status_turns + 1, TOXIC_CAP)    # the counter still ticks
        return 0
    if mon.status in RESIDUAL:
        n, d = RESIDUAL[mon.status]
        return max(1, mon.max_hp * n // d)
    if mon.status == "tox":
        mon.status_turns = min(mon.status_turns + 1, TOXIC_CAP)
        return max(1, mon.max_hp // 16) * mon.status_turns
    return 0


def tick_yawn(battle, mon):
    """End of turn: a yawning mon falls asleep once its counter runs out (if it has no status by then)."""
    if "yawn" not in mon.volatiles:
        return
    mon.volatiles["yawn"] -= 1
    if mon.volatiles["yawn"] <= 0:
        del mon.volatiles["yawn"]
        try_set_status(battle, mon, "slp", announce=False)
