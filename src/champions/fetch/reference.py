"""Refresh data/items.json, data/types.json and data/abilities.json.

Run:  champions fetch reference     (stdlib only)

Items: Showdown marks availability with `isNonstandard` in data/items.ts ("Past" = not
obtainable). The champions mod overrides that per item (null = available, e.g. Mega Stones).
Effective flag = mod override if present, else base. `legal` = no flag. Names and
descriptions come from Showdown's compiled items.js, which has no availability flags.
Abilities: descriptions from PokeAPI (slugs match champions.json). Showdown's champions
mod abilities.ts flags abilities it overrides (`champions_override`). That can be a real change
(Regenerator heals 1/3) or an implementation detail (Berserk), so treat it as "check this one".
Descriptions themselves are main-series text.
Types: Showdown's typechart.js. damageTaken codes: 0 normal, 1 super effective, 2 resisted, 3 immune.
"""
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

SD = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master"
PLAY = "https://play.pokemonshowdown.com/data"
DATA = Path(__file__).parent.parent / "data"
POKEAPI = "https://pokeapi.co/api/v2"
MULT = {0: 1, 1: 2, 2: 0.5, 3: 0}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "champions-notes/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_flags(ts):
    """{item_id: isNonstandard value or None} for entries that have the field, from a Showdown items.ts."""
    out, cur = {}, None
    for line in ts.splitlines():
        if m := re.match(r"^\t(\w+): \{$", line):
            cur = m.group(1)
        elif cur and (m := re.match(r'^\t\tisNonstandard: (null|"[^"]*"),$', line)):
            out[cur] = json.loads(m.group(1))
    return out


def parse_item_text(js):
    """{item_id: (name, short description)} from the compiled items.js (unquoted-key JS, so split by regex)."""
    body = js.split("=", 1)[1]
    out = {}
    for chunk in re.split(r',(?=[a-z0-9]+:\{name:")', body):
        m = re.match(r'\{?([a-z0-9]+):\{name:"((?:[^"\\]|\\.)*)"', chunk)
        if not m:
            continue
        d = re.search(r'shortDesc:"((?:[^"\\]|\\.)*)"', chunk)
        out[m.group(1)] = (json.loads(f'"{m.group(2)}"'), json.loads(f'"{d.group(1)}"') if d else None)
    return out


def parse_changed_abilities(ts):
    """Ability ids the champions mod overrides beyond availability flags (i.e. changed behavior)."""
    changed, cur = set(), None
    for line in ts.splitlines():
        if m := re.match(r"^\t(\w+): \{$", line):
            cur = m.group(1)
        elif cur and (m := re.match(r"^\t\t(\w+)[:(]", line)) and m.group(1) not in ("inherit", "isNonstandard"):
            changed.add(cur)
    return changed


def fetch_ability(slug):
    try:
        a = json.loads(fetch(f"{POKEAPI}/ability/{slug}"))
    except Exception:
        return slug, None
    en = lambda entries, key: next((e[key] for e in entries if e["language"]["name"] == "en"), None)
    desc = en(a["effect_entries"], "short_effect")
    if not desc:  # newer abilities may only have flavor text
        texts = [e["flavor_text"] for e in a["flavor_text_entries"] if e["language"]["name"] == "en"]
        desc = texts[-1].replace("\n", " ") if texts else None
    return slug, {"name": en(a["names"], "name") or slug, "short_desc": desc}


def parse_typechart(js):
    """{attacker: {defender: multiplier}} for the 18 types (Stellar excluded)."""
    taken = {}
    for t, body in re.findall(r"([a-z]+):\{damageTaken:\{([^}]*)\}", js):
        taken[t] = {k: v for k, v in re.findall(r"([A-Z][a-z]+):(\d)", body)}
    taken.pop("stellar", None)  # Tera-only; not in Champions
    types = sorted(taken)
    return {a.capitalize(): {d.capitalize(): MULT[int(taken[d][a.capitalize()])] for d in types} for a in types}


def main():
    base = parse_flags(fetch(f"{SD}/data/items.ts"))
    mod = parse_flags(fetch(f"{SD}/data/mods/champions/items.ts"))
    text = parse_item_text(fetch(f"{PLAY}/items.js"))
    flags = {**base, **mod}  # mod override wins, including an explicit null
    items = {}
    for iid, (name, desc) in sorted(text.items()):
        if flags.get(iid) is None:
            items[iid] = {"name": name, "short_desc": desc}
    types = parse_typechart(fetch(f"{PLAY}/typechart.js"))

    forms = json.loads((DATA / "champions.json").read_text())["pokemon"]
    slugs = sorted({a for f in forms for a in f["abilities"]})
    with ThreadPoolExecutor(max_workers=8) as ex:
        fetched = dict(ex.map(fetch_ability, slugs))
    changed = parse_changed_abilities(fetch(f"{SD}/data/mods/champions/abilities.ts"))
    abilities = {}
    for slug, info in fetched.items():
        if info:
            abilities[slug] = {**info, "champions_override": re.sub(r"[^a-z0-9]", "", slug) in changed}
    missing = [s for s, i in fetched.items() if not i]

    meta = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "smogon/pokemon-showdown (items.ts + champions mod, typechart.js)"}
    (DATA / "items.json").write_text(json.dumps({**meta, "items": items}, indent=1) + "\n")
    (DATA / "types.json").write_text(json.dumps({**meta, "chart": types}, indent=1) + "\n")
    (DATA / "abilities.json").write_text(json.dumps({**meta, "abilities": abilities}, indent=1) + "\n")
    print(f"{len(items)} legal items of {len(text)}, {len(types)} types, {len(abilities)} abilities "
          f"({sum(a['champions_override'] for a in abilities.values())} overridden in Champions mod)")
    if missing:
        print("no PokeAPI data for abilities:", ", ".join(missing))
    nodesc = [s for s, a in abilities.items() if not a["short_desc"]]
    if nodesc:
        print("no description for:", ", ".join(nodesc))


if __name__ == "__main__":
    main()
