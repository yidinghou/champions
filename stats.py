"""Compute battle stats from base stats. Reads data/champions.json (raw) at call time.

ASSUMPTION: main-series stat rules (IVs, EVs, natures) at level 50. Champions may
handle stat investment differently -- see data/rules.json "stats". Update here once confirmed.

    python3 stats.py baxcalibur jolly     # or: python3 stats.py garchomp-mega-z
"""
import json
import sys
from pathlib import Path

DATA = Path(__file__).parent / "data" / "champions.json"
LEVEL = 50  # fixed in Champions (data/rules.json)
STATS = ["hp", "attack", "defense", "special-attack", "special-defense", "speed"]

# nature -> (raised stat, lowered stat); neutral natures map to None
_UP_DOWN = {
    "lonely": ("attack", "defense"), "brave": ("attack", "speed"),
    "adamant": ("attack", "special-attack"), "naughty": ("attack", "special-defense"),
    "bold": ("defense", "attack"), "relaxed": ("defense", "speed"),
    "impish": ("defense", "special-attack"), "lax": ("defense", "special-defense"),
    "timid": ("speed", "attack"), "hasty": ("speed", "defense"),
    "jolly": ("speed", "special-attack"), "naive": ("speed", "special-defense"),
    "modest": ("special-attack", "attack"), "mild": ("special-attack", "defense"),
    "quiet": ("special-attack", "speed"), "rash": ("special-attack", "special-defense"),
    "calm": ("special-defense", "attack"), "gentle": ("special-defense", "defense"),
    "sassy": ("special-defense", "speed"), "careful": ("special-defense", "special-attack"),
}
NEUTRAL = {"hardy", "docile", "serious", "bashful", "quirky"}


def level50(base, nature="hardy", iv=31, ev=0):
    """base: dict of the six base stats. ev applies to every stat (0-252)."""
    nature = nature.lower()
    if nature not in _UP_DOWN and nature not in NEUTRAL:
        raise ValueError(f"unknown nature: {nature}")
    up, down = _UP_DOWN.get(nature, (None, None))
    out = {}
    for s in STATS:
        core = (2 * base[s] + iv + ev // 4) * LEVEL // 100
        if s == "hp":
            out[s] = core + LEVEL + 10
        else:
            out[s] = core + 5
            if s == up:
                out[s] = out[s] * 110 // 100
            elif s == down:
                out[s] = out[s] * 90 // 100
    return out


def load(name):
    for p in json.loads(DATA.read_text())["pokemon"]:
        if p["name"] == name:
            return p
    raise KeyError(name)


if __name__ == "__main__":
    mon = load(sys.argv[1])
    nature = sys.argv[2] if len(sys.argv) > 2 else "hardy"
    print(mon["name"], nature, list(level50(mon["stats"], nature).values()))
