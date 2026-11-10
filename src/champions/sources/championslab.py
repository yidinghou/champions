"""Champions Lab (championslab.xyz) meta page: top-20 doubles usage + winrate, tournament winning teams.

Run:  champions sources championslab [--refresh]

Only what the server renders: one page, the top 20 Pokémon (usage %, winrate) and the first batch of
winning tournament teams (placing, record, field size, six Pokémon). The full 198-Pokémon ranking, the
Singles toggle and per-Pokémon move analysis load client-side and are NOT fetched. The site's
robots.txt sets `ai-train=no`; this is a single low-rate request for personal reference.
"""
import re
import sys
from html import unescape

from . import common

URL = "https://championslab.xyz/meta"
RANK = re.compile(r'<span class="text-xs font-bold w-6[^>]*>(\d+)</span><img alt="([^"]+)".*?'
                  r'<span class="text-\[10px\] font-bold text-white drop-shadow-sm">([\d.]+)<!-- -->%</span>.*?'
                  r'([\d.]+)\s*(?:<!-- -->)?\s*%\s*(?:<!-- -->)?\s*WR', re.S)
TEAM = re.compile(r'<p class="text-sm font-bold truncate">([^<]+)</p><p[^>]*>([^<]*)</p>.*?'
                  r'>(\d+)<!-- -->W-<!-- -->(\d+)<!-- -->L</span><p[^>]*>(\d+)<!-- --> players</p>(.*?)</div></div></div>', re.S)


def parse(html):
    out = {"updated": None, "usage": [], "teams": []}
    m = re.search(r"Last updated\s*(?:<[^>]+>\s*)*([\d/]+)", html)
    out["updated"] = m.group(1) if m else None
    m = re.search(r"(\d[\d,]*) community tournaments \(([\d,]+) teams\)", common.strip_tags(html))
    out["corpus"] = f"{m.group(1)} tournaments, {m.group(2)} teams" if m else None
    for rank, name, usage, wr in RANK.findall(html):
        out["usage"].append({"rank": int(rank), "name": unescape(name), "usage": float(usage), "winrate": float(wr)})
    for who, event, w, l, n, rest in TEAM.findall(html):
        out["teams"].append({"player": unescape(who), "event": unescape(event), "wins": int(w), "losses": int(l),
                             "players": int(n), "team": [unescape(x) for x in re.findall(r'<img alt="([^"]+)"', rest)]})
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    html = common.get(URL, "championslab", "meta", 0, "--refresh" in argv)
    d = parse(html)
    pokemon = {common.key(u["name"]): {"name": u["name"], "rank": u["rank"], "usage": u["usage"],
                                       "winrate": u["winrate"], "as_of": d["updated"]} for u in d["usage"]}
    path = common.save("championslab", "doubles", URL, pokemon,
                       notes=f"top-20 only; corpus: {d['corpus']}; {len(d['teams'])} winning teams in 'teams'")
    snap = common.load("championslab", "doubles")
    snap["teams"] = d["teams"]
    import json
    path.write_text(json.dumps(snap, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(pokemon)} Pokémon, {len(d['teams'])} teams -> {path}")


if __name__ == "__main__":
    main()
