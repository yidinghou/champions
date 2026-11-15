"""Turn order and end-of-turn. Actions sort by kind (switch, Mega, move), priority, then Speed.

Priority is read when the turn starts; Speed is re-read after every action (`resort`). Exact ties are broken with
the seeded RNG, once.
"""
from __future__ import annotations

from collections import namedtuple

from . import arena, screens, status, volatiles
from .actions import Switch
from .hooks import fire
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
    s *= arena.speed_multiplier(battle, mon)
    if mon.item == "choicescarf":
        s = s * 3 // 2
    elif mon.item == "ironball":
        s //= 2
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
    Weather runs first (sand damage, Rain Dish, Ice Body), then Grassy Terrain healing; the terrain counts
    down in tick_field. TODO(residuals): items, screens and Tailwind countdowns."""
    arena.weather_residual(battle)
    arena.terrain_heal(battle)
    for m in sorted((m for s in battle.sides for _, m in s.alive_active() if m.item), key=lambda m: -speed(battle, m)):
        fire(battle, "on_residual", m, [f"item:{m.item}"])          # Leftovers
    mons = [m for s in battle.sides for _, m in s.alive_active()]
    mons.sort(key=lambda m: -speed(battle, m))
    for m in mons:
        if m.fainted:
            continue                                  # fainted to the sandstorm
        dmg = status.residual_damage(m)
        if dmg:
            m.take(dmg)
        if not m.fainted:
            status.tick_yawn(battle, m)
        volatiles.residual(battle, m)
        if m.ability == "speedboost" and m.turns_out > 0 and not m.fainted:
            m.boost("spe", 1, cause="speedboost")
        m.volatiles.pop("flinch", None)
        m.volatiles.pop("protect", None)
        m.volatiles.pop("followme", None)
        m.volatiles.pop("ragepowder", None)
    screens.tick(battle)
    tick_field(battle)
    arena.terrain_tick(battle)


def resort(battle, remaining, chosen_by):
    """Gen 8+ ordering: Speed is re-read after every action, so Tailwind, Trick Room or paralysis set mid-turn
    changes who moves next. Stable: actions that tie keep the order the seeded tie-break gave them."""
    reverse = bool(battle.arena.get("trick_room"))
    fresh = []
    for a in remaining:
        mon = chosen_by[(a.choice.side, a.choice.slot)]
        fresh.append(a._replace(speed=speed(battle, mon)))
    fresh.sort(key=lambda a: (a.kind, -a.priority, a.speed if reverse else -a.speed))
    return fresh
