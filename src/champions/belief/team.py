"""Belief over an opposing team: which of the previewed species were brought, and each one's hidden set.

Team preview shows all six (doubles: bring 4; singles: bring 3). A species that has appeared must be among those
brought. The prior over which subset is uniform unless an `affinity` score per teammate pair is supplied, in which
case a subset's weight is exp(beta * sum of its pair scores); the usage data has no usable numbers for this yet.
"""
from __future__ import annotations

import itertools
import math
import random
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

from . import factors as F
from .belief import Belief, Observation
from .prior import PriorBook


class TeamBelief:
    def __init__(self, species: Sequence[str], beliefs: Dict[str, Belief], subsets: Dict[FrozenSet[str], float],
                 leads: Tuple[str, ...] = (), bring: int = 4):
        self.species = tuple(species)
        self.beliefs = beliefs
        self.subsets = subsets
        self.leads = tuple(leads)
        self.bring = bring

    @classmethod
    def from_preview(cls, species_list: Sequence[str], book: PriorBook, leads: Sequence[str] = (), bring: int = 4,
                     affinity: Optional[Dict[Tuple[str, str], float]] = None, beta: float = 0.0) -> "TeamBelief":
        slugs = []
        for s in species_list:
            slug = book.names.resolve(s)
            if slug is None:
                raise ValueError(f"unknown species {s!r}; did you mean {', '.join(book.names.suggest(s)) or 'nothing close'}?")
            slugs.append(slug)
        if len(set(slugs)) != len(slugs):
            raise ValueError("duplicate species in the preview")
        if len(slugs) < bring:
            raise ValueError(f"need at least {bring} species to bring {bring}")
        beliefs = {}
        for slug in slugs:
            prior = book.get(slug)
            if prior is None:
                raise ValueError(f"no usage data for {slug}")
            beliefs[slug] = Belief.from_prior(prior)
        subsets = {}
        for combo in itertools.combinations(slugs, bring):
            w = 1.0
            if affinity and beta:
                w = math.exp(beta * sum(affinity.get((a, b), affinity.get((b, a), 0.0))
                                        for a, b in itertools.combinations(combo, 2)))
            subsets[frozenset(combo)] = w
        tb = cls(slugs, beliefs, F.normalize(subsets), bring=bring)
        lead_slugs = []
        for name in leads:
            slug = book.names.resolve(name)
            if slug not in beliefs:
                raise ValueError(f"lead {name!r} is not in the preview")
            lead_slugs.append(slug)
        return tb.appeared(*lead_slugs).with_leads(lead_slugs) if lead_slugs else tb

    def _copy(self, **kw) -> "TeamBelief":
        d = dict(species=self.species, beliefs=self.beliefs, subsets=self.subsets, leads=self.leads, bring=self.bring)
        d.update(kw)
        return TeamBelief(**d)

    def with_leads(self, leads: Sequence[str]) -> "TeamBelief":
        return self._copy(leads=tuple(leads))

    def appeared(self, *species: str) -> "TeamBelief":
        """Condition on these species having appeared in battle (so they were brought)."""
        slugs = []
        for s in species:
            if s not in self.beliefs:
                raise ValueError(f"{s!r} is not on this team")
            slugs.append(s)
        kept = {sub: p for sub, p in self.subsets.items() if all(s in sub for s in slugs)}
        if not kept or sum(kept.values()) <= 0:
            raise ValueError(f"cannot bring all of {', '.join(slugs)} with a team of {self.bring}")
        return self._copy(subsets=F.normalize(kept))

    def condition(self, species: str, obs: Observation) -> "TeamBelief":
        """Condition one species' set on a revealed move/item/ability. It must have appeared, so it was brought."""
        tb = self.appeared(species)
        beliefs = dict(tb.beliefs)
        beliefs[species] = beliefs[species].condition(obs)
        return tb._copy(beliefs=beliefs)

    def p_brought(self, species: str) -> float:
        return sum(p for sub, p in self.subsets.items() if species in sub)

    def sample_team(self, rng: random.Random, view: str = "project", require_moves: bool = False) -> List[dict]:
        """One plausible opposing team as engine specs: leads first, then the rest in preview order."""
        sub = None
        r, acc = rng.random(), 0.0
        for s, p in self.subsets.items():
            acc += p
            sub = s
            if r < acc:
                break
        order = [s for s in self.leads if s in sub] + [s for s in self.species if s in sub and s not in self.leads]
        team = []
        for s in order:
            h = self.beliefs[s].sample(rng, view, require_moves)
            if h is None:
                raise RuntimeError(f"no {view}-simulable set for {s}")
            team.append(h.spec(s))
        return team

    def weighted_teams(self, n: int, rng: random.Random, view: str = "project",
                       require_moves: bool = False) -> List[Tuple[List[dict], float]]:
        """n sampled teams with equal weight (a Monte Carlo stand-in for the full distribution)."""
        return [(self.sample_team(rng, view, require_moves), 1.0 / n) for _ in range(n)]
