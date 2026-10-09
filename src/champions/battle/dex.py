"""Picker data for the UI: species with their supported moves, plus items and natures."""
from functools import lru_cache

from ..lookup import load
from ..stats import NEUTRAL, _UP_DOWN
from .moves import all_moves, is_supported


@lru_cache(maxsize=None)
def dex():
    learnsets = load("learnsets.json")["learnsets"]
    species, used = {}, set()
    for f in load("champions.json")["pokemon"]:
        moves = [m for m in learnsets.get(f["name"], []) if is_supported(m)]
        used.update(moves)
        species[f["name"]] = {"types": f["types"], "stats": f["stats"], "abilities": f["abilities"],
                              "hidden_ability": f.get("hidden_ability"), "moves": moves}
    am = all_moves()
    moves = {m: {"name": am[m]["name"], "type": am[m]["type"], "category": am[m]["category"],
                 "power": am[m]["base_power"], "priority": am[m]["priority"], "target": am[m]["target"]}
             for m in sorted(used)}
    return {"species": species, "moves": moves, "items": sorted(load("items.json")["items"]),
            "natures": sorted(set(_UP_DOWN) | NEUTRAL)}
