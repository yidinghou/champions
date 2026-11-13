"""Shared helpers: polite cached HTTP, name normalisation, snapshot read/write.

Snapshot shape (one JSON file per source+format, sources/snapshots/<source>-<format>.json):
  {source, format, url, fetched_at, notes, pokemon: {<key>: entry}}
Entry fields (all optional; a source fills what it publishes). Values are percentages 0-100:
  name, rank, usage, winrate, as_of,
  moves/items/abilities/natures/teammates: {name: pct}, spreads: {"hp/atk/def/spa/spd/spe": pct}
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SOURCES = REPO / "sources"
SNAPSHOTS = SOURCES / "snapshots"
CACHE = SOURCES / "cache"          # raw HTML, gitignored; makes reruns resumable and parsers re-runnable
UA = "champions-local-research/0.1 (personal, low-rate; see github Yiding Hou/champions)"


def key(name):
    """Join key across sources: 'Mr. Rime' / 'mr-rime' -> 'mrrime'; 'Garchomp-Mega-Z' -> 'garchompmegaz'."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def get(url, source, slug, delay, refresh=False, ua=UA):
    """HTML for url, cached at cache/<source>/<slug>.html. Sleeps `delay` s only after a network hit.
    Returns None on 404."""
    path = CACHE / source / (re.sub(r"[^\w.-]", "_", slug) + ".html")
    if path.exists() and not refresh:
        return path.read_text()
    url = urllib.parse.quote(url, safe=":/?=&%")          # names like "Farfetch’d" are not ASCII
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            html = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            time.sleep(delay)
            return None
        raise
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    time.sleep(delay)
    return html


def strip_tags(html):
    html = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def save(source, fmt, url, pokemon, notes=""):
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    out = SNAPSHOTS / f"{source}-{fmt}.json"
    out.write_text(json.dumps({
        "source": source, "format": fmt, "url": url, "notes": notes,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pokemon": pokemon}, indent=1, ensure_ascii=False) + "\n")
    return out


def load(source, fmt):
    p = SNAPSHOTS / f"{source}-{fmt}.json"
    return json.loads(p.read_text()) if p.exists() else None


def parse_args(argv):
    """-> (names, limit, refresh, format). Shared flags: --limit N, --refresh, --format singles|doubles."""
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    fmt = argv[argv.index("--format") + 1] if "--format" in argv else "doubles"
    skip = {argv.index(f) + 1 for f in ("--limit", "--format") if f in argv}
    names = [a for i, a in enumerate(argv) if not a.startswith("--") and i not in skip]
    return names, limit, "--refresh" in argv, fmt
