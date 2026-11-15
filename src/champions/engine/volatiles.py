"""Volatile status: confusion, Taunt, Encore, Disable, Leech Seed and trapping.

They live in `mon.volatiles` (name -> JSON-safe value), are separate from the major status slot, and are
cleared when the mon leaves the field or faints. Re-applying one that is already there changes nothing.
The numbers are Showdown's; Champions may differ (flagged `verify` in the catalogue).
"""
from __future__ import annotations

from ..calc.damage import damage
from . import arena

CONFUSION_TURNS = (2, 5)
CONFUSION_SELF_HIT_PCT = 100 / 3
TAUNT_TURNS = 3
ENCORE_TURNS = 3
DISABLE_TURNS = 4
SELF_HIT = {"base_power": 40, "category": "Physical", "type": None}     # typeless, never a crit


def fail(battle, mon, move_id, reason):
    battle.log_event("fail", mon=mon.ref, move=move_id, reason=reason)
    return False


def apply(battle, target, name, user, move_id, announce=True):
    """Put a volatile on `target`. Returns True if it took hold; logs a `fail`/`immune` otherwise (if announce)."""
    if target.fainted:
        return False
    if name in target.volatiles:
        return announce and fail(battle, target, move_id, f"already_{name}")
    reason = arena.blocks_volatile(battle, target, name)
    if reason:
        return announce and fail(battle, target, move_id, reason)
    if name == "confusion":
        target.add_volatile(name, battle.rng.randint(*CONFUSION_TURNS, "confusion_turns"))
    elif name == "taunt":
        target.add_volatile(name, TAUNT_TURNS)
    elif name in ("encore", "disable"):
        if not target.last_move:
            return fail(battle, target, move_id, "no_last_move")
        target.add_volatile(name, {"move": target.last_move,
                                   "turns": ENCORE_TURNS if name == "encore" else DISABLE_TURNS})
    elif name == "leechseed":
        if "grass" in target.types:
            battle.log_event("immune", mon=target.ref, move=move_id)
            return False
        target.add_volatile(name, {"by": [user.side, battle.sides[user.side].active.index(user.idx)]})
    else:
        raise ValueError(f"unknown volatile {name!r}")
    return True


def trap(battle, target, user, move_id, turns, dmg):
    """Fire Spin (4-5 turns, 1/8 per turn) and Mean Look (no timer, no damage). Ghost types are immune."""
    if target.fainted or "trapped" in target.volatiles:
        return False
    if "ghost" in target.types:
        if not dmg:                       # Mean Look says so; a damaging trap move just does not trap
            battle.log_event("immune", mon=target.ref, move=move_id)
        return False
    n = battle.rng.randint(*turns, "trap_turns") if turns else None
    info = {"by": user.ref, "turns": n, "dmg": dmg}
    if user.item == "bindingband":
        info["band"] = True                  # 1/6 max HP a turn instead of 1/8
    target.add_volatile("trapped", info)
    return True


def before_move(battle, mon, move_id, move):
    """Disable, Taunt and confusion can stop a move. Returns a reason if the mon cannot act, else None."""
    dis = mon.volatiles.get("disable")
    if dis and dis["move"] == move_id:
        return "disabled"
    if mon.volatiles.get("taunt") and move["category"] == "Status":
        return "taunted"
    if "confusion" in mon.volatiles:
        mon.volatiles["confusion"] -= 1
        if mon.volatiles["confusion"] <= 0:
            mon.remove_volatile("confusion")           # snaps out of it and acts
        elif battle.rng.chance(CONFUSION_SELF_HIT_PCT, "confusion_hit"):
            mon.take(damage(mon, mon, SELF_HIT, crit=False, roll=battle.rng.randint(85, 100, "damage_roll")))
            return "confused"
    return None


def forced_move(mon, move_id):
    """Encore overrides the chosen move with the last one used."""
    enc = mon.volatiles.get("encore")
    return enc["move"] if enc else move_id


def choice_allows(mon, move_id):
    """Choice Scarf locks the holder into the first move it uses (until it switches out or loses the item)."""
    lock = mon.volatiles.get("choicelock")
    return not (lock and mon.item == "choicescarf" and move_id != lock)


def can_choose(mon, move_id, move):
    """Would the engine let this mon use this move now? (Used for legal choices, not for validation.)"""
    enc = mon.volatiles.get("encore")
    if enc:
        return move_id == enc["move"]
    dis = mon.volatiles.get("disable")
    if dis and dis["move"] == move_id:
        return False
    return not (mon.volatiles.get("taunt") and move["category"] == "Status")


def is_trapped(mon):
    return "trapped" in mon.volatiles and "ghost" not in mon.types and mon.item != "shedshell"


def _trapper_present(battle, ref):
    for side in battle.sides:
        for slot, i in enumerate(side.active):
            if i is not None and side.team[i].ref == ref and not side.team[i].fainted:
                return True
    return False


def residual(battle, mon):
    """End of turn: Leech Seed drain, trapping damage, then the Taunt/Encore/Disable timers."""
    seed = mon.volatiles.get("leechseed")
    if seed and not mon.fainted:
        dealt = mon.take(max(1, mon.max_hp // 8))
        side, slot = seed["by"]
        seeder = battle.mon(side, slot)
        if seeder is not None and not seeder.fainted:
            seeder.heal(dealt * 5324 // 4096 if seeder.item == "bigroot" else dealt)
    tr = mon.volatiles.get("trapped")
    if tr and not mon.fainted:
        if not _trapper_present(battle, tr["by"]):
            mon.remove_volatile("trapped")
        else:
            if tr["dmg"]:
                mon.take(max(1, mon.max_hp // (6 if tr.get("band") else 8)))
            if tr["turns"] is not None and not mon.fainted:
                tr["turns"] -= 1
                if tr["turns"] <= 0:
                    mon.remove_volatile("trapped")
    for name in ("taunt", "encore", "disable"):
        v = mon.volatiles.get(name)
        if v is None or mon.fainted:
            continue
        if isinstance(v, dict):
            v["turns"] -= 1
            done = v["turns"] <= 0
        else:
            mon.volatiles[name] = v - 1
            done = v - 1 <= 0
        if done:
            mon.remove_volatile(name)
