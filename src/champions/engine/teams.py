"""Build battle state from plain team specs (what replays and catalogue cases store)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .. import stats as stats_mod
from .rng import Rng
from .state import Battle, Mon, Side

DATA = Path(__file__).resolve().parents[1] / "data"
SP_ORDER = ("hp", "attack", "defense", "special-attack", "special-defense", "speed")
SHORT = {"hp": "hp", "attack": "atk", "defense": "def",
         "special-attack": "spa", "special-defense": "spd", "speed": "spe"}


def key(name):
    return "".join(ch for ch in name.lower() if ch.isalnum())


@lru_cache(maxsize=None)
def _species():
    return {p["name"]: p for p in json.loads((DATA / "champions.json").read_text())["pokemon"]}


@lru_cache(maxsize=None)
def moves_data():
    return json.loads((DATA / "moves.json").read_text())["moves"]


def parse_sp(sp):
    """'32/0/0/0/32/2' (hp/atk/def/spa/spd/spe) or a dict keyed by long stat names -> dict."""
    if not sp:
        return {}
    if isinstance(sp, dict):
        return dict(sp)
    parts = [int(x) for x in sp.split("/")]
    return {s: v for s, v in zip(SP_ORDER, parts) if v}


def build_mon(spec, side=0, idx=0):
    """spec: 'species' | 'species:ability' | dict(species, ability, item, moves, sp, nature)."""
    if isinstance(spec, str):
        name, _, ability = spec.partition(":")
        spec = {"species": name, "ability": ability or None}
    sp = _species()[spec["species"]]
    base_stats = stats_mod.level50(sp["stats"], spec.get("nature", "hardy"), parse_sp(spec.get("sp")))
    st = {SHORT[k]: v for k, v in base_stats.items()}
    ability = key(spec.get("ability") or sp["abilities"][0])
    moves = [key(m) for m in spec.get("moves", [])]
    mv = moves_data()
    pp = {m: mv[m]["pp"] for m in moves if m in mv}
    hp = st["hp"] if spec.get("hp") is None else max(0, min(st["hp"], spec["hp"]))  # "hp" is for tests
    return Mon(species=sp["name"], types=list(sp["types"]), ability=ability,
               item=spec.get("item"), moves=moves, stats=st, hp=hp, max_hp=st["hp"],
               status=spec.get("status"), status_turns=spec.get("status_turns", 0),
               side=side, idx=idx, pp=pp)


def build_battle(teams, seed=0, format="doubles", rng=None):
    """teams: [[spec, ...], [spec, ...]]. The first 2 (doubles) or 1 (singles) of each lead."""
    slots = 2 if format == "doubles" else 1
    sides = []
    for s, team in enumerate(teams):
        mons = [build_mon(spec, s, i) for i, spec in enumerate(team)]
        active = [i if i < len(mons) else None for i in range(slots)]
        sides.append(Side(team=mons, active=active))
    return Battle(sides=sides, rng=rng or Rng(seed), format=format)
