"""Likely sets from the MunchStats in-game snapshot, as battle-spec fields (for pre-filling opponents).

defaults(name, dex) -> {"moves": [...], "item": id, "ability": id, "nature": id, "sp": {...}}; any field
with no usable data is left out. Everything is checked against `dex` (battle.dex.dex()) so the spec
only contains ids the battle engine accepts. With no snapshot (installed package, never scraped) it
returns {}. Percentages are MunchStats' own, so these are "most common", not "most likely together".
"""
import re

from . import common

_SP = ("hp", "attack", "defense", "special-attack", "special-defense", "speed")
_snap = {}


def _entries():
    if "e" not in _snap:
        snap = common.load("munchstats", "doubles")
        _snap["e"] = snap["pokemon"] if snap else {}
    return _snap["e"]


def _top(pcts, ok):
    """Names from {name: pct}, best first, that pass ok(name)."""
    return [n for n, _ in sorted(pcts.items(), key=lambda kv: -kv[1]) if ok(n)]


def defaults(name, dex):
    e = _entries().get(common.key(name))
    sp = dex["species"].get(name)
    if not e or not sp:
        return {}
    out = {}
    moves = _top(e.get("moves", {}), lambda m: common.key(m) in sp["moves"])
    if moves:
        out["moves"] = [common.key(m) for m in moves[:4]]
    abil = {re.sub(r"[^a-z0-9]+", "-", a.lower()).strip("-") for a in sp["abilities"] + [sp.get("hidden_ability") or ""]}
    ab = _top(e.get("abilities", {}), lambda a: re.sub(r"[^a-z0-9]+", "-", a.lower()).strip("-") in abil)
    if ab:
        out["ability"] = re.sub(r"[^a-z0-9]+", "-", ab[0].lower()).strip("-")
    items = _top(e.get("items", {}), lambda i: common.key(i) in dex["items"])
    if items:
        out["item"] = common.key(items[0])
    nat = _top(e.get("natures", {}), lambda n: n.lower() in dex["natures"])
    if nat:
        out["nature"] = nat[0].lower()
    spreads = sorted(e.get("spreads", {}).items(), key=lambda kv: -kv[1])
    if spreads:
        out["sp"] = dict(zip(_SP, map(int, spreads[0][0].split("/"))))
    return out
