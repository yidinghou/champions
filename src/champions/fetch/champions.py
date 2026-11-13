"""Refresh data/champions.json from PokeAPI's `champions` pokedex.

Run:  champions fetch champions
Stdlib only. Safe to re-run any time; it overwrites the output file.

Data note: PokeAPI lists every Pokemon in the Champions game, but has NO
regulation/season info. We tag the Regulation M-C additions ourselves (see
NEW_IN_MC). Sources: the official announcement, cross-checked with
check_roster.py against Pokemon Showdown:
https://www.pokemon.com/us/news/get-ready-for-regulation-set-m-c-in-pokemon-champions
"""
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

API = "https://pokeapi.co/api/v2"
OUT = Path(__file__).parent.parent / "data" / "champions.json"

# Hand-maintained: exact PokeAPI form names added in Regulation M-C. Update per regulation.
# check_roster.py verifies this against Pokemon Showdown's roster and exits 1 on any mismatch.
NEW_IN_MC = {
    "absol-mega-z", "arboliva", "baxcalibur", "baxcalibur-mega", "cinderace",
    "farfetchd", "garchomp-mega-z", "gogoat", "golisopod", "golisopod-mega",
    "grapploct", "indeedee-female", "indeedee-male", "inteleon", "lucario-mega-z",
    "mabosstiff", "mr-mime", "pawmot", "perrserker", "persian", "persian-alola",
    "pincurchin", "rillaboom", "salamence", "salamence-mega", "sirfetchd",
    "squawkabilly-blue-plumage", "squawkabilly-green-plumage",
    "squawkabilly-white-plumage", "squawkabilly-yellow-plumage", "swalot", "thievul",
    "toxtricity-amped", "toxtricity-low-key", "wigglytuff",
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
            "new_in_mc": p["name"] in NEW_IN_MC,
            "types": [t["type"]["name"] for t in sorted(p["types"], key=lambda t: t["slot"])],
            "stats": {s["stat"]["name"]: s["base_stat"] for s in p["stats"]},
            "abilities": [a["ability"]["name"] for a in p["abilities"]],
            "hidden_ability": next((a["ability"]["name"] for a in p["abilities"] if a["is_hidden"]), None),
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
