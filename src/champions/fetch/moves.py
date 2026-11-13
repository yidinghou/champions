"""Refresh data/moves.json and data/learnsets.json from Pokemon Showdown.

Run:  champions fetch moves     (after `champions fetch champions`; stdlib only)

Sources (see DECISIONS.md 005):
- Learnsets: smogon/pokemon-showdown data/mods/champions/learnsets.ts
- Moves: Showdown's compiled main-series moves.json, with the champions mod's
  moves.ts *overrides* merged on top. That file only lists what differs from
  main series, e.g. a changed basePower. (isNonstandard "Past" overrides are ignored: the
  champions learnsets already exclude unusable moves.)
- PP: Serebii's Champions moves page (one request). Showdown doesn't model
  Champions PP, and Serebii's values differ from main series for most moves.
Showdown ids are lowercase alphanumeric ("doubleedge"). Learnsets are keyed by
OUR form names from champions.json.
"""
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAW = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/mods/champions"
TEXT_URL = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/text"
MOVES_JSON = "https://play.pokemonshowdown.com/data/moves.json"
COMMITS = "https://api.github.com/repos/smogon/pokemon-showdown/commits?per_page=1&path=data/mods/champions/learnsets.ts"
SEREBII_MOVES = "https://www.serebii.net/pokemonchampions/moves.shtml"
DATA = Path(__file__).parent.parent / "data"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "champions-notes/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")  # Serebii pages aren't always UTF-8


def norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def fetch_pp():
    """{showdown_id: PP} from Serebii's Champions moves table (columns: type, category, PP, power, accuracy)."""
    html = fetch(SEREBII_MOVES)
    rows = re.findall(
        r'attackdex-champions/([^"]+?)\.shtml">[^<]+</a>.*?<td class="cen">\s*(\d+|--)\s*</td>', html, re.S)
    return {norm(slug): int(pp) for slug, pp in rows if pp != "--"}


def parse_learnsets(ts):
    """{showdown_id: [move ids]} from the champions learnsets.ts."""
    out, mon, in_learnset = {}, None, False
    for line in ts.splitlines():
        if m := re.match(r"^\t(\w+): \{$", line):
            mon, in_learnset = m.group(1), False
            out[mon] = []
        elif re.match(r"^\t\tlearnset: \{$", line):
            in_learnset = True
        elif in_learnset and (m := re.match(r"^\t\t\t(\w+): \[", line)):
            out[mon].append(m.group(1))
        elif re.match(r"^\t\t\},?$", line):
            in_learnset = False
    return out


def parse_short_descs(ts):
    """{id: shortDesc} from Showdown's data/text/{moves,items}.ts (current-gen text: the 2-tab shortDesc,
    not the genN sub-blocks). The compiled play.pokemonshowdown.com data files no longer carry descriptions."""
    out, cur = {}, None
    for line in ts.splitlines():
        if m := re.match(r"^\t(\w+): \{$", line):
            cur = m.group(1)
        elif cur and (m := re.match(r'^\t\tshortDesc: ("(?:[^"\\]|\\.)*"),$', line)):
            out[cur] = json.loads(m.group(1))
    return out


def parse_move_overrides(ts):
    """{move_id: {field: value}} for scalar fields only (nested ones like secondary are skipped)."""
    out, move = {}, None
    for line in ts.splitlines():
        if m := re.match(r"^\t(\w+): \{$", line):
            move = out.setdefault(m.group(1), {})
        elif move is not None and (m := re.match(r'^\t\t(\w+): (true|false|-?\d+|"[^"]*"),$', line)):
            if m.group(1) != "inherit":
                move[m.group(1)] = json.loads(m.group(2))
    return out


# Showdown only keys the Champions Floette as floetteeternal.
ALIASES = {"floette": "floetteeternal", "floette-mega": "floetteeternal"}


def resolve(form, learnsets):
    """Showdown id for one of our forms. Megas and cosmetic forms fall back to the base species."""
    if form["name"] in ALIASES:
        return ALIASES[form["name"]]
    parts = form["name"].split("-")
    candidates = [norm(form["name"])] + [norm("-".join(parts[:i])) for i in range(len(parts) - 1, 0, -1)]
    candidates.append(norm(form["species"]))
    return next((c for c in candidates if learnsets.get(c)), None)


def main():
    forms = json.loads((DATA / "champions.json").read_text())["pokemon"]
    learnsets = parse_learnsets(fetch(f"{RAW}/learnsets.ts"))

    by_form, unmatched = {}, []
    for f in forms:
        sid = resolve(f, learnsets)
        if sid:
            by_form[f["name"]] = sorted(learnsets[sid])
        else:
            unmatched.append(f["name"])

    base = json.loads(fetch(MOVES_JSON))
    pp = fetch_pp()
    overrides = parse_move_overrides(fetch(f"{RAW}/moves.ts"))
    descs = parse_short_descs(fetch(f"{TEXT_URL}/moves.ts"))
    used = {m for moves in by_form.values() for m in moves}
    moves = {}
    for mid in sorted(used):
        b = base.get(mid, {})
        o = overrides.get(mid, {})
        merged = {**b, **{k: v for k, v in o.items() if k != "isNonstandard"}}
        moves[mid] = {
            "name": b.get("name", mid),
            "type": merged.get("type"),
            "category": merged.get("category"),
            "base_power": merged.get("basePower"),
            "accuracy": merged.get("accuracy"),
            "pp": pp.get(mid),  # Serebii (Showdown has no Champions PP)
            "priority": merged.get("priority"),
            "target": merged.get("target"),
            "flags": sorted(merged.get("flags") or {}),  # contact, punch, bite, slicing, pulse, sound, ...
            "multihit": merged.get("multihit"),  # int, or [min, max]
            "short_desc": descs.get(mid),
            "champions_overrides": o or None,
        }

    try:
        c = json.loads(fetch(COMMITS))[0]
        source_commit = {"sha": c["sha"][:10], "date": c["commit"]["author"]["date"]}
    except Exception:  # GitHub rate limit etc. -- provenance is nice-to-have
        source_commit = None

    meta = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "smogon/pokemon-showdown data/mods/champions",
        "learnsets_source_commit": source_commit,
    }
    (DATA / "learnsets.json").write_text(json.dumps({**meta, "learnsets": by_form}, indent=1) + "\n")
    (DATA / "moves.json").write_text(json.dumps({**meta, "moves": moves}, indent=1) + "\n")
    print(f"{len(by_form)}/{len(forms)} forms with learnsets, {len(moves)} moves")
    if unmatched:
        print("no learnset for:", ", ".join(unmatched))
    no_pp = [m for m in moves if moves[m]["pp"] is None]
    if no_pp:
        print("no PP from Serebii for:", ", ".join(no_pp))
    missing = [m for m in moves if m not in base]
    if missing:
        print("moves missing from base moves.json:", ", ".join(missing))


if __name__ == "__main__":
    main()
