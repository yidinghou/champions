"""Scrape OP.GG's Pokémon Champions Pokédex for Stat Point spreads and move usage (Singles view).

Run:  champions fetch opgg [--limit N] [name ...]     (stdlib only, ~1 request/second)

EXPERIMENTAL, held on a branch for manual review. Writes data/opgg_spreads.json and a
human-readable review file docs/opgg_review.md; neither is read by anything else yet.
Only the default (Singles) view is in the server-rendered HTML; the Doubles tab loads client-side
and is not scraped. OP.GG has no public API, so this parses page text and may break on redesigns.
Slugs: champions.json "venusaur-mega" -> OP.GG "mega-venusaur". Misses (HTTP 404) are recorded.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ..stats import MAX_SP_PER_STAT, MAX_SP_TOTAL, STATS, level50

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
REVIEW = ROOT.parent.parent / "docs" / "opgg_review.md"
URL = "https://op.gg/pokemon-champions/pokedex/{}"
DELAY = 1.0
LABELS = {"HP": "hp", "Attack": "attack", "Defense": "defense", "Sp. Atk": "special-attack",
          "Sp. Def": "special-defense", "Speed": "speed"}


def slug(name):
    """champions.json form name -> OP.GG slug (megas are prefixed, not suffixed)."""
    m = re.match(r"^(.+?)-mega(-[xyz])?$", name)
    return f"mega-{m.group(1)}{m.group(2) or ''}" if m else name


def fetch(name):
    req = urllib.request.Request(URL.format(slug(name)), headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def text(html):
    t = re.sub(r"<[^>]+>", "|", html)
    return re.sub(r"\|[\s|]*\|", "|", t)


def parse(html):
    """{'updated', 'base', 'spreads': [{rank, usage, sp}], 'moves': [{name, usage}]} from a page."""
    t = text(re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S))
    out = {"updated": None, "base": {}, "spreads": [], "moves": []}
    if m := re.search(r"Updated\|([^|]+)\|", t):
        out["updated"] = m.group(1)
    for label, key in LABELS.items():
        if m := re.search(rf"\|{re.escape(label)}\|(\d+)\|", t.split("Type Effectiveness")[0]):
            out["base"][key] = int(m.group(1))
    i = html.find(">Stat Points</div>")
    if i >= 0:
        seg = text(html[i:i + 40000])
        pat = r"\|(\d+)\|([\d.]+)%(?:\|[^|]{0,20}){0,4}?" + "".join(rf"\|{re.escape(l)}\|(\d+)" for l in LABELS)
        for m in re.finditer(pat, seg):
            sp = dict(zip(LABELS.values(), map(int, m.groups()[2:])))
            out["spreads"].append({"rank": int(m.group(1)), "usage": float(m.group(2)), "sp": sp})
    ms = t.split("|Moves|", 2)[-1]
    for m in re.finditer(r"\|(\d+)\|([\d.]+)%\|([^|]+)\|(?:Physical|Special|Status)\|", ms):
        out["moves"].append({"name": m.group(3), "usage": float(m.group(2))})
    return out


def check(entry):
    """Problems vs ground truth (66 SP total, 32 per stat); empty list = OK."""
    bad = []
    for s in entry["spreads"]:
        if sum(s["sp"].values()) > MAX_SP_TOTAL or max(s["sp"].values()) > MAX_SP_PER_STAT:
            bad.append(f"spread #{s['rank']} breaks SP limits: {s['sp']}")
    return bad


def review_md(results, base):
    L = ["# OP.GG spreads — manual review", "",
         "Singles view only. Check anything odd, then approve or reject the branch. "
         "Final stats assume the nature shown (OP.GG's spread table doesn't state one: "
         "hardy = no nature).", ""]
    ok = [r for r in results if r["spreads"]]
    L.append(f"{len(results)} pages fetched, {len(ok)} with spreads, "
             f"{sum(1 for r in results if r['problems'])} with problems, "
             f"{sum(1 for r in results if r['base_mismatch'])} base-stat mismatches vs champions.json.\n")
    for r in results:
        L.append(f"## {r['name']}")
        if r["problems"] or r["base_mismatch"]:
            L += [f"- ⚠ {p}" for p in r["problems"] + r["base_mismatch"]]
        if not r["spreads"]:
            L += ["- no spreads on page", ""]
            continue
        L += [f"Updated {r['updated']}", "",
              "| # | usage | HP | Atk | Def | SpA | SpD | Spe | → level-50 stats (hardy) |",
              "|---|---|---|---|---|---|---|---|---|"]
        for s in r["spreads"][:5]:
            final = level50(base[r["name"]], "hardy", s["sp"])
            L.append(f"| {s['rank']} | {s['usage']}% | " + " | ".join(str(s["sp"][k]) for k in STATS)
                     + " | " + "/".join(str(final[k]) for k in STATS) + " |")
        L.append("")
    return "\n".join(L)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    names = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--limit")]
    mons = json.loads((DATA / "champions.json").read_text())["pokemon"]
    base = {p["name"]: p["stats"] for p in mons}
    todo = names or [p["name"] for p in mons if p["is_default"] or p["is_mega"]]
    todo = todo[:limit] if limit else todo
    results, misses = [], []
    for n, name in enumerate(todo, 1):
        html = fetch(name)
        if html is None:
            misses.append(name)
        else:
            e = parse(html)
            e["name"] = name
            e["problems"] = check(e)
            e["base_mismatch"] = [f"base {k}: OP.GG {v} vs champions.json {base[name][k]}"
                                  for k, v in e["base"].items() if base[name][k] != v]
            results.append(e)
        print(f"[{n}/{len(todo)}] {name}{' (404)' if html is None else ''}", file=sys.stderr)
        time.sleep(DELAY)
    DATA.joinpath("opgg_spreads.json").write_text(json.dumps(
        {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": URL,
         "view": "singles", "misses": misses, "pokemon": results}, indent=1) + "\n")
    REVIEW.write_text(review_md(results, base) + "\n")
    print(f"{len(results)} ok, {len(misses)} misses -> data/opgg_spreads.json, docs/opgg_review.md")


if __name__ == "__main__":
    main()
