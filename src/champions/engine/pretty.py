"""Human-readable rendering of one turn: grouped by action, with an HP table before and after."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

BAR_WIDTH = 20
STATUS_WORDS = {"brn": "burned", "psn": "poisoned", "tox": "badly poisoned", "par": "paralyzed",
                "slp": "asleep", "frz": "frozen"}
STAT_NAMES = {"atk": "Attack", "def": "Defense", "spa": "Sp. Atk", "spd": "Sp. Def",
              "spe": "Speed", "acc": "Accuracy", "eva": "Evasion"}


@lru_cache(maxsize=1)
def _move_names():
    try:
        d = json.loads((Path(__file__).resolve().parents[1] / "data" / "moves.json").read_text())
        return {k: v["name"] for k, v in d["moves"].items()}
    except (OSError, KeyError, ValueError):
        return {}


def move_name(move_id):
    return _move_names().get(move_id) or move_id.replace("_", " ").title()


def mon_name(ref):
    """'p1:incineroar' -> 'Incineroar (P1)'."""
    side, _, species = ref.partition(":")
    return f"{species.replace('-', ' ').title()} ({side.upper()})"


def hp_bar(hp, max_hp, width=BAR_WIDTH):
    filled = 0 if hp <= 0 else max(1, round(width * hp / max_hp))
    return "[" + "#" * filled + "." * (width - filled) + "]"


def hp_table(b):
    lines = []
    for si, side in enumerate(b.sides):
        for slot, i in enumerate(side.active):
            m = None if i is None else side.team[i]
            if m is None:
                continue
            name = mon_name(m.ref)
            extra = []
            if m.status:
                extra.append(m.status)
            extra += [f"{STAT_NAMES.get(k, k)} {v:+d}" for k, v in m.stages.items() if v]
            extra += [k for k in m.volatiles]
            tail = f"  ({', '.join(extra)})" if extra else ""
            lines.append(f"  {name:<22}{m.hp:>4}/{m.max_hp:<4} {hp_bar(m.hp, m.max_hp)}{tail}")
    return lines


def _describe(e):
    """One line for an event, or None to hide it."""
    d, k = e.data, e.kind
    if k == "damage":
        return f"{mon_name(d['mon'])} takes {d['amount']} damage ({d['hp']})"
    if k == "recoil":
        return f"{mon_name(d['mon'])} is hurt by recoil ({d['amount']})"
    if k == "heal":
        return f"{mon_name(d['mon'])} recovers {d['amount']} ({d['hp']})"
    if k == "faint":
        return f"{mon_name(d['mon'])} fainted!"
    if k == "volatile":
        return f"{mon_name(d['mon'])} gets {d['add']}"
    if k == "boost":
        stat = STAT_NAMES.get(d["stat"], d["stat"])
        if d["change"] == 0:
            return f"{mon_name(d['mon'])}'s {stat} won't go any further (stage {d['stage']:+d})"
        word = "rose" if d["change"] > 0 else "fell"
        return f"{mon_name(d['mon'])}'s {stat} {word} by {abs(d['change'])} (stage {d['stage']:+d})"
    if k == "crit":
        return "A critical hit!"
    if k == "fail" and d.get("reason") == "already_status":
        return f"{mon_name(d['mon'])} already has a status, so {move_name(d['move'])} fails"
    if k == "fail":
        return f"{mon_name(d['mon'])} can't use {move_name(d['move'])}: {d['reason'].replace('_', ' ')}"
    if k == "immune":
        return f"It doesn't affect {mon_name(d['mon'])}"
    if k == "protected":
        return f"{mon_name(d['mon'])} protected itself"
    if k == "missed":
        return f"{mon_name(d['mon'])} avoided the attack"
    if k == "blocked":
        return f"{mon_name(d['mon'])}'s {d.get('ability', 'ability')} blocked the {d.get('stat')} drop"
    if k == "status":
        if "cure" in d:
            return f"{mon_name(d['mon'])} is no longer {STATUS_WORDS.get(d['cure'], d['cure'])}"
        return f"{mon_name(d['mon'])} is {STATUS_WORDS.get(d['add'], d['add'])}"
    if k == "switch":
        return f"{mon_name(d['mon'])} was sent out"
    if k == "mega":
        return f"{mon_name(d['mon'])} Mega Evolved"
    if k == "win":
        return "Draw" if d["side"] == -1 else f"P{d['side'] + 1} wins!"
    if k in ("hit", "rng", "start", "turn", "move"):
        return None
    return f"{k} {d}"


def render_turn(events, show_rng=False):
    """Lines for one turn's events. A 'move' event starts a new action block."""
    out = []
    for e in events:
        d = e.data
        if e.kind == "move":
            out.append(f"{mon_name(d['mon'])} used {move_name(d['move'])}!")
        elif e.kind == "rng":
            if show_rng:
                out.append(f"      (roll {d['label']} = {d['value']})")
        elif e.kind == "hit" and d.get("spread"):
            out.append(f"  hits {mon_name(d['mon'])} (spread)")
        else:
            line = _describe(e)
            if line:
                out.append("  " + line)
    return out


def render(replay_data, turn, play, show_rng=False):
    """Play the replay up to the end of `turn` and print that turn only.

    `play` is replay.play_replay. State before the turn comes from playing one turn fewer.
    """
    n = len(replay_data["turns"])
    if not 1 <= turn <= n:
        raise ValueError(f"turn must be between 1 and {n}")
    before = play({**replay_data, "turns": replay_data["turns"][:turn - 1]})
    after = play({**replay_data, "turns": replay_data["turns"][:turn]})
    evs = [e for e in after.log if e.turn == turn]
    lines = [f"=== Turn {turn} ===", "", "Start of turn:", *hp_table(before), ""]
    lines += render_turn(evs, show_rng)
    lines += ["", "End of turn:", *hp_table(after)]
    if after.winner is not None:
        lines.append("Winner: " + ("draw" if after.winner == -1 else f"P{after.winner + 1}"))
    return "\n".join(lines)
