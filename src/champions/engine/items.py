"""Held items: which are modeled, using one up, and the checks the rest of the engine asks.

An item is `mon.item` (an id, or None once used). Items hook in through the registry as "item:<id>":
  on_update           holder, after every action and at the end of the turn (berries, herbs, seeds)
  on_residual         holder, end of turn (Leftovers)
  on_damaging_hit     holder was hit by a damaging move (Rocky Helmet, Air Balloon); ctx.user is the attacker
  on_user_hit         holder hit a target (King's Rock)
  on_after_all_hits   holder's move finished (Shell Bell, Life Orb)
  on_after_hit_target holder was hit and survived (Eject Button, Red Card)
Damage and accuracy items are read directly by the calc and the accuracy stage.
Numbers are Showdown's gen 9 values; Champions may differ (flagged `verify` in the catalogue).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..calc.items import RESIST_BERRY, TYPE_BOOST
from .errors import Unsupported
from .hooks import fire

DATA = Path(__file__).resolve().parents[1] / "data"

STATUS_BERRIES = {"cheriberry": ("par",), "chestoberry": ("slp",), "pechaberry": ("psn", "tox"),
                  "rawstberry": ("brn",), "aspearberry": ("frz",)}
SEEDS = {"electricseed": ("electric", "def"), "grassyseed": ("grassy", "def"),
         "mistyseed": ("misty", "spd"), "psychicseed": ("psychic", "spd")}
MENTAL_HERB_CURES = ("taunt", "encore", "disable")
EXTENDERS = {"heatrock", "damprock", "smoothrock", "icyrock", "terrainextender", "lightclay"}
MODELED_ITEMS = (set(TYPE_BOOST) | set(RESIST_BERRY) | set(STATUS_BERRIES) | set(SEEDS) | EXTENDERS | {
    "muscleband", "wiseglasses", "lifeorb", "expertbelt", "lightball", "choicescarf", "leftovers", "shellbell",
    "rockyhelmet", "focussash", "focusband", "kingsrock", "scopelens", "widelens", "zoomlens", "brightpowder",
    "bigroot", "bindingband", "shedshell", "ironball", "airballoon", "ejectbutton", "redcard", "mentalherb",
    "whiteherb", "sitrusberry", "oranberry", "lumberry", "persimberry", "leppaberry"})
# Held but with nothing to do: Mega Stones are added from the data (Mega is rejected at the choice, so the stone is
# only carried).
INERT_ITEMS = set()
# Known gaps: these raise Unsupported rather than being carried silently.
UNMODELED_ITEMS = {"leek", "metronome", "normalgem"}


@lru_cache(maxsize=None)
def _item_data():
    return json.loads((DATA / "items.json").read_text())["items"]


@lru_cache(maxsize=None)
def _mega_stones():
    return {k for k, v in _item_data().items() if "Mega Evolve" in (v.get("short_desc") or "")}


def item_name(item_id):
    return _item_data().get(item_id, {}).get("name") or item_id


def is_supported_item(item_id):
    """Non-raising check: is this item modeled, or known to do nothing here? None (no item) is fine."""
    return not item_id or item_id in MODELED_ITEMS or item_id in INERT_ITEMS or item_id in _mega_stones()


def check_item(item_id):
    if not is_supported_item(item_id):
        raise Unsupported(f"item not modeled: {item_id}")


def consume(battle, mon, cause=None, **extra):
    """The holder uses its item up."""
    item, mon.item = mon.item, None
    battle.log_event("item", mon=mon.ref, item=item, cause=cause, **extra)
    return item


def can_eat(battle, mon):
    """Berries need an item and no foe with Unnerve on the field. (Herbs and seeds ignore Unnerve.)"""
    return bool(mon.item) and not any(f.ability == "unnerve" for _, f in battle.sides[1 - mon.side].alive_active())


def update_all(battle):
    """Showdown's Update event: every active mon may use a berry, herb or seed, in Speed order."""
    from .turn import speed
    mons = [m for s in battle.sides for _, m in s.alive_active() if m.item]
    mons.sort(key=lambda m: -speed(battle, m))
    for m in mons:
        if m.item and not m.fainted:
            fire(battle, "on_update", m, [f"item:{m.item}"])


def cap_damage(battle, target, dmg):
    """Focus Sash and Focus Band: a hit that would KO leaves 1 HP instead. Returns the damage to deal."""
    if dmg < target.hp:
        return dmg
    if target.item == "focussash" and target.hp == target.max_hp:
        consume(battle, target, cause="survive")
        return target.hp - 1
    if target.item == "focusband" and battle.rng.chance(10, "focusband"):
        battle.log_event("item", mon=target.ref, item="focusband", cause="survive")
        return target.hp - 1
    return dmg


def switch_candidates(battle, mon):
    s = battle.sides[mon.side]
    return [i for i, m in enumerate(s.team) if not m.fainted and i not in s.active]
