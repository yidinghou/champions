"""Type effectiveness from data/types.json: chart[attacker][defender] -> multiplier."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"


@lru_cache(maxsize=None)
def chart():
    return json.loads((DATA / "types.json").read_text())["chart"]


def effectiveness(move_type, defender_types, ignore_immunity_to=()):
    """Product of the multipliers. Types in ignore_immunity_to count as neutral if they would be 0
    (Scrappy: Normal and Fighting hit Ghost)."""
    atk = move_type.capitalize()
    mult = 1.0
    for t in defender_types:
        m = chart()[atk][t.capitalize()]
        if m == 0 and t.lower() in ignore_immunity_to:
            m = 1
        mult *= m
    return mult


def is_immune(move_type, defender_types, ignore_immunity_to=()):
    return effectiveness(move_type, defender_types, ignore_immunity_to) == 0
