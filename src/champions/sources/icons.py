"""Reference sprites for every roster form, used to recognise Pokémon in screenshots.

Run:  champions sources icons [--refresh] [name ...]      (names as in champions.json)

Primary source: Pikalytics' Champions sprites (128 px, same small front-facing render style as the
game's team-select icons), tried under a few file-name spellings. Fallback for default forms only:
Champions Lab's 512 px art by Pokédex number. Cosmetic variants with no sprite (Pikachu caps, ...) are
reported as misses, not guessed. Writes sources/icons/<name>.png and sources/icons/index.json.
"""
import json
import re
import sys
from pathlib import Path

from . import common

PIKA = "https://cdn.pikalytics.com/images/championssprites/{}.png"
LAB = "https://championslab.xyz/sprites/{}.png"
OUT = common.SOURCES / "icons"
DELAY = 0.5
DATA = Path(__file__).resolve().parent.parent / "data" / "champions.json"


def pika_names(name):
    """Candidate Pikalytics file names for a champions.json name, best first.
    'charizard-mega-x' -> 'charizard_megax'; 'farfetchd-galar' -> 'farfetchd_galar'."""
    base = name.replace("-mega-", "_mega").replace("-", "_")
    out = [base, name.replace("-", "_"), re.sub(r"_mega([xyz])$", r"_mega_\1", base)]
    return list(dict.fromkeys(out))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    refresh = "--refresh" in argv
    want = {a for a in argv if not a.startswith("--")}
    mons = json.loads(DATA.read_text())["pokemon"]
    OUT.mkdir(parents=True, exist_ok=True)
    index, misses = {}, []
    for i, p in enumerate(mons, 1):
        name = p["name"]
        if want and name not in want:
            continue
        data = src = None
        for cand in pika_names(name):
            data = common.get_bytes(PIKA.format(cand), "pikalytics-icons", cand, DELAY, refresh)
            if data:
                src = PIKA.format(cand)
                break
        if not data and p["is_default"]:
            data = common.get_bytes(LAB.format(p["dex_id"]), "championslab-icons", str(p["dex_id"]), DELAY, refresh)
            src = LAB.format(p["dex_id"]) if data else None
        print(f"[{i}/{len(mons)}] {name}{'' if data else ' (no icon)'}", file=sys.stderr)
        if data:
            (OUT / f"{name}.png").write_bytes(data)
            index[name] = {"source": src, "bytes": len(data)}
        else:
            misses.append(name)
    (OUT / "index.json").write_text(json.dumps({"icons": index, "misses": misses}, indent=1) + "\n")
    print(f"{len(index)} icons, {len(misses)} without -> {OUT}")


if __name__ == "__main__":
    main()
