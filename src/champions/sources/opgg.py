"""OP.GG Pokémon Champions pokédex (Singles view) -> common snapshot, with cached pages.

Run:  champions sources opgg [--limit N] [--refresh] [name ...]      (names as in champions.json)

Reuses the parser in champions.fetch.opgg (moves + Stat Point spreads; Singles only, because the Doubles
tab is client-side). The older `champions fetch opgg` still writes data/opgg_spreads.json + the review doc.
"""
import json
import sys

from ..fetch import opgg as old
from . import common

DELAY = 1.0


def main(argv=None):
    names, limit, refresh, _ = common.parse_args(sys.argv[1:] if argv is None else argv)
    mons = json.loads((old.DATA / "champions.json").read_text())["pokemon"]
    species = {p["name"]: p["species"] for p in mons}
    todo = [n.lower() for n in names] or [p["name"] for p in mons if p["is_default"] or p["is_mega"]]
    todo = [n for n in todo if n in species]       # names the local roster doesn't know are skipped
    todo = todo[:limit] if limit else todo
    out = {}
    for i, name in enumerate(todo, 1):
        html = used = None
        for slug in old.slugs(name, species[name]):
            html = common.get(old.URL.format(slug), "opgg", slug, DELAY, refresh)
            if html:
                used = slug
                break
        print(f"[{i}/{len(todo)}] {name}{'' if html else ' (404)'}", file=sys.stderr)
        if html:
            e = old.parse(html)
            out[common.key(name)] = {
                "name": name, "slug": used, "as_of": e["updated"],
                "moves": {m["name"]: m["usage"] for m in e["moves"]},
                "spreads": {"/".join(str(s["sp"][k]) for k in old.STATS): s["usage"] for s in e["spreads"]}}
    path = common.save("opgg", "singles", old.URL, out, notes="Singles ladder; no rank/usage % per Pokémon parsed")
    print(f"{len(out)} Pokémon -> {path}")


if __name__ == "__main__":
    main()
