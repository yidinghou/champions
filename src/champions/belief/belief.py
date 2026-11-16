"""A belief over one opposing Pokemon's hidden set: the prior factors, conditioned on what has been revealed.

Observations (a move used, an item or ability revealed) multiply into one factor and renormalize: exact Bayes.
If an observation has no support in the listed data it is repaired (the most likely sets that include it are
used, at a small prior weight) when it is legal for the species, and flagged `impossible` when it is not.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple, Union

from ..sources.common import key
from . import factors as F
from . import reference as R
from . import support as S
from .prior import IA, NS, MoveSet, SetPrior

EPS = 0.005                      # prior weight given to a repaired (unlisted but legal) observation
VIEWS = ("raw", "project", "strict")


@dataclass(frozen=True)
class MoveSeen:
    move: str


@dataclass(frozen=True)
class ItemSeen:
    item: str


@dataclass(frozen=True)
class AbilitySeen:
    ability: str


Observation = Union[MoveSeen, ItemSeen, AbilitySeen]


@dataclass(frozen=True)
class SetHyp:
    """One concrete set. `spec(species)` is the dict `engine.teams.build_mon` takes."""
    moves: Tuple[str, ...]
    item: Optional[str]
    ability: str
    nature: str
    spread: str
    mega_form: Optional[str] = None      # set when a Mega Stone is held: the already-Mega'd form is simulated

    def spec(self, species: str) -> dict:
        return {"species": self.mega_form or species, "ability": self.ability, "item": self.item,
                "moves": list(self.moves), "nature": self.nature, "sp": self.spread}


def project_set(h: SetHyp) -> SetHyp:
    """The engine-simulable version: unsupported moves deleted, an unsupported ability made inert."""
    return replace(h, moves=tuple(m for m in h.moves if S.move_ok(m)),
                   ability=h.ability if S.ability_ok(h.ability) else S.INERT_ABILITY)


@dataclass
class Archetypes:
    items: List[Tuple[SetHyp, float]]     # most likely first; weights sum to 1 - residual
    residual: float                       # probability not covered by the returned sets
    coverage: S.Coverage
    view: str


def _draw(rng: random.Random, weights: Dict):
    r, acc, last = rng.random(), 0.0, None
    for k, w in weights.items():
        acc += w
        last = k
        if r < acc:
            return k
    return last


class Belief:
    def __init__(self, prior: SetPrior, moves: Dict[MoveSet, float], ia: Dict[IA, float], ns: Dict[NS, float],
                 seen_moves=(), evidence: float = 1.0, notes: Optional[List[str]] = None, impossible: bool = False):
        self.prior, self.moves, self.ia, self.ns = prior, moves, ia, ns
        self.seen_moves = tuple(seen_moves)
        self.evidence = evidence                 # prior probability of everything observed so far
        self.notes = list(notes or [])
        self.impossible = impossible

    @classmethod
    def from_prior(cls, prior: SetPrior) -> "Belief":
        return cls(prior, dict(prior.moves), dict(prior.ia), dict(prior.ns), notes=prior.notes)

    @property
    def species(self) -> str:
        return self.prior.species

    def log_evidence(self) -> float:
        return math.log(self.evidence) if self.evidence > 0 else float("-inf")

    # ---- conditioning -------------------------------------------------------------------------------
    def _with(self, **kw) -> "Belief":
        d = dict(prior=self.prior, moves=self.moves, ia=self.ia, ns=self.ns, seen_moves=self.seen_moves,
                 evidence=self.evidence, notes=self.notes, impossible=self.impossible)
        d.update(kw)
        return Belief(**d)

    def _fail(self, why: str) -> "Belief":
        return self._with(notes=self.notes + [why], impossible=True)

    def condition(self, obs: Observation) -> "Belief":
        if self.impossible:
            return self
        if isinstance(obs, MoveSeen):
            return self._see_move(key(obs.move))
        if isinstance(obs, ItemSeen):
            return self._see_item(key(obs.item))
        if isinstance(obs, AbilitySeen):
            return self._see_ability(key(obs.ability))
        raise TypeError(f"unknown observation: {obs!r}")

    def _see_move(self, m: str) -> "Belief":
        seen = self.seen_moves if m in self.seen_moves else self.seen_moves + (m,)
        if len(seen) > 4:
            return self._fail(f"more than 4 distinct moves revealed: {', '.join(seen)}")
        kept = {c: p for c, p in self.moves.items() if m in c}
        mass = sum(kept.values())
        if mass > 0:
            return self._with(moves=F.normalize(kept), seen_moves=seen, evidence=self.evidence * mass)
        if not R.can_learn(self.species, m):
            return self._fail(f"{m} cannot be learned by {self.species}")
        # not in any listed set: use the likeliest current sets with their weakest unseen move swapped for it
        incl = F.inclusion_of(self.moves)
        repaired: Dict[MoveSet, float] = {}
        for c, p in sorted(self.moves.items(), key=lambda t: -t[1])[:5]:
            swappable = [x for x in c if x not in self.seen_moves]
            if not swappable:
                continue
            out = min(swappable, key=lambda x: incl.get(x, 0.0))
            new = tuple(sorted([x for x in c if x != out] + [m]))
            repaired[new] = repaired.get(new, 0.0) + p
        if not repaired:
            return self._fail(f"cannot fit revealed move {m} into any set")
        return self._with(moves=F.normalize(repaired), seen_moves=seen, evidence=self.evidence * EPS,
                          notes=self.notes + [f"{m} was not in any listed set; used the likeliest sets that include it"])

    def _see_item(self, item: str) -> "Belief":
        kept = {k: p for k, p in self.ia.items() if k[0] == item}
        mass = sum(kept.values())
        if mass > 0:
            return self._with(ia=F.normalize(kept), evidence=self.evidence * mass)
        abil: Dict[str, float] = {}
        for (_, a, mega), p in self.ia.items():
            if mega is None:
                abil[a] = abil.get(a, 0.0) + p
        mega = R.mega_form_for(self.species, item)
        if mega:
            repaired = {(item, key(R.species_table()[mega]["abilities"][0]), mega): 1.0}
        else:
            repaired = {(item, a, None): p for a, p in F.normalize(abil).items()} if abil else {}
        if not repaired:
            return self._fail(f"cannot fit revealed item {item}")
        note = f"{item} was not in the listed items" + ("" if R.is_item(item) else " (and is not in items.json)")
        return self._with(ia=repaired, evidence=self.evidence * EPS, notes=self.notes + [note])

    def _see_ability(self, a: str) -> "Belief":
        kept = {k: p for k, p in self.ia.items() if k[1] == a}
        mass = sum(kept.values())
        if mass > 0:
            return self._with(ia=F.normalize(kept), evidence=self.evidence * mass)
        if a not in R.legal_abilities(self.species):
            return self._fail(f"{a} is not a legal ability for {self.species}")
        items: Dict[Optional[str], float] = {}
        for (i, _, mega), p in self.ia.items():
            if mega is None:
                items[i] = items.get(i, 0.0) + p
        repaired = {(i, a, None): p for i, p in F.normalize(items).items()} or {(None, a, None): 1.0}
        return self._with(ia=repaired, evidence=self.evidence * EPS,
                          notes=self.notes + [f"{a} was not in the listed abilities"])

    # ---- views ----------------------------------------------------------------------------------------
    def marginals(self) -> Dict[str, Dict]:
        out: Dict[str, Dict] = {"moves": F.inclusion_of(self.moves), "items": {}, "abilities": {},
                                "natures": {}, "spreads": {}}
        for (i, a, _), p in self.ia.items():
            out["items"][i] = out["items"].get(i, 0.0) + p
            out["abilities"][a] = out["abilities"].get(a, 0.0) + p
        for (n, s), p in self.ns.items():
            out["natures"][n] = out["natures"].get(n, 0.0) + p
            out["spreads"][s] = out["spreads"].get(s, 0.0) + p
        return out

    def coverage(self) -> S.Coverage:
        return S.coverage(self.moves, self.ia, self.prior.tails)

    def archetypes(self, k: int = 32, view: str = "project", merge_items: bool = True) -> Archetypes:
        """The k most likely sets under `view`, with their probabilities (renormalized within the view).
        Items are ignored when ranking if merge_items (the engine ignores them); each set shows its likeliest item."""
        if view not in VIEWS:
            raise ValueError(f"view must be one of {VIEWS}")
        cov = self.coverage()
        moves: Dict[Tuple[str, ...], float] = {}
        for c, p in self.moves.items():
            if view == "strict" and not all(S.move_ok(m) for m in c):
                continue
            c2 = tuple(m for m in c if S.move_ok(m)) if view == "project" else c
            moves[c2] = moves.get(c2, 0.0) + p
        ia: Dict[tuple, float] = {}
        best_item: Dict[tuple, Tuple[float, Optional[str]]] = {}
        for (item, a, mega), p in self.ia.items():
            if view == "strict" and (mega is not None or not S.ability_ok(a)):
                continue
            a2 = a if view != "project" or S.ability_ok(a) else S.INERT_ABILITY
            k2 = (a2, mega) if merge_items else (item, a2, mega)
            ia[k2] = ia.get(k2, 0.0) + p
            if merge_items and p > best_item.get(k2, (-1.0, None))[0]:
                best_item[k2] = (p, item)
        moves, ia, ns = F.normalize(moves), F.normalize(ia), dict(self.ns)
        order = lambda d: sorted(d.items(), key=lambda t: -t[1])
        out: List[Tuple[SetHyp, float]] = []
        for (mv, iak, nsk), w in F.best_first([order(moves), order(ia), order(ns)]):
            if merge_items:
                a, mega = iak
                item = best_item[iak][1]
            else:
                item, a, mega = iak
            out.append((SetHyp(tuple(mv), item, a, nsk[0], nsk[1], mega), w))
            if len(out) >= k:
                break
        if not moves or not ia:
            out = []
        return Archetypes(out, max(0.0, 1.0 - sum(w for _, w in out)) if out else 1.0, cov, view)

    def sample(self, rng: random.Random, view: str = "raw", require_moves: bool = False) -> Optional[SetHyp]:
        """Draw one set. 'raw' as listed; 'project' with unsupported moves removed; 'strict' only fully simulable
        sets (rejection sampling; None if essentially none exist). require_moves (project view): redraw, up to 100
        times, until the set keeps at least one simulable move. That conditions on being simulable, so it biases the
        draw toward species the engine models better; leave it off to see the inert sets (see Coverage.empty_mass)."""
        if view not in VIEWS:
            raise ValueError(f"view must be one of {VIEWS}")
        if view == "project" and require_moves:
            h = None
            for _ in range(100):
                h = self.sample(rng, view)
                if h.moves:
                    break
            return h
        for _ in range(2000 if view == "strict" else 1):
            item, a, mega = _draw(rng, self.ia)
            nature, spread = _draw(rng, self.ns)
            h = SetHyp(tuple(_draw(rng, self.moves)), item, a, nature, spread, mega)
            if view == "raw":
                return h
            if view == "project":
                return project_set(h)
            if mega is None and S.ability_ok(a) and all(S.move_ok(m) for m in h.moves):
                return h
        return None
