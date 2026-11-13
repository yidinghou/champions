"""Cross-check our new_in_mc tags against Pokemon Showdown's Champions roster.

Run:  champions check-roster     (after `champions fetch champions`; exits 1 on mismatch)

Showdown's champions mod marks a Pokemon legal when its formats-data.ts entry has
no isNonstandard and tier != "Illegal". The commit that shipped a regulation flips
newly legal Pokemon from Past/Illegal to legal, so diffing legality before and after
that commit gives the regulation's additions. Update MC_COMMIT for the next regulation.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

REPO = "smogon/pokemon-showdown"
MC_COMMIT = "812501ede865eea397cd6e9a6f040d73ff57cc84"  # "Add Champions Regulation M-C"
RAW = f"https://raw.githubusercontent.com/{REPO}/%s/data/mods/champions/formats-data.ts"
DATA = Path(__file__).parent.parent / "data" / "champions.json"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "champions-notes/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode()


def norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def legal_ids(ts):
    entries, cur = {}, None
    for line in ts.splitlines():
        if m := re.match(r"^\t(\w+): \{$", line):
            cur = entries.setdefault(m.group(1), {})
        elif cur is not None and (m := re.match(r'^\t\t(\w+): "([^"]*)",$', line)):
            cur[m.group(1)] = m.group(2)
    legal = {k for k, v in entries.items() if "isNonstandard" not in v and v.get("tier") != "Illegal"}
    return legal, set(entries)


# Showdown abbreviates some form ids.
ALIASES = {"indeedee-female": "indeedeef"}


def showdown_id(form, legal, known):
    """Showdown id for one of our forms, or None if it isn't legal.
    An exact Showdown entry wins (so illegal Galarian Mr. Mime doesn't inherit legal Mr. Mime);
    only forms Showdown doesn't list at all (cosmetic ones) fall back to a shorter name."""
    parts = form["name"].split("-")
    exact = ALIASES.get(form["name"], norm(form["name"]))
    if exact in known:
        return exact if exact in legal else None
    for c in [norm("-".join(parts[:i])) for i in range(len(parts) - 1, 0, -1)]:
        if c in legal:
            return c
    return None


def main():
    parent = json.loads(fetch(f"https://api.github.com/repos/{REPO}/commits/{MC_COMMIT}"))["parents"][0]["sha"]
    (now, known), (before, _) = legal_ids(fetch(RAW % "master")), legal_ids(fetch(RAW % parent))
    added = now - before
    print(f"Showdown: {len(now)} legal now, {len(before)} before M-C, {len(added)} added")

    forms = json.loads(DATA.read_text())["pokemon"]
    # A Mega only counts as new if Showdown lists that exact Mega as added.
    expected = set()
    for f in forms:
        sid = showdown_id(f, now, known)
        if sid in added and (not f["is_mega"] or sid == norm(f["name"])):
            expected.add(f["name"])
    ours = {f["name"] for f in forms if f["new_in_mc"]}

    for label, names in (("tagged new_in_mc but NOT added by Showdown", ours - expected),
                         ("added by Showdown but NOT tagged new_in_mc", expected - ours)):
        print(f"\n{label} ({len(names)}):", ", ".join(sorted(names)) or "none")

    covered = {showdown_id(f, now, known) for f in forms}
    print("\nShowdown-added ids with no matching form in our data:",
          ", ".join(sorted(added - covered)) or "none")
    sys.exit(0 if ours == expected else 1)


if __name__ == "__main__":
    main()
