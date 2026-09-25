#!/usr/bin/env python3
"""Refresh data/items.json and data/types.json from Pokemon Showdown.

Run:  python3 fetch_reference.py      (stdlib only)

Items: Showdown marks availability with `isNonstandard` in data/items.ts ("Past" = not
obtainable). The champions mod overrides that per item (null = available, e.g. Mega Stones).
Effective flag = mod override if present, else base. `legal` = no flag. Names and
descriptions come from Showdown's compiled items.js, which has no availability flags.
Types: Showdown's typechart.js. damageTaken codes: 0 normal, 1 super effective, 2 resisted, 3 immune.
"""
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SD = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master"
PLAY = "https://play.pokemonshowdown.com/data"
DATA = Path(__file__).parent / "data"
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

    meta = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "smogon/pokemon-showdown (items.ts + champions mod, typechart.js)"}
    (DATA / "items.json").write_text(json.dumps({**meta, "items": items}, indent=1) + "\n")
    (DATA / "types.json").write_text(json.dumps({**meta, "chart": types}, indent=1) + "\n")
    print(f"{len(items)} legal items of {len(text)}, {len(types)} types")


if __name__ == "__main__":
    main()
