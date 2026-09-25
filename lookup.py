#!/usr/bin/env python3
"""Look things up in the local Champions data (no network).

    python3 lookup.py baxcalibur                       # every form matching the name
    python3 lookup.py baxcalibur -n jolly -s attack=32,speed=32   # level-50 stats
    python3 lookup.py rillaboom --moves                # + full movepool
    python3 lookup.py --learns "fake out"              # who learns a move
    python3 lookup.py --learns "fake out" --type grass --new       # combine filters
    python3 lookup.py --type ghost/fire                # dual type (or --type ghost --type fire)
    python3 lookup.py --item "focus"                   # search legal held items
    python3 lookup.py --ability regenerator            # ability text + who has it

Each Pokémon also shows its type matchups (weak to / resists / immune).

Filters (--learns, --type, --new) list matching forms one per line.
Data comes from fetch_champions.py, fetch_moves.py and fetch_reference.py.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from stats import STATS, level50

DATA = Path(__file__).parent / "data"
ABBR = {"hp": "HP", "attack": "Atk", "defense": "Def", "special-attack": "SpA",
        "special-defense": "SpD", "speed": "Spe"}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load(name):
    return json.loads((DATA / name).read_text())


def find_forms(query, forms):
    """Exact form name, else every form of that species, else substring matches."""
    q = query.lower().replace(" ", "-")
    for hit in ([f for f in forms if f["name"] == q],
                [f for f in forms if f["species"] == q],
                [f for f in forms if q in f["name"]]):
        if hit:
            return hit
    return []


def parse_sp(text):
    try:
        return {k: int(v) for k, v in (p.split("=") for p in text.split(","))}
    except ValueError:
        sys.exit(f"bad --sp {text!r}; expected e.g. attack=32,speed=32")


def fmt_stats(stats):
    return "  ".join(f"{ABBR[s]} {stats[s]}" for s in STATS)


def matchups(types, chart):
    """Group attacking types by damage multiplier against a defender with these types."""
    groups = {}
    for att in chart:
        mult = 1
        for t in types:
            mult *= chart[att][t.capitalize()]
        if mult != 1:
            groups.setdefault(mult, []).append(att.lower())
    return groups


def fmt_matchups(groups):
    labels = [(4, "weak x4"), (2, "weak x2"), (0.5, "resists x0.5"), (0.25, "resists x0.25"), (0, "immune")]
    return "\n".join(f"  {label}: {', '.join(groups[m])}" for m, label in labels if m in groups)


def show(form, moves, learnsets, chart, abilities, args):
    tag = "  [new in M-C]" if form["new_in_mc"] else ""
    print(f"{form['name']}  {'/'.join(form['types'])}{tag}")
    print("  abilities:")
    for slug in form["abilities"]:
        a = abilities.get(slug, {})
        flags = (" (hidden)" if slug == form.get("hidden_ability") else "") + (
            " [Champions override]" if a.get("champions_override") else "")
        print(f"    {a.get('name', slug)}{flags}: {a.get('short_desc') or '(no description)'}")
    print(f"  base:  {fmt_stats(form['stats'])}   (BST {sum(form['stats'].values())})")
    sp = parse_sp(args.sp) if args.sp else None
    print(fmt_matchups(matchups(form["types"], chart)))
    label = f"lv50 {args.nature}" + (f", SP {args.sp}" if args.sp else ", no SP")
    print(f"  {label}:  {fmt_stats(level50(form['stats'], args.nature, sp))}")
    pool = learnsets.get(form["name"], [])
    if not args.moves:
        print(f"  moves: {len(pool)}  (--moves to list)")
        return
    print(f"  moves ({len(pool)}):")
    rows = sorted((moves[m] for m in pool if m in moves), key=lambda m: (m["category"], m["type"], m["name"]))
    for m in rows:
        power = m["base_power"] or "--"
        acc = "--" if m["accuracy"] is True else m["accuracy"]
        print(f"    {m['name']:<20} {m['type']:<9} {m['category']:<8} pow {power!s:>3}  acc {acc!s:>3}  pp {m['pp']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", nargs="?", help="Pokémon or form name, e.g. baxcalibur, garchomp-mega-z")
    ap.add_argument("-n", "--nature", default="hardy", help="nature for level-50 stats (default: hardy, neutral)")
    ap.add_argument("-s", "--sp", help="Stat Points, e.g. attack=32,speed=32 (max 32 each, 66 total)")
    ap.add_argument("--moves", action="store_true", help="list the full movepool")
    ap.add_argument("--item", help="search legal held items by name")
    ap.add_argument("--ability", help="search abilities by name and list who has them")
    ap.add_argument("--learns", help="only forms that learn this move")
    ap.add_argument("--type", action="append", metavar="TYPE",
                    help="only forms with this type; repeat or use ghost/fire for a dual type (must have all)")
    ap.add_argument("--new", action="store_true", help="only forms new in Regulation M-C")
    args = ap.parse_args()

    forms = load("champions.json")["pokemon"]
    moves = load("moves.json")["moves"]
    learnsets = load("learnsets.json")["learnsets"]

    if args.item:
        items = load("items.json")["items"]
        hits = [v for v in items.values() if norm(args.item) in norm(v["name"])]
        for v in sorted(hits, key=lambda v: v["name"]):
            print(f"{v['name']:<22} {v['short_desc'] or ''}")
        print(f"{len(hits)} matches")
        return

    if args.ability:
        abilities = load("abilities.json")["abilities"]
        hits = {k: v for k, v in abilities.items() if norm(args.ability) in norm(v["name"])}
        for slug, v in sorted(hits.items(), key=lambda kv: kv[1]["name"]):
            flag = " [Champions override]" if v["champions_override"] else ""
            print(f"{v['name']}{flag}: {v['short_desc']}")
            who = [f["name"] + (" (hidden)" if f.get("hidden_ability") == slug else "") for f in forms if slug in f["abilities"]]
            print(f"  {len(who)} forms: {', '.join(who)}\n")
        if not hits:
            sys.exit(f"no ability matching {args.ability!r}")
        return

    chart = load("types.json")["chart"]
    abilities = load("abilities.json")["abilities"]
    filtering = args.learns or args.type or args.new
    if not args.name and not filtering:
        ap.print_help()
        return
    if args.name:
        forms = find_forms(args.name, forms)
        if not forms:
            sys.exit(f"no Pokémon matching {args.name!r}")
    if args.learns:
        mid = norm(args.learns)
        if mid not in moves:
            sys.exit(f"unknown move {args.learns!r}")
        forms = [f for f in forms if mid in learnsets.get(f["name"], [])]
    if args.type:
        wanted = {t.lower() for arg in args.type for t in re.split(r"[/,]", arg) if t}
        unknown = wanted - {t.lower() for t in chart}
        if unknown:
            sys.exit(f"unknown type: {', '.join(sorted(unknown))}")
        forms = [f for f in forms if wanted <= set(f["types"])]
    if args.new:
        forms = [f for f in forms if f["new_in_mc"]]

    if filtering and not args.name:
        for f in forms:
            print(f"{f['name']:<28} {'/'.join(f['types']):<16} {fmt_stats(f['stats'])}")
        print(f"{len(forms)} matches")
    else:
        for f in forms:
            show(f, moves, learnsets, chart, abilities, args)
            print()


if __name__ == "__main__":
    main()
