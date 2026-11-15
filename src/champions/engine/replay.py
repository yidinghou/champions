"""Save and replay games, and snapshot state.

A replay is the inputs only: format, seed, teams, and each turn's choices. Playing it again gives the same
game, because all randomness comes from the seeded Rng. The event log is a derived output (save_log).
"""
from __future__ import annotations

import json
from pathlib import Path

from .actions import from_dict
from .events import Event
from .game import play_turn, start
from .rng import Rng
from .state import Battle, Mon, Side
from .teams import build_battle

REPLAY_VERSION = 1


class ReplayError(ValueError):
    pass


def make_replay(teams, seed, turns, format="doubles"):
    """turns: list of lists of Move/Switch choices (or their dicts)."""
    return {"version": REPLAY_VERSION, "format": format, "seed": seed, "teams": teams,
            "turns": [[c if isinstance(c, dict) else c.to_dict() for c in t] for t in turns]}


def save_replay(path, teams, seed, turns, format="doubles"):
    Path(path).write_text(json.dumps(make_replay(teams, seed, turns, format), indent=1) + "\n")


def load_replay(path):
    r = json.loads(Path(path).read_text())
    if r.get("version") != REPLAY_VERSION:
        raise ReplayError(f"replay version {r.get('version')!r} not supported (engine reads {REPLAY_VERSION})")
    for k in ("format", "seed", "teams", "turns"):
        if k not in r:
            raise ReplayError(f"replay is missing {k!r}")
    return r


def play_replay(r):
    b = start(r["teams"], r["seed"], r["format"])
    for choices in r["turns"]:
        play_turn(b, [from_dict(c) for c in choices])
    return b


def replay(path):
    return play_replay(load_replay(path))


def log_to_list(battle):
    return [e.to_dict() for e in battle.log]


def save_log(path, battle):
    Path(path).write_text(json.dumps(log_to_list(battle), indent=1) + "\n")


_MON_FIELDS = ("species", "types", "ability", "item", "moves", "stats", "hp", "max_hp", "side", "idx",
               "stages", "status", "status_turns", "volatiles", "last_move", "turns_out", "pp", "mega", "nature", "sp")


def snapshot(b):
    """Plain-dict copy of everything needed to continue a battle, including the RNG state."""
    return {
        "format": b.format, "turn": b.turn, "winner": b.winner, "arena": json.loads(json.dumps(b.arena)),
        "seed": b.rng.seed, "rng_state": b.rng.getstate(), "log": log_to_list(b),
        "sides": [{"active": list(s.active), "conditions": json.loads(json.dumps(s.conditions)),
                   "mega_used": s.mega_used,
                   "team": [{f: json.loads(json.dumps(getattr(m, f))) for f in _MON_FIELDS} for m in s.team]}
                  for s in b.sides],
    }


def restore(d):
    sides = [Side(team=[Mon(**m) for m in sd["team"]], active=list(sd["active"]),
                  conditions=dict(sd["conditions"]), mega_used=sd["mega_used"]) for sd in d["sides"]]
    rng = Rng(d["seed"])
    rng.setstate(d["rng_state"])
    b = Battle(sides=sides, rng=rng, format=d["format"], arena=dict(d["arena"]), turn=d["turn"],
               log=[Event(e["turn"], e["kind"], e["data"]) for e in d["log"]], winner=d["winner"])
    return b
