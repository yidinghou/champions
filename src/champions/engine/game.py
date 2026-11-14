"""The turn loop. A game is a function of (teams, seed, choices): same inputs, same log."""
from __future__ import annotations

from . import handlers  # noqa: F401  (registers handlers)
from .actions import Move, Switch
from .effects_table import check_ability, move_effects
from .errors import Unsupported
from .hooks import fire
from .pipeline import run_move
from .teams import build_battle
from .turn import order_actions, run_residuals, speed

MAX_TURNS = 100


def validate_teams(battle):
    for side in battle.sides:
        for m in side.team:
            check_ability(m.ability)
            for mv in m.moves:
                move_effects(mv)


def start(teams, seed=0, format="doubles", rng=None):
    b = build_battle(teams, seed, format, rng)
    validate_teams(b)
    b.log_event("start", format=format, seed=seed)
    b.arena["moved"] = []
    entering = [m for s in b.sides for _, m in s.alive_active()]
    for m in sorted(entering, key=lambda m: -speed(b, m)):   # TODO: random speed ties
        send_in(b, m)
    return b


def send_in(battle, mon):
    mon.turns_out = 0
    fire(battle, "on_switch_in", mon, [f"ability:{mon.ability}"])


def legal_choices(battle, side):
    """Every Move and Switch the side could choose, per active slot (simple: all foes as targets)."""
    out = []
    s = battle.sides[side]
    for slot, mon in s.alive_active():
        foes = battle.sides[1 - side].alive_active()
        for mv in mon.moves:
            for fslot, _ in foes or [(0, None)]:
                out.append(Move(side, slot, mv, (1 - side, fslot)))
        for i, m in enumerate(s.team):
            if not m.fainted and i not in s.active:
                out.append(Switch(side, slot, i))
    return out


def validate(battle, choices):
    seen = set()
    for c in choices:
        mon = battle.mon(c.side, c.slot)
        if mon is None or mon.fainted:
            raise ValueError(f"no active mon at side {c.side} slot {c.slot}")
        if (c.side, c.slot) in seen:
            raise ValueError(f"two choices for side {c.side} slot {c.slot}")
        seen.add((c.side, c.slot))
        if isinstance(c, Switch):
            s = battle.sides[c.side]
            if not 0 <= c.to < len(s.team) or s.team[c.to].fainted or c.to in s.active:
                raise ValueError(f"illegal switch to {c.to}")
            continue
        if c.move not in mon.moves:
            raise ValueError(f"{mon.species} does not know {c.move}")
        move_effects(c.move)  # Unsupported if not modeled
        if c.mega:
            raise Unsupported("Mega Evolution is not modeled yet")


def run_switch(battle, act):
    s = battle.sides[act.side]
    old = s.mon_at(act.slot)
    if old is not None:
        old.clear_on_switch()
    s.active[act.slot] = act.to
    new = s.team[act.to]
    battle.log_event("switch", mon=new.ref, slot=act.slot)
    send_in(battle, new)


def run_action(battle, act):
    mon = battle.mon(act.side, act.slot)
    if isinstance(act, Switch):
        return run_switch(battle, act)
    target = tuple(act.target) if act.target else None
    run_move(battle, mon, act.move, target)
    if "protect" not in move_effects(act.move):
        mon.volatiles.pop("protect_chain", None)      # the Protect chain breaks on any other move
    mon.turns_out += 1
    battle.arena["moved"].append(mon.ref)


def check_winner(battle):
    alive = [s.has_living() for s in battle.sides]
    if all(alive):
        return None
    battle.winner = -1 if not any(alive) else alive.index(True)
    battle.log_event("win", side=battle.winner)
    return battle.winner


def request_replacements(battle):
    """KO'd actives are replaced by the first living bench mon (TODO: let the policy choose)."""
    for si, s in enumerate(battle.sides):
        for slot, idx in enumerate(s.active):
            if idx is not None and s.team[idx].fainted:
                bench = [i for i, m in enumerate(s.team) if not m.fainted and i not in s.active]
                if bench:
                    run_switch(battle, Switch(si, slot, bench[0]))
                else:
                    s.active[slot] = None


def play_turn(battle, choices):
    battle.turn += 1
    battle.arena["moved"] = []
    battle.log_event("turn", number=battle.turn)
    validate(battle, choices)
    for act in order_actions(battle, choices):
        c = act.choice
        mon = battle.mon(c.side, c.slot)
        if mon is None or mon.fainted:
            continue                                  # KO'd earlier this turn: loses its action
        if act.kind == 1:
            battle.log_event("mega", mon=mon.ref)
            continue                                  # TODO(mega): form change
        run_action(battle, c)
        if check_winner(battle) is not None:
            return battle
    run_residuals(battle)
    request_replacements(battle)
    check_winner(battle)
    return battle


def run_to_end(teams, seed, policy, format="doubles", max_turns=MAX_TURNS):
    b = start(teams, seed, format)
    while b.winner is None and b.turn < max_turns:
        play_turn(b, policy(b))
    return b
