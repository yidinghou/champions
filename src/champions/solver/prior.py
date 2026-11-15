"""Cheap 'likely move' ranking, used to cut each side's actions BEFORE building a payoff matrix.

Each Pokemon's actions are scored without simulating anything: a damaging move is worth the fraction of each
target's HP it is expected to remove (damage at an average roll x accuracy, capped at a KO), a switch is worth the
incoming Pokemon's best attack minus the best attack aimed at it, and a status move gets a small flat score.
We keep the top few moves, the best status move and the best switch per slot. It is a heuristic: it can drop
a move that only pays off later, so measure its error against an unfiltered solve.
"""
import itertools

from ..calc.damage import damage
from ..engine.actions import Move, Switch
from ..engine.pipeline.accuracy import final_accuracy
from ..engine.teams import moves_data
from .actions import slot_choices

AVG_ROLL = 92
STATUS_SCORE = 0.10
PRIORITY_BONUS = 0.10


def _targets(battle, user, choice, data):
    kind = data["target"]
    foes = [m for _, m in battle.sides[1 - user.side].alive_active()]
    ally = [m for _, m in battle.sides[user.side].alive_active() if m is not user]
    if kind in ("normal", "any"):
        t = battle.mon(*choice.target) if choice.target else None
        return [t] if t is not None and not t.fainted else []
    if kind == "allAdjacentFoes":
        return foes
    if kind == "allAdjacent":
        return foes + ally
    if kind == "adjacentAlly":
        return ally
    return []


def pressure(battle, user, choice):
    """Expected damage, as a fraction of target HP, of a move choice. Allies hit by a spread move count against it."""
    data = moves_data()[choice.move]
    if data["category"] == "Status" or not data["base_power"]:
        return None
    targets = _targets(battle, user, choice, data)
    spread = data["target"] in ("allAdjacentFoes", "allAdjacent") and len(targets) > 1
    total = 0.0
    for t in targets:
        acc = data["accuracy"]
        hit = 1.0 if acc is True or acc is None else min(1.0, final_accuracy(user, t, acc) / 100)
        frac = min(1.0, damage(user, t, data, roll=AVG_ROLL, spread=spread) / max(1, t.hp)) * hit
        total += -frac if t.side == user.side else frac
    return total + (PRIORITY_BONUS if data["priority"] > 0 else 0.0)


def _best_attack(battle, user, foes):
    best = 0.0
    for mv in user.moves:
        data = moves_data()[mv]
        if data["category"] == "Status" or not data["base_power"]:
            continue
        for t in foes:
            if data["target"] in ("normal", "any", "allAdjacentFoes", "allAdjacent"):
                best = max(best, min(1.0, damage(user, t, data, roll=AVG_ROLL) / max(1, t.hp)))
    return best


def _switch_score(battle, side, choice):
    me = battle.sides[side].team[choice.to]
    foes = [m for _, m in battle.sides[1 - side].alive_active()]
    threat = max((_best_attack(battle, f, [me]) for f in foes), default=0.0)
    return _best_attack(battle, me, foes) - threat


def candidate_slot_choices(battle, side, moves=2, status=1, switches=1):
    """{slot: [choices]}: the top `moves` damaging moves, the best `status` status moves and the best `switches`
    switches per slot. Slots with no damaging or status candidate keep all their choices."""
    out = {}
    for slot, choices in slot_choices(battle, side).items():
        user = battle.sides[side].mon_at(slot)
        dmg, stat, sw = [], [], []
        for c in choices:
            if isinstance(c, Switch):
                sw.append((_switch_score(battle, side, c), c))
            else:
                p = pressure(battle, user, c)
                (stat if p is None else dmg).append((STATUS_SCORE if p is None else p, c))
        rank = lambda items, n: [c for _, c in sorted(items, key=lambda t: -t[0])[:n]]
        picked = rank(dmg, moves) + rank(stat, status) + rank(sw, switches)
        out[slot] = picked or choices
    return out


def candidate_joint_actions(battle, side, **kw):
    """Joint actions built from candidate_slot_choices (two slots may not switch to the same Pokemon)."""
    per_slot = candidate_slot_choices(battle, side, **kw)
    out = []
    for combo in itertools.product(*per_slot.values()):
        targets = [c.to for c in combo if isinstance(c, Switch)]
        if len(targets) == len(set(targets)):
            out.append(list(combo))
    return out
