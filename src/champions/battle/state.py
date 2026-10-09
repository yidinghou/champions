"""Battle state: one Pokémon and the field. Stats come from stats.level50 (Stat Points, level 50)."""
from dataclasses import dataclass, field as dc_field
from typing import Dict, List, Optional

from ..lookup import load, norm
from ..stats import level50, load as load_form

SPEC_KEYS = {"species", "moves", "nature", "sp", "item", "ability", "status", "boosts", "turns_out", "hp"}
FIELD_KEYS = ("trick_room", "tailwind_p1", "tailwind_p2")  # turns remaining; 0 = inactive
STATUSES = {"par", "brn", "psn", "tox", "slp", "frz"}
STAGE_KEYS = ("attack", "defense", "special-attack", "special-defense", "speed")


@dataclass
class Pokemon:
    species: str
    types: List[str]
    stats: Dict[str, int]
    hp: int
    max_hp: int
    moves: List[str]
    nature: str = "hardy"
    sp: Dict[str, int] = dc_field(default_factory=dict)
    item: Optional[str] = None
    ability: str = ""
    status: Optional[str] = None
    boosts: Dict[str, int] = dc_field(default_factory=dict)
    turns_out: int = 0  # turns spent on the field; Fake Out needs exactly 1
    flinched: bool = False
    protected: bool = False


def make_pokemon(spec):
    """Build a Pokemon from a scenario/team spec dict. Unknown keys or moves raise, so typos fail loudly."""
    unknown = set(spec) - SPEC_KEYS
    if unknown:
        raise ValueError(f"unknown pokemon key(s): {', '.join(sorted(unknown))}")
    form = load_form(spec["species"])
    nature, sp = spec.get("nature", "hardy"), spec.get("sp") or {}
    stats = level50(form["stats"], nature, sp)
    all_moves = load("moves.json")["moves"]
    moves = [norm(m) for m in spec.get("moves", [])]
    for m in moves:
        if m not in all_moves:
            raise ValueError(f"unknown move: {m}")
    status = spec.get("status")
    if status is not None and status not in STATUSES:
        raise ValueError(f"unknown status: {status}")
    boosts = spec.get("boosts") or {}
    if set(boosts) - set(STAGE_KEYS):
        raise ValueError(f"unknown boost stat(s): {', '.join(sorted(set(boosts) - set(STAGE_KEYS)))}")
    hp = spec.get("hp", stats["hp"])
    if not 1 <= hp <= stats["hp"]:
        raise ValueError(f"hp must be 1..{stats['hp']}, got {hp}")
    return Pokemon(species=form["name"], types=list(form["types"]), stats=stats, hp=hp,
                   max_hp=stats["hp"], moves=moves, nature=nature, sp=dict(sp),
                   item=norm(spec["item"]) if spec.get("item") else None, ability=spec.get("ability", ""),
                   status=status, boosts=dict(boosts), turns_out=spec.get("turns_out", 0))


def make_field(overrides):
    f = {k: 0 for k in FIELD_KEYS}
    for k, v in (overrides or {}).items():
        if k not in f:
            raise ValueError(f"unknown field key: {k}")
        f[k] = v
    return f
