"""Human-readable rendering of one turn: grouped by action, with an HP table before and after."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

BAR_WIDTH = 20

_CODES = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33", "blue": "34",
          "magenta": "35", "cyan": "36", "orange": "38;5;208",
          "purple": "38;5;99", "crimson": "38;5;161", "sky": "38;5;75"}
_color = False
SIDE_COLORS = ["purple", "crimson"]   # team colors (as in the game's team select); orange is damage, green heal
KIND_COLORS = {"damage": "orange", "recoil": "orange", "faint": "bold orange", "crit": "bold yellow",
               "heal": "green", "field": "bold cyan", "status": "sky", "volatile": "sky", "switch": "cyan",
               "mega": "bold sky", "win": "bold green", "fail": "yellow", "immune": "dim",
               "item": "yellow", "protected": "cyan", "missed": "dim", "blocked": "cyan"}


def set_color(on):
    global _color
    _color = bool(on)


def paint(text, style):
    """Wrap text in ANSI codes for a space-separated style like 'bold red'. No-op when color is off."""
    if not _color or not style:
        return text
    return "\033[" + ";".join(_CODES[w] for w in style.split()) + "m" + text + "\033[0m"


def side_style(ref):
    side = ref.partition(":")[0]
    return "bold " + SIDE_COLORS[0 if side == "p1" else 1]
STATUS_WORDS = {"brn": "burned", "psn": "poisoned", "tox": "badly poisoned", "par": "paralyzed",
                "slp": "asleep", "frz": "frozen"}
VOLATILE_WORDS = {"confusion": "confused", "taunt": "taunted", "encore": "encored", "disable": "disabled",
                  "leechseed": "seeded", "trapped": "trapped", "yawn": "drowsy", "followme": "the center of attention", "ragepowder": "the center of attention", "choicelock": "locked into a move"}
HIDDEN_VOLATILES = {"protect_chain"}      # engine bookkeeping, not something a player sees
from .arena import TERRAIN_WORDS, WEATHER_WORDS  # noqa: E402
from .items import item_name  # noqa: E402
from .screens import SIDE_WORDS  # noqa: E402

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
    frac = hp / max_hp if max_hp else 0
    style = "green" if frac > 0.5 else "yellow" if frac > 0.2 else "orange"
    return "[" + paint("#" * filled, style) + paint("." * (width - filled), "dim") + "]"


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
            extra += [k for k in m.volatiles if k not in HIDDEN_VOLATILES]
            tail = f"  ({', '.join(extra)})" if extra else ""
            lines.append(f"  {paint(f'{name:<22}', side_style(m.ref))}{m.hp:>4}/{m.max_hp:<4} "
                         f"{hp_bar(m.hp, m.max_hp)}{paint(tail, 'yellow')}")
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
        if "remove" in d:
            return f"{mon_name(d['mon'])} is no longer {VOLATILE_WORDS.get(d['remove'], d['remove'])}"
        if d["add"] == "protect":
            return f"{mon_name(d['mon'])} braced behind Protect"
        return f"{mon_name(d['mon'])} is {VOLATILE_WORDS.get(d['add'], 'now ' + d['add'])}"
    if k == "boost":
        stat = STAT_NAMES.get(d["stat"], d["stat"])
        if d["change"] == 0:
            return f"{mon_name(d['mon'])}'s {stat} won't go any further (stage {d['stage']:+d})"
        word = "rose" if d["change"] > 0 else "fell"
        return f"{mon_name(d['mon'])}'s {stat} {word} by {abs(d['change'])} (stage {d['stage']:+d})"
    if k == "field" and d["effect"] == "trick_room":
        if d.get("start"):
            return f"{mon_name(d['mon'])} twisted the dimensions! (Trick Room, {d['turns']} turns)"
        return "The twisted dimensions returned to normal!"
    if k == "field" and d["effect"] == "weather":
        if d.get("start"):
            return f"The weather turned to {WEATHER_WORDS[d['which']]}! ({d['turns']} turns)"
        return f"The {WEATHER_WORDS[d['which']].removeprefix('a ')} ended"
    if k == "field" and d["effect"] == "terrain":
        if d.get("start"):
            return f"{TERRAIN_WORDS[d['which']]} covers the battlefield! ({d['turns']} turns)"
        return f"{TERRAIN_WORDS[d['which']]} faded"
    if k == "item":
        who, name = mon_name(d["mon"]), item_name(d["item"])
        return {"eat": f"{who} ate its {name}", "weaken": f"{name} weakened the damage to {who}",
                "survive": f"{who} hung on using its {name}", "popped": f"{who}'s {name} popped",
                "eject": f"{who} was switched out by its {name}", "red_card": f"{who} held up its {name}"
                }.get(d.get("cause"), f"{who} used its {name}")
    if k == "field" and d["effect"] == "side":
        who, name = f"P{d['side'] + 1}'s side", SIDE_WORDS[d["which"]]
        if d.get("start"):
            return f"{name} is up on {who} ({d['turns']} turns)"
        return f"{name} wore off on {who}" if d.get("cause") == "expired" else f"{name} was shattered on {who}"
    if k == "crit":
        return "A critical hit!"
    if k == "fail" and d.get("reason") == "already_status":
        return f"{mon_name(d['mon'])} already has a status, so {move_name(d['move'])} fails"
    if k == "fail":
        return f"{mon_name(d['mon'])} can't use {move_name(d['move'])}: {d['reason'].replace('_', ' ')}"
    if k == "immune" and d.get("ability"):
        return f"{mon_name(d['mon'])}'s {d['ability']} absorbed {move_name(d['move'])}"
    if k == "immune":
        return f"It doesn't affect {mon_name(d['mon'])}"
    if k == "redirect":
        return f"{move_name(d['move'])} was drawn to {mon_name(d['mon'])} ({d['cause']})"
    if k == "protected":
        return f"{mon_name(d['mon'])} protected itself"
    if k == "missed":
        return f"{mon_name(d['mon'])} avoided the attack"
    if k == "blocked" and d.get("reason") == "psychic_terrain":
        return f"Psychic Terrain protects {mon_name(d['mon'])} from {move_name(d['move'])}"
    if k == "blocked":
        return f"{mon_name(d['mon'])}'s {d.get('ability', 'ability')} blocked the {d.get('stat')} drop"
    if k == "status":
        if "cure" in d:
            return f"{mon_name(d['mon'])} is no longer {STATUS_WORDS.get(d['cure'], d['cure'])}"
        return f"{mon_name(d['mon'])} is {STATUS_WORDS.get(d['add'], d['add'])}"
    if k == "switch":
        return f"{mon_name(d['mon'])} was sent out"
    if k == "mega":
        return f"{mon_name(d['mon'])} Mega Evolved into {d['form'].replace('-', ' ').title()}! ({d['ability']}, {d['types']})"
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
            out.append(f"{paint(mon_name(d['mon']), side_style(d['mon']))} used "
                       f"{paint(move_name(d['move']), 'bold')}!")
        elif e.kind == "rng":
            if show_rng:
                out.append(paint(f"      (roll {d['label']} = {d['value']})", "dim"))
        elif e.kind == "hit" and d.get("spread"):
            out.append(paint(f"  hits {mon_name(d['mon'])} (spread)", "dim"))
        else:
            line = _describe(e)
            if line:
                style = KIND_COLORS.get(e.kind)
                if e.kind == "boost":
                    style = "green" if d["change"] > 0 else "yellow" if d["change"] < 0 else "dim"
                name = mon_name(d["mon"]) if "mon" in d else None
                if name and line.startswith(name):     # team-colored name, event-colored rest
                    line = paint(name, side_style(d["mon"])) + paint(line[len(name):], style)
                else:
                    line = paint(line, style)
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
    lines = [paint(f"=== Turn {turn} ===", "bold cyan"), ""]
    entry = render_turn([e for e in after.log if e.turn == 0], show_rng) if turn == 1 else []
    if entry:                                  # battle-start effects, e.g. Intimidate
        lines += [paint("Switch-in:", "bold"), *entry, ""]
    lines += [paint("Start of turn:", "bold"), *hp_table(before), ""]
    lines += render_turn(evs, show_rng)
    lines += ["", paint("End of turn:", "bold"), *hp_table(after)]
    if after.winner is not None:
        lines.append(paint("Winner: " + ("draw" if after.winner == -1 else f"P{after.winner + 1}"),
                           "bold green"))
    return "\n".join(lines)
