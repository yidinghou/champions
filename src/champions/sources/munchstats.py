"""MunchStats in-game stats ([Champions] In-Game Singles/Doubles) from munchstats.com.

Run:  champions sources munchstats [--format doubles|singles] [--limit N] [--refresh] [name ...]

Data is captured by MunchStats from the game's own Battle Data screens (per their About page), so it
is the closest thing to the official source. The game publishes Pokémon usage as a RANK, not a %:
`rank` is filled, `usage` is not; teammates are likewise rank-only (`teammate_ranks`). Moves, items,
abilities, natures and Stat Point spreads are percentages. Server-rendered HTML, no JS needed.
robots.txt asks for Crawl-delay: 10, honoured here (~40 min for 235 Pokémon; pages are cached so
reruns resume). Only the first page load is network; --refresh re-downloads.
"""
import re
import sys
from html import unescape

from . import common

BASE = "https://www.munchstats.com/champions/{fmt}/{name}"
DELAY = 10.0
SECTIONS = {"Moves": "moves", "Items": "items", "Abilities": "abilities", "Natures": "natures",
            "Stat Point Spreads": "spreads"}
ROW = re.compile(r'<span class="left-text"[^>]*>([^<]+)</span>\s*(?:</div>\s*)?<span class="right-text">([\d.]+)%</span>')


def roster(html):
    """{name: rank} from the usage-rank list present on every page."""
    out = {}
    for name, rank in re.findall(r"selectPokemon\('([^']+)'\).*?right-text\">#(\d+)<", html, flags=re.S):
        out.setdefault(unescape(name), int(rank))
    return out


def parse(html):
    e = {}
    parts = re.split(r"<h2>", html)
    for part in parts[1:]:
        title = re.match(r"([^<]+)", part).group(1).strip()
        body = part
        if title in SECTIONS:
            e[SECTIONS[title]] = {unescape(n).strip(): float(p) for n, p in ROW.findall(body)}
        elif title == "Teammates":
            e["teammate_ranks"] = [unescape(n) for n in re.findall(r"class=\"left-text\"[^>]*>([^<]+)<", body)]
    m = re.search(r"info-stat-label\">Rank</span>\s*<span class=\"info-stat-value\">#(\d+)", html)
    e["rank"] = int(m.group(1)) if m else None
    m = re.search(r'id="champions-updated-value">([^<]+)<', html)
    e["as_of"] = m.group(1) if m else None
    return e


def main(argv=None):
    names, limit, refresh, fmt = common.parse_args(sys.argv[1:] if argv is None else argv)
    start = common.get(BASE.format(fmt=fmt, name="Garchomp"), "munchstats", f"{fmt}-Garchomp", DELAY, refresh)
    ranks = roster(start)
    todo = names or [n for n, _ in sorted(ranks.items(), key=lambda kv: kv[1])]
    todo = todo[:limit] if limit else todo
    out = {}
    for i, name in enumerate(todo, 1):
        html = common.get(BASE.format(fmt=fmt, name=name), "munchstats", f"{fmt}-{name}", DELAY, refresh)
        print(f"[{i}/{len(todo)}] {name}{'' if html else ' (404)'}", file=sys.stderr)
        if html:
            e = parse(html)
            e["name"] = name
            out[common.key(name)] = e
    path = common.save("munchstats", fmt, BASE, out,
                       notes="in-game Battle Data screens; usage is rank-only; teammates rank-only")
    print(f"{len(out)} Pokémon -> {path}")


if __name__ == "__main__":
    main()
