"""Cached reference data the belief module needs: species forms, learnsets, items, Mega forms.

Reads the same JSON files as the engine (src/champions/data). Names are Showdown-style ids (`key`) unless noted.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Dict, List, Optional, Set

from ..engine.teams import DATA
from ..sources.common import key


@lru_cache(maxsize=None)
def species_table() -> Dict[str, dict]:
    """{champions.json form name: entry}, e.g. 'garchomp-mega-z' -> {...}."""
    return {p["name"]: p for p in json.loads((DATA / "champions.json").read_text())["pokemon"]}


@lru_cache(maxsize=None)
def learnsets() -> Dict[str, Set[str]]:
    return {k: set(v) for k, v in json.loads((DATA / "learnsets.json").read_text())["learnsets"].items()}


@lru_cache(maxsize=None)
def items() -> Dict[str, dict]:
    return json.loads((DATA / "items.json").read_text())["items"]


def legal_abilities(slug: str) -> Set[str]:
    """Ability ids (key form) a form can have, including its hidden ability."""
    e = species_table().get(slug)
    if not e:
        return set()
    names = list(e["abilities"]) + ([e["hidden_ability"]] if e.get("hidden_ability") else [])
    return {key(a) for a in names}


def can_learn(slug: str, move: str) -> bool:
    return key(move) in learnsets().get(slug, set())


def is_item(item: str) -> bool:
    return key(item) in items()


def is_mega_stone(item: str) -> bool:
    e = items().get(key(item))
    return bool(e) and "Mega Evolve" in e.get("short_desc", "")


def mega_forms(species: str) -> List[str]:
    """Mega form slugs of a base species (garchomp -> ['garchomp-mega-z'])."""
    base = species_table().get(species, {}).get("species", species)
    return sorted(n for n, e in species_table().items() if e["is_mega"] and e["species"] == base)


def mega_form_for(species: str, stone: str) -> Optional[str]:
    """The Mega form a stone produces for `species`, or None if it cannot be told.
    Stones for species with several Megas end in the form's letter (charizarditex -> charizard-mega-x)."""
    if not is_mega_stone(stone):
        return None
    forms = mega_forms(species)
    if len(forms) == 1:
        return forms[0]
    k = key(stone)
    for f in forms:
        tail = f.rsplit("-", 1)[-1]          # 'x', 'y', 'z'
        if len(tail) == 1 and k.endswith(tail):
            return f
    return None
