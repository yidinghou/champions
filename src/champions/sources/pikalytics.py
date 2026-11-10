"""Pikalytics Champions VGC (doubles) usage from pikalytics.com.

Run:  champions sources pikalytics [--limit N] [--refresh] [name ...]

Source is tournament/Limitless-ladder teams (not the in-game ladder), Regulation M-C, "updated daily".
Per Pokémon: usage %, rank, winrate, moves, teammates, items, abilities (server-rendered).
Stat spreads, natures and cores load client-side and are not scraped. Doubles only.
No crawl-delay in robots.txt; we use 2 s between requests.
"""
import re
import sys
from html import unescape

from . import common

FORMAT = "gen9championsvgc2026regmc"
INDEX = "https://www.pikalytics.com/champions"
URL = f"https://www.pikalytics.com/pokedex/{FORMAT}/{{name}}"
DELAY = 2.0
WRAPPERS = [("moves", "moves_wrapper"), ("teammates", "teammate_wrapper"),
            ("items", "items_wrapper"), ("abilities", "abilities_wrapper")]
ENTRY = re.compile(r'pokedex-move-entry-new.*?(?:data-name="([^"]+)"|pokedex-inline-text(?:-offset)?">([^<]+)<)'
                   r'.*?pokedex-inline-right">([\d.]+)%', re.S)


def roster(html):
    return list(dict.fromkeys(unescape(n) for n in re.findall(rf'href="/pokedex/{FORMAT}/([^"?/]+)"', html)))


def candidates(home):
    """Pikalytics has no full roster page. Use the links on its index plus MunchStats' in-game roster
    (same Showdown-style names, run `champions sources munchstats` first); misses are just 404s."""
    names = roster(home)
    ms = common.load("munchstats", "doubles")
    if ms:
        names += [e["name"] for e in ms["pokemon"].values()]
    return list(dict.fromkeys(names))


def section(html, start):
    """The pokedex-category HTML from `id="<start>"` to the next wrapper of the four we parse."""
    i = html.find(f'id="{start}"')
    if i < 0:
        return ""
    ends = [html.find(f'id="{w}"', i + 10) for _, w in WRAPPERS if w != start]
    ends = [j for j in ends if j > i]
    return html[i:min(ends) if ends else i + 20000]


def parse(html):
    e = {}
    for field, wrapper in WRAPPERS:
        body = section(html, wrapper)
        # entries are split on the entry class so a missing % can't swallow the next row
        rows = {}
        for chunk in body.split("pokedex-move-entry-new")[1:]:
            m = ENTRY.search("pokedex-move-entry-new" + chunk)
            if m:
                rows.setdefault(unescape(m.group(1) or m.group(2)).strip(), float(m.group(3)))
        e[field] = rows
    m = re.search(r'Usage Percent</div>\s*<div[^>]*>([\d.]+)', html)
    e["usage"] = float(m.group(1)) if m else None
    m = re.search(r'Monthly Rank</div>.*?</span>(\d+)<', html, re.S)
    e["rank"] = int(m.group(1)) if m else None
    m = re.search(r'Winrate</div>\s*<div[^>]*>([\d.]+)', html)
    e["winrate"] = float(m.group(1)) if m else None
    return e


def main(argv=None):
    names, limit, refresh, _ = common.parse_args(sys.argv[1:] if argv is None else argv)
    home = common.get(INDEX, "pikalytics", "_index", DELAY, refresh)
    todo = names or candidates(home)
    todo = todo[:limit] if limit else todo
    out = {}
    for i, name in enumerate(todo, 1):
        html = common.get(URL.format(name=name), "pikalytics", name, DELAY, refresh)
        print(f"[{i}/{len(todo)}] {name}{'' if html else ' (404)'}", file=sys.stderr)
        if html:
            e = parse(html)
            e["name"] = name
            out[common.key(name)] = e
    path = common.save("pikalytics", "doubles", URL, out,
                       notes="tournament/Limitless teams, Reg M-C; no spreads/natures (client-side)")
    print(f"{len(out)} Pokémon -> {path}")


if __name__ == "__main__":
    main()
