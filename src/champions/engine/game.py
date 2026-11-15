"""The turn loop. A game is a function of (teams, seed, choices): same inputs, same log."""
from __future__ import annotations

from . import handlers  # noqa: F401  (registers handlers)
from .actions import Move, Switch
from .effects_table import check_ability, move_effects
from .items import check_item, update_all
from .errors import Unsupported
from .hooks import fire
from .pipeline import run_move
from . import mega, volatiles
from .teams import build_battle, moves_data
from .turn import order_actions, resort, run_residuals, speed

MAX_TURNS = 100


def validate_teams(battle):
    for side in battle.sides:
        for m in side.team:
            check_ability(m.ability)
            check_item(m.item)
            form = mega.form_for(m)
            if form:
                check_ability(mega.form_ability(form))      # a Mega form with an unmodeled ability is rejected up front
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
    update_all(b)                                            # seeds, herbs and berries that are ready on entry
    return b


def send_in_ability(battle, mon):
    """The mon's ability starts (on entry, or when a Mega Evolution gives it a new one)."""
    fire(battle, "on_switch_in", mon, [f"ability:{mon.ability}"])


def send_in(battle, mon):
    mon.turns_out = 0
    send_in_ability(battle, mon)


def legal_choices(battle, side):
    """Every Move and Switch the side could choose, per active slot (simple: all foes as targets)."""
    out = []
    s = battle.sides[side]
    for slot, mon in s.alive_active():
        foes = battle.sides[1 - side].alive_active()
        for mv in mon.moves:
            if not volatiles.can_choose(mon, mv, moves_data()[mv]) or not volatiles.choice_allows(mon, mv):
                continue
            for fslot, _ in foes or [(0, None)]:
                bench = [i for i, m in enumerate(s.team) if not m.fainted and i not in s.active]
                pivots = bench if move_effects(mv).get("pivot") and len(bench) > 1 else [None]    # name the replacement
                for pv in pivots:
                    out.append(Move(side, slot, mv, (1 - side, fslot), pivot_to=pv))
                    if mega.can_evolve(battle, mon):
                        out.append(Move(side, slot, mv, (1 - side, fslot), mega=True, pivot_to=pv))
        for i, m in enumerate(s.team):
            if not m.fainted and i not in s.active and not volatiles.is_trapped(mon, battle):
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
            if volatiles.is_trapped(mon, battle):
                raise ValueError(f"{mon.species} is trapped and cannot switch")
            continue
        if c.move not in mon.moves:
            raise ValueError(f"{mon.species} does not know {c.move}")
        move_effects(c.move)  # Unsupported if not modeled
        if c.pivot_to is not None:
            s = battle.sides[c.side]
            if not 0 <= c.pivot_to < len(s.team) or s.team[c.pivot_to].fainted or c.pivot_to in s.active:
                raise ValueError(f"illegal pivot target {c.pivot_to}")
        if not volatiles.choice_allows(mon, c.move):
            raise ValueError(f"{mon.species} is locked into {mon.volatiles['choicelock']} by its Choice item")
    mega.check_choice(battle, choices)


def run_switch(battle, act, cause=None, passing=None):
    """Swap the mon in a slot. cause: the move that made it happen (log only). passing: Baton Pass's payload,
    {"stages": ..., "volatiles": ...}, given to the replacement before its entry effects run."""
    s = battle.sides[act.side]
    old = s.mon_at(act.slot)
    if old is not None:
        if old.ability == "regenerator" and not old.fainted:
            old.heal(old.max_hp // 3)
        old.clear_on_switch()
    s.active[act.slot] = act.to
    new = s.team[act.to]
    battle.log_event("switch", mon=new.ref, slot=act.slot, cause=cause)
    if passing:
        new.stages.update(passing["stages"])
        for name, value in passing["volatiles"].items():
            new.add_volatile(name, value)
    send_in(battle, new)
    update_all(battle)


def run_action(battle, act):
    mon = battle.mon(act.side, act.slot)
    if isinstance(act, Switch):
        return run_switch(battle, act)
    target = tuple(act.target) if act.target else None
    move_id = volatiles.forced_move(mon, act.move)
    run_move(battle, mon, move_id, target, getattr(act, "pivot_to", None))
    if "protect" not in move_effects(act.move):
        mon.volatiles.pop("protect_chain", None)      # the Protect chain breaks on any other move
    if battle.sides[mon.side].mon_at(act.slot) is mon:        # not if an Eject Button or Red Card moved it out
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
    validate(battle, choices)                         # refuse bad choices before anything changes
    battle.turn += 1
    battle.arena["moved"] = []
    battle.log_event("turn", number=battle.turn)
    chosen_by = {(c.side, c.slot): battle.mon(c.side, c.slot) for c in choices}
    queue = order_actions(battle, choices)
    while queue:
        queue = resort(battle, queue, chosen_by)      # Speed is re-read after every action
        act = queue.pop(0)
        c = act.choice
        mon = battle.mon(c.side, c.slot)
        if mon is None or mon.fainted:
            continue                                  # KO'd earlier this turn: loses its action
        if mon is not chosen_by[(c.side, c.slot)]:
            continue                                  # switched out earlier this turn (Eject Button, Red Card): its choice lapses
        if act.kind == 1:
            mega.evolve(battle, mon)
            update_all(battle)
            continue                                  # its move comes later in the queue
        run_action(battle, c)
        update_all(battle)
        if check_winner(battle) is not None:
            return battle
    run_residuals(battle)
    update_all(battle)
    request_replacements(battle)
    check_winner(battle)
    return battle


def run_to_end(teams, seed, policy, format="doubles", max_turns=MAX_TURNS):
    b = start(teams, seed, format)
    while b.winner is None and b.turn < max_turns:
        play_turn(b, policy(b))
    return b
