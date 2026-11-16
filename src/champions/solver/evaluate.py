"""Score a battle from side 0's view, -1..1.

A win or loss is exact (+1 / -1, draw 0). Otherwise a hand-built static evaluation: for each side a sum of
terms (material, status, stat stages, speed control, side conditions, threat), the difference of the two sums
squashed with tanh. Every weight lives in W so it can be tuned or fitted later (see scripts/eval_audit.py).

Terms, each as a fraction of "one healthy Pokemon" (so a full Pokemon up is worth about 1 + ALIVE):
  material  HP fraction of each living Pokemon, plus a flat bonus per living Pokemon
  status    sleep, freeze, paralysis, burn, poison, toxic and the volatiles that cripple a slot, scaled by HP left
  stages    attack / speed / bulk stages on the Pokemon in play, scaled by HP left
  speed     which active Pokemon move first (reversed by Trick Room), plus Tailwind
  field     Reflect, Light Screen, Aurora Veil, Tailwind on a side
  threat    how much each active Pokemon can take off the opposing actives next turn, and whether it can KO
            first. This is what lets a one-turn search see tempo (Fake Out, Protect, switching) at all.
"""
import math

from ..calc.damage import damage
from ..engine.teams import moves_data
from ..engine.turn import speed

W = {
    "hp": 1.0,              # per living Pokemon, times its HP fraction
    "alive": 0.35,          # per living Pokemon (a 3v2 beats 2v2 at equal HP)
    "status": {"slp": 0.45, "frz": 0.5, "par": 0.25, "brn": 0.25, "psn": 0.12, "tox": 0.2},
    "brn_physical": 0.15,   # extra burn penalty on a mon whose Atk beats its SpA
    "par_fast": 0.10,       # extra paralysis penalty on a fast mon
    "volatile": {"confusion": 0.10, "taunt": 0.08, "encore": 0.12, "disable": 0.05, "leechseed": 0.10,
                 "trapped": 0.08, "yawn": 0.10},
    "stage_main": 0.10,     # per stage on the stronger attacking stat
    "stage_off": 0.02,      # per stage on the weaker one
    "stage_spe": 0.06,
    "stage_bulk": 0.04,
    "speed": 0.25,          # all active pairs move first (+) vs all move second (-)
    "tailwind": 0.12,
    "screen": 0.10,
    "threat": 0.45,         # per full-HP of damage an active can do to the opposing actives
    "ko": 0.20,             # extra for each active that can KO an opposing active this turn
    "second": 0.5,          # threat weight kept when a faster foe can KO the attacker first
    "scale": 1.8,           # tanh scale: a lead of this many "healthy Pokemon" scores about +0.76
}

AVG_ROLL = 92
_SCREENS = ("reflect", "lightscreen", "auroraveil")
_cache = {}


def _hit_frac(user, target):
    """Best expected damage of any of user's moves on target, as a fraction of target's current HP (cached)."""
    best = 0.0
    for mv in user.moves:
        data = moves_data()[mv]
        if data["category"] == "Status" or not data["base_power"]:
            continue
        k = (user.species, tuple(user.types), user.stats["atk"], user.stats["spa"], user.stages["atk"],
             user.stages["spa"], user.status, user.ability, target.species, tuple(target.types),
             target.stats["def"], target.stats["spd"], target.stages["def"], target.stages["spd"], mv)
        d = _cache.get(k)
        if d is None:
            if len(_cache) > 200000:
                _cache.clear()
            d = _cache[k] = damage(user, target, data, roll=AVG_ROLL)
            acc = data["accuracy"]
            if acc is not True and acc is not None:
                d = _cache[k] = d * min(1.0, acc / 100)
        best = max(best, d)
    return min(1.0, best / max(1, target.hp))


def _hp(m):
    return m.hp / m.max_hp


def _material(side):
    return sum(W["hp"] * _hp(m) + W["alive"] for m in side.team if not m.fainted)


def _mon_penalty(m):
    """Status and volatile penalties, in 'healthy Pokemon', scaled by HP left."""
    pen = 0.0
    if m.status:
        pen += W["status"].get(m.status, 0.1)
        if m.status == "brn" and m.stats["atk"] > m.stats["spa"]:
            pen += W["brn_physical"]
        if m.status == "par" and m.stats["spe"] >= 100:
            pen += W["par_fast"]
    for v, w in W["volatile"].items():
        if v in m.volatiles:
            pen += w
    return pen * _hp(m)


def _mon_stages(m):
    st = m.stages
    main, off = ("atk", "spa") if m.stats["atk"] >= m.stats["spa"] else ("spa", "atk")
    v = W["stage_main"] * st[main] + W["stage_off"] * st[off] + W["stage_spe"] * st["spe"]
    v += W["stage_bulk"] * (st["def"] + st["spd"]) / 2
    return v * _hp(m)


def _condition(side, key):
    v = side.conditions.get(key)
    return 1.0 if v else 0.0


def _speed_term(b, mine, theirs):
    """+1 if every active of ours moves first, -1 if every one moves second."""
    if not mine or not theirs:
        return 0.0
    tr = bool(b.arena.get("trick_room"))
    tot = 0.0
    for a in mine:
        sa = speed(b, a)
        for f in theirs:
            sf = speed(b, f)
            if sa == sf:
                continue
            tot += 1.0 if (sa > sf) != tr else -1.0
    return tot / (len(mine) * len(theirs))


def _threat(b, side_i):
    """Pressure the side's actives put on the opposing actives, in 'healthy Pokemon'.

    Each attacker aims at the foe it hurts most (weighted toward healthy targets). Its pressure is the damage
    fraction times the target's HP share, plus a bonus if it can KO. Halved if a faster foe can KO it first."""
    me = [m for _, m in b.sides[side_i].alive_active()]
    foes = [m for _, m in b.sides[1 - side_i].alive_active()]
    tr = bool(b.arena.get("trick_room"))
    total = 0.0
    for a in me:
        tgt = max(foes, key=lambda f: _hit_frac(a, f) * (0.5 + _hp(f)), default=None)
        if tgt is None:
            continue
        frac = _hit_frac(a, tgt)
        sa = speed(b, a)
        outsped_and_ko = any(_hit_frac(f, a) >= 1.0 and ((speed(b, f) > sa) != tr) for f in foes)
        w = W["second"] if outsped_and_ko else 1.0
        total += w * (W["threat"] * frac * (0.5 + _hp(tgt)) + (W["ko"] if frac >= 1.0 else 0.0))
    return total


def _side_score(b, i):
    s = b.sides[i]
    score = _material(s)
    for _, m in s.alive_active():
        score -= _mon_penalty(m)
        score += _mon_stages(m)
    score += W["tailwind"] * _condition(s, "tailwind")
    score += W["screen"] * sum(_condition(s, k) for k in _SCREENS)
    score += _threat(b, i)
    return score


def evaluate(b):
    """Exact on a finished battle; otherwise tanh of the (side 0 - side 1) static score."""
    if b.winner is not None:
        return 0.0 if b.winner == -1 else (1.0 if b.winner == 0 else -1.0)
    mine = [m for _, m in b.sides[0].alive_active()]
    theirs = [m for _, m in b.sides[1].alive_active()]
    diff = _side_score(b, 0) - _side_score(b, 1) + W["speed"] * _speed_term(b, mine, theirs)
    # benched Pokemon carry status too (it stays through a switch)
    for i, sign in ((0, -1), (1, 1)):
        act = set(b.sides[i].active)
        for j, m in enumerate(b.sides[i].team):
            if j not in act and not m.fainted and m.status:
                diff += sign * _mon_penalty(m)
    return math.tanh(diff / W["scale"])


def evaluate_hp(b):
    """The original evaluation (average team HP fraction difference), kept for comparison."""
    if b.winner is not None:
        return 0.0 if b.winner == -1 else (1.0 if b.winner == 0 else -1.0)
    frac = [sum(m.hp / m.max_hp for m in s.team) / len(s.team) for s in b.sides]
    return frac[0] - frac[1]
