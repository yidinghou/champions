"""Prior over one species' hidden set, built from scraped usage data (sources/snapshots).

The data only gives marginals (move %, item %, ability %, nature %, spread %), so the prior is a product of
three small joint factors instead of a flat list of sets:
  moves  - which 4 moves (a conditional-Bernoulli model matched to each move's usage rate)
  ia     - (item, ability, mega form), where a Mega Stone forces the Mega form's ability
  ns     - (nature, spread), independent marginals for now
MunchStats is the primary source; Pikalytics only fills species MunchStats lacks (its move scale differs, so it
is never mixed per field). Everything not listed by the source (move tail, unlisted spreads) is reported in `tails`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

from .. import stats as stats_mod
from ..sources import common
from ..sources.common import key
from . import factors as F
from . import reference as R
from .names import NameIndex

STALE_DAYS = 30
MAX_MOVES_LISTED = 12             # Pikalytics lists dozens; keep the most used so the set space stays small
DEFAULT_NATURE, DEFAULT_SPREAD = "hardy", "0/0/0/0/0/0"
_AS_OF_FORMATS = ("%B %d, %Y at %H:%M UTC", "%b %d, %Y, %I:%M %p")

MoveSet = Tuple[str, ...]
IA = Tuple[Optional[str], str, Optional[str]]        # (item id, ability id, mega form slug)
NS = Tuple[str, str]                                 # (nature, "hp/atk/def/spa/spd/spe")


@dataclass
class SetPrior:
    species: str                                     # engine species slug
    source: str
    as_of: Optional[str]
    moves: Dict[MoveSet, float]
    ia: Dict[IA, float]
    ns: Dict[NS, float]
    tails: Dict[str, float]                          # fraction of each field's mass the source did not list
    notes: List[str] = field(default_factory=list)
    defaulted: List[str] = field(default_factory=list)   # fields filled with a neutral default


def _valid_spread(s: str) -> bool:
    try:
        v = [int(x) for x in s.split("/")]
    except ValueError:
        return False
    return len(v) == 6 and sum(v) <= stats_mod.MAX_SP_TOTAL and all(0 <= x <= stats_mod.MAX_SP_PER_STAT for x in v)


def _natures() -> set:
    return set(stats_mod._UP_DOWN) | set(stats_mod.NEUTRAL)


def _marginal(pcts: Dict[str, float], ok: Callable[[str], bool], notes: List[str], what: str):
    """{key: pct} -> (renormalized probabilities over the legal keys, listed mass fraction 0..1)."""
    kept = {}
    for name, pct in pcts.items():
        k = name if what == "spread" else key(name)
        if pct > 0 and ok(k):
            kept[k] = kept.get(k, 0.0) + pct
        elif pct > 0:
            notes.append(f"dropped {what} {name!r}")
    total = sum(kept.values())
    listed = min(1.0, sum(p for p in pcts.values() if p > 0) / 100.0)
    return ({k: v / total for k, v in kept.items()} if total > 0 else {}), listed


def build_prior(species: str, entry: dict, source: str) -> Optional[SetPrior]:
    """One species' prior from a usage entry, or None if the entry has no moves."""
    notes: List[str] = []
    defaulted: List[str] = []
    mv = {key(m): pct for m, pct in (entry.get("moves") or {}).items() if pct > 0}
    legal = {m: p for m, p in mv.items() if R.can_learn(species, m)}
    if len(legal) < len(mv):
        notes.append(f"dropped {len(mv) - len(legal)} move(s) not in the learnset")
    if not legal:
        return None
    top = sorted(legal.items(), key=lambda t: -t[1])[:MAX_MOVES_LISTED]
    names = [m for m, _ in top]
    p = F.scale_inclusion([pct for _, pct in top])
    moves = F.combo_distribution(names, F.fit_inclusion(p))
    # munchstats move rates are out of 400 (4 slots x 100%); the share beyond the listed moves is the tail
    tail_moves = max(0.0, (400.0 - sum(pct for _, pct in top)) / 400.0) if source == "munchstats" else None

    item_p, item_listed = _marginal(entry.get("items") or {}, lambda _: True, notes, "item")   # labels only: keep all
    unknown = sorted(i for i in item_p if i and not R.is_item(i))
    if unknown:
        notes.append(f"item(s) not in items.json: {', '.join(unknown)}")
    abil_p, abil_listed = _marginal(entry.get("abilities") or {}, lambda a: a in R.legal_abilities(species), notes, "ability")
    if not abil_p:
        first = key(R.species_table()[species]["abilities"][0])
        abil_p, abil_listed = {first: 1.0}, 0.0
        defaulted.append("ability")
    if not item_p:
        item_p, item_listed = {None: 1.0}, 0.0
        defaulted.append("item")
    ia: Dict[IA, float] = {}
    for item, pi in item_p.items():
        mega = R.mega_form_for(species, item) if item else None
        if mega:
            ability = key(R.species_table()[mega]["abilities"][0])
            ia[(item, ability, mega)] = ia.get((item, ability, mega), 0.0) + pi
        else:
            for ability, pa in abil_p.items():
                ia[(item, ability, None)] = ia.get((item, ability, None), 0.0) + pi * pa

    nat_p, nat_listed = _marginal(entry.get("natures") or {}, lambda n: n in _natures(), notes, "nature")
    spr_p, spr_listed = _marginal(entry.get("spreads") or {}, _valid_spread, notes, "spread")
    if not nat_p:
        nat_p, nat_listed = {DEFAULT_NATURE: 1.0}, 0.0
        defaulted.append("nature")
    if not spr_p:
        spr_p, spr_listed = {DEFAULT_SPREAD: 1.0}, 0.0
        defaulted.append("spread")
    ns = {(n, s): pn * ps for n, pn in nat_p.items() for s, ps in spr_p.items()}

    tails = {"items": 1.0 - item_listed, "abilities": 1.0 - abil_listed, "natures": 1.0 - nat_listed,
             "spreads": 1.0 - spr_listed}
    if tail_moves is not None:
        tails["moves"] = tail_moves
    if defaulted:
        notes.append("defaulted: " + ", ".join(defaulted))
    return SetPrior(species=species, source=source, as_of=entry.get("as_of"), moves=moves, ia=ia, ns=ns,
                    tails=tails, notes=notes, defaulted=defaulted)


def _parse_when(text: Optional[str]) -> Optional[datetime]:
    for fmt in _AS_OF_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    return None


def _age_warning(snap: dict, label: str, now: datetime) -> Optional[str]:
    """Warn if the snapshot's own data date (as_of) or, failing that, our fetch time is old, missing or in the future."""
    when = next((w for w in (_parse_when(e.get("as_of")) for e in snap["pokemon"].values()) if w), None)
    basis = "data date"
    if when is None:
        try:
            when = datetime.fromisoformat(snap.get("fetched_at"))
            when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)      # a bare timestamp is read as UTC
            basis = "fetch date"
        except (TypeError, ValueError):
            return f"{label}: no usable date, cannot tell how fresh it is"
    days = (now - when).days
    if days < 0:
        return f"{label}: {basis} is in the future ({when.date()})"
    if days > STALE_DAYS:
        return f"{label}: {basis} {when.date()} is {days} days old (over {STALE_DAYS})"
    return None


class PriorBook:
    """Priors for every species the usage data covers. Built lazily per species and cached."""

    def __init__(self, entries: Dict[str, Tuple[str, dict]], warnings: List[str], names: NameIndex):
        self._entries = entries                       # slug -> (source, entry)
        self._cache: Dict[str, Optional[SetPrior]] = {}
        self.warnings = warnings
        self.names = names

    def species(self) -> List[str]:
        return sorted(self._entries)

    def get(self, species: str) -> Optional[SetPrior]:
        slug = self.names.resolve(species)
        if slug is None or slug not in self._entries:
            return None
        if slug not in self._cache:
            source, entry = self._entries[slug]
            self._cache[slug] = build_prior(slug, entry, source)
        return self._cache[slug]


def load_priors(source: str = "munchstats-doubles", fallback: Optional[str] = "pikalytics-doubles",
                loader: Callable = common.load, names: Optional[NameIndex] = None,
                now: Optional[datetime] = None) -> PriorBook:
    """Read the primary snapshot (and the fallback, for species the primary lacks). `source` is '<site>-<format>';
    `loader(site, format)` returns a snapshot dict or None (tests pass a stub)."""
    names = names or NameIndex()
    now = now or datetime.now(timezone.utc)
    warnings: List[str] = []
    entries: Dict[str, Tuple[str, dict]] = {}
    for label, is_fallback in ((source, False), (fallback, True)):
        if not label:
            continue
        site, fmt = label.rsplit("-", 1)
        snap = loader(site, fmt)
        if snap is None:
            warnings.append(f"{label}: no snapshot found")
            continue
        warn = _age_warning(snap, label, now)
        if warn and not is_fallback:
            warnings.append(warn)
        unresolved, used = [], 0
        for k, entry in snap["pokemon"].items():
            slug = names.resolve(k)
            if slug is None:
                if not (is_fallback and "mega" in k):      # fallback Mega keys are skipped anyway
                    unresolved.append(k)
                continue
            if not entry.get("moves"):
                continue
            if is_fallback and (slug in entries or R.species_table()[slug]["is_mega"]):
                continue                                # fallback: only species the primary lacks, never Mega keys
            if slug not in entries:
                entries[slug] = (site, entry)
                used += 1
        if unresolved:
            warnings.append(f"{label}: {len(unresolved)} name(s) did not resolve: {', '.join(unresolved[:8])}")
        if is_fallback and used:
            warnings.append(f"{label}: used for {used} species the primary source lacks (move scale differs; nature/spread defaulted)")
    return PriorBook(entries, warnings, names)
