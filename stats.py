"""Compute battle stats from base stats. Reads data/champions.json (raw) at call time.

Champions uses Stat Points (SP) instead of EVs/IVs: 66 SP total, max 32 per stat, each SP = +1
stat at level 50, fixed 31 IVs. Nature ("Stat Alignment") is applied AFTER SP are added.
Formula per champsdex.com; total/cap/+1 per SP also on Game8. Confirmed in-game by the user.

    python3 stats.py baxcalibur jolly speed=32,attack=32
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


MAX_SP_TOTAL, MAX_SP_PER_STAT = 66, 32


def level50(base, nature="hardy", sp=None):
    """base: dict of the six base stats. sp: dict of stat -> Stat Points (default none)."""
    nature = nature.lower()
    if nature not in _UP_DOWN and nature not in NEUTRAL:
        raise ValueError(f"unknown nature: {nature}")
    sp = sp or {}
    if sum(sp.values()) > MAX_SP_TOTAL or any(v > MAX_SP_PER_STAT for v in sp.values()):
        raise ValueError(f"SP over limit ({MAX_SP_TOTAL} total, {MAX_SP_PER_STAT} per stat)")
    up, down = _UP_DOWN.get(nature, (None, None))
    out = {}
    for s in STATS:
        core = (2 * base[s] + 31) * LEVEL // 100
        if s == "hp":
            out[s] = core + LEVEL + 10 + sp.get(s, 0)
        else:
            out[s] = core + 5 + sp.get(s, 0)
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
    sp = {k: int(v) for k, v in (p.split("=") for p in sys.argv[3].split(","))} if len(sys.argv) > 3 else None
    print(mon["name"], nature, list(level50(mon["stats"], nature, sp).values()))
