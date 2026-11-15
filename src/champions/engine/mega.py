"""Mega Evolution. A mon holding the Mega Stone for its species may Mega Evolve once per side per battle, as part of
choosing a move (`Move(..., mega=True)`). The evolution happens before any move that turn, in Speed order (kind
MEGA in turn.py). The new form's types, ability and stats replace the old ones for the rest of the battle: HP is
kept as it is, the other stats are recomputed at level 50 with the mon's own Stat Points and nature, and the new
ability's switch-in effect runs (Drought, Intimidate...). The form stays through switching and the ability is locked in.
TODO(mega): Mega forms are only as good as the abilities modeled; a team whose stone leads to an unmodeled
ability is rejected at start().
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .. import stats as stats_mod
from .teams import DATA, SHORT, key

LETTERS = ("x", "y", "z")


@lru_cache(maxsize=None)
def _forms():
    """Mega form name -> its champions.json entry."""
    data = json.loads((DATA / "champions.json").read_text())["pokemon"]
    return {p["name"]: p for p in data if p.get("is_mega")}


@lru_cache(maxsize=None)
def _species_of():
    data = json.loads((DATA / "champions.json").read_text())["pokemon"]
    return {p["name"]: p["species"] for p in data}


def _common(a, b):
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return n


@lru_cache(maxsize=None)
def stone_species(stone):
    """The species a Mega Stone belongs to: the one whose name shares the longest start with the stone's id
    ('garchomp' for garchompitez, 'heracross' for heracronite, 'floette' for floettite)."""
    best, score = None, 4
    for s in sorted({f["species"] for f in _forms().values()}):
        n = _common(stone, s)
        if n > score:
            best, score = s, n
    return best


def form_for(mon):
    """Name of the Mega form `mon` can take with the stone it holds, or None."""
    stone = mon.item
    if not stone or stone not in _mega_stone_ids():
        return None
    species = stone_species(stone)
    if species is None or _species_of().get(mon.species) != species:
        return None
    forms = sorted(n for n, f in _forms().items() if f["species"] == species)
    if len(forms) == 1:
        return forms[0]
    letter = stone[-1]
    if letter in LETTERS and f"{species}-mega-{letter}" in forms:
        return f"{species}-mega-{letter}"
    own = f"{mon.species}-mega"                      # meowstic-male -> meowstic-male-mega
    if own in forms:
        return own
    plain = f"{species}-mega"                        # garchompite -> garchomp-mega (when -z also exists)
    return plain if plain in forms else None


@lru_cache(maxsize=None)
def _mega_stone_ids():
    from .items import _mega_stones
    return frozenset(_mega_stones())


def form_ability(form_name):
    return key(_forms()[form_name]["abilities"][0])


def can_evolve(battle, mon):
    return (form_for(mon) is not None and not mon.mega and not battle.sides[mon.side].mega_used)


def check_choice(battle, choices):
    """Raise ValueError for a Mega Evolution that is not allowed this turn."""
    used = set()
    for c in choices:
        if not getattr(c, "mega", False):
            continue
        mon = battle.mon(c.side, c.slot)
        if form_for(mon) is None:
            raise ValueError(f"{mon.species} cannot Mega Evolve (needs the Mega Stone for its species)")
        if mon.mega or battle.sides[c.side].mega_used or c.side in used:
            raise ValueError(f"side {c.side} has already used Mega Evolution")
        used.add(c.side)


def evolve(battle, mon):
    """Change `mon` into its Mega form. HP stays; other stats are recomputed; the new ability starts."""
    from .game import send_in_ability
    form_name = form_for(mon)
    form = _forms()[form_name]
    new = stats_mod.level50(form["stats"], mon.nature, mon.sp)
    for long, short in SHORT.items():
        if short != "hp":
            mon.stats[short] = new[long]
    mon.types = list(form["types"])
    mon.ability = form_ability(form_name)
    mon.mega = True
    battle.sides[mon.side].mega_used = True
    battle.log_event("mega", mon=mon.ref, form=form_name, ability=mon.ability, types="/".join(mon.types))
    send_in_ability(battle, mon)
