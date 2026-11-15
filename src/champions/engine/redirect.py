"""Redirection and absorbing: who a single-target move really hits, and abilities that eat a move's type.

In doubles a single-target move ("normal" or "any") can be pulled to another mon before anything else:
  1. Follow Me / Rage Powder: a foe that used it this turn takes the move. If several did, the last to use it wins.
     Rage Powder does not work on Grass types or Overcoat holders.
  2. Lightning Rod (Electric) / Storm Drain (Water): any other mon on the field that has it takes the move, even
     an ally's; the fastest holder wins.
Spread and self moves are never redirected. Following the same rule as Showdown, a redirected move can be one the
user aimed at its own ally.
Absorbing: an Electric, Water or Grass move at a holder of Lightning Rod, Storm Drain, Sap Sipper, Motor Drive,
Volt Absorb or Water Absorb does nothing and boosts or heals the holder. Numbers are Showdown's gen 9 values.
TODO(redirect): Stalwart and Propeller Tail, Snipe Shot, Spotlight, Mold Breaker, Wide Guard, Quick Guard.
"""
from __future__ import annotations

from .stages import change_stat

REDIRECT_MOVES = ("followme", "ragepowder")
REDIRECT_ABILITY = {"Electric": "lightningrod", "Water": "stormdrain"}
SINGLE_TARGET = ("normal", "any")
ABSORB = {                         # ability -> (move type, what it does)
    "lightningrod": ("Electric", ("boost", "spa")), "stormdrain": ("Water", ("boost", "spa")),
    "sapsipper": ("Grass", ("boost", "atk")), "motordrive": ("Electric", ("boost", "spe")),
    "voltabsorb": ("Electric", ("heal", 4)), "waterabsorb": ("Water", ("heal", 4)),
}


def _powder_immune(user):
    return "grass" in user.types or user.ability == "overcoat"


def redirect_target(battle, user, move, move_id, target):
    """The mon a single-target move actually hits (`target` if nothing redirects it)."""
    if battle.format != "doubles":
        return target
    foes = [m for _, m in battle.sides[1 - user.side].alive_active()]
    drawn = [(m.volatiles[k], k, m) for m in foes for k in REDIRECT_MOVES if k in m.volatiles]
    if "ragepowder" in {k for _, k, _ in drawn} and _powder_immune(user):
        drawn = [d for d in drawn if d[1] != "ragepowder"]
    if drawn:
        _, cause, m = max(drawn, key=lambda d: d[0])
        return _log(battle, m, target, move_id, cause)
    ability = REDIRECT_ABILITY.get(move["type"])
    if ability:
        from .turn import speed
        holders = [m for s in battle.sides for _, m in s.alive_active() if m is not user and m.ability == ability]
        if holders:
            m = max(holders, key=lambda h: speed(battle, h))
            return _log(battle, m, target, move_id, ability)
    return target


def _log(battle, redirector, original, move_id, cause):
    if redirector is not original:
        battle.log_event("redirect", mon=redirector.ref, was=original.ref, move=move_id, cause=cause)
    return redirector


def absorbs(target, move):
    """(kind, arg) if `target`'s ability eats this move, else None."""
    entry = ABSORB.get(target.ability)
    return entry[1] if entry and move["type"] == entry[0] else None


def absorb(battle, target, move_id, effect):
    battle.log_event("immune", mon=target.ref, move=move_id, ability=target.ability)
    kind, arg = effect
    if kind == "boost":
        change_stat(battle, target, arg, 1, source=target, cause="self")
    else:
        target.heal(max(1, target.max_hp // arg))
