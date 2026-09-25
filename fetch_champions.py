#!/usr/bin/env python3
"""Refresh data/champions.json from PokeAPI's `champions` pokedex.

Run:  python3 fetch_champions.py
Stdlib only. Safe to re-run any time; it overwrites the output file.

Data note: PokeAPI lists every Pokemon in the Champions game, but has NO
regulation/season info. We tag the Regulation M-C additions ourselves (see
NEW_IN_MC) from the official announcement, which is our source of truth:
https://www.pokemon.com/us/news/get-ready-for-regulation-set-m-c-in-pokemon-champions
"""
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

API = "https://pokeapi.co/api/v2"
OUT = Path(__file__).parent / "data" / "champions.json"

# Hand-maintained. Species names as PokeAPI spells them. Update per regulation.
# Game8 lists 22 new Pokemon, the official post says 24 -- unresolved, so this
# is likely incomplete. Extra data is fine; we filter at lookup time.
NEW_IN_MC = {
    "wigglytuff", "persian", "mr-mime", "swalot", "salamence", "gogoat",
    "golisopod", "rillaboom", "cinderace", "inteleon", "thievul", "toxtricity",
    "grapploct", "perrserker", "pincurchin", "indeedee", "arboliva",
    "squawkabilly", "mabosstiff", "baxcalibur", "pawmot",
}
NEW_MEGAS_MC = {
    "salamence-mega", "golisopod-mega", "baxcalibur-mega",
    "absol-mega-z", "garchomp-mega-z", "lucario-mega-z",
}


def get(path, retries=3):
    url = f"{API}/{path}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "champions-notes/0.1"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def fetch_species(name):
    """One species -> list of forms (base, megas, regional variants)."""
    species = get(f"pokemon-species/{name}")
    forms = []
    for v in species["varieties"]:
        if "gmax" in v["pokemon"]["name"]:  # Gigantamax isn't in Champions
            continue
        p = get(f"pokemon/{v['pokemon']['name']}")
        forms.append({
            "name": p["name"],
            "species": name,
            "dex_id": species["id"],
            "is_default": v["is_default"],
            "is_mega": "-mega" in p["name"],
            "new_in_mc": p["name"] in NEW_MEGAS_MC or (v["is_default"] and name in NEW_IN_MC),
            "types": [t["type"]["name"] for t in sorted(p["types"], key=lambda t: t["slot"])],
            "stats": {s["stat"]["name"]: s["base_stat"] for s in p["stats"]},
            "abilities": [a["ability"]["name"] for a in p["abilities"]],
        })
    return forms


def main():
    dex = get("pokedex/champions")
    species = [e["pokemon_species"]["name"] for e in dex["pokemon_entries"]]
    # 8 workers keeps us polite; ~550 requests total, well under a minute.
    with ThreadPoolExecutor(max_workers=8) as ex:
        pokemon = [f for forms in ex.map(fetch_species, species) for f in forms]

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": f"{API}/pokedex/champions",
        "species_count": len(species),
        "pokemon": pokemon,
    }, indent=1) + "\n")
    print(f"{len(species)} species, {len(pokemon)} forms -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
