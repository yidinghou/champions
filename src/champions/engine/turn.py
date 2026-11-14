"""Turn order and end-of-turn. Actions sort by kind (switch, Mega, move), priority, then Speed.

Priority and Speed are read when the turn starts. Exact ties are broken with the seeded RNG.
"""
from __future__ import annotations

from collections import namedtuple

from . import status, volatiles
from .actions import Switch
from .handlers.field import tick_field
from .teams import moves_data

Action = namedtuple("Action", "kind choice priority speed")
SWITCH, MEGA, MOVE = 0, 1, 2


def speed(battle, mon):
    s = mon.stats["spe"]
    st = mon.stages["spe"]
    s = int(s * ((2 + st) / 2 if st >= 0 else 2 / (2 - st)))
    if mon.status == "par":
        s //= 2
    if battle.sides[mon.side].conditions.get("tailwind"):
        s *= 2
    return s


def order_actions(battle, choices):
    actions = []
    for c in choices:
        mon = battle.mon(c.side, c.slot)
        sp = speed(battle, mon)
        if isinstance(c, Switch):
            actions.append(Action(SWITCH, c, 0, sp))
            continue
        if c.mega:
            actions.append(Action(MEGA, c, 0, sp))
        actions.append(Action(MOVE, c, moves_data()[c.move]["priority"], sp))
    reverse = bool(battle.arena.get("trick_room"))   # Trick Room reverses Speed, not priority

    def key(a):
        return (a.kind, -a.priority, a.speed if reverse else -a.speed)

    actions.sort(key=key)
    out, i = [], 0
    while i < len(actions):                       # break exact ties with the seeded RNG
        j = i
        while j < len(actions) and key(actions[j]) == key(actions[i]):
            j += 1
        group = actions[i:j]
        while len(group) > 1:
            out.append(group.pop(battle.rng.randint(0, len(group) - 1, "speed_tie")))
        out += group
        i = j
    return out


def run_residuals(battle):
    """End of turn, in Speed order. Burn, poison and Toxic damage, then clears flinch.
    TODO(residuals): weather, terrain, items, screens and Tailwind countdowns."""
    mons = [m for s in battle.sides for _, m in s.alive_active()]
    mons.sort(key=lambda m: -speed(battle, m))
    for m in mons:
        dmg = status.residual_damage(m)
        if dmg:
            m.take(dmg)
        if not m.fainted:
            status.tick_yawn(battle, m)
        volatiles.residual(battle, m)
        m.volatiles.pop("flinch", None)
        m.volatiles.pop("protect", None)
    tick_field(battle)
