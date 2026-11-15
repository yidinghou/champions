"""All randomness goes through here so a game is a function of (teams, seed, choices)."""
from __future__ import annotations

import random


class Rng:
    def __init__(self, seed=0):
        self.seed = seed
        self._r = random.Random(seed)
        self.sink = None  # set by Battle: called as sink(kind, **data) to log each draw

    def _note(self, label, value):
        if self.sink:
            self.sink("rng", label=label, value=value)
        return value

    def randint(self, a, b, label="randint"):
        return self._note(label, self._r.randint(a, b))

    def chance(self, pct, label="chance"):
        """True with probability pct/100. pct >= 100 never draws (no randomness consumed)."""
        if pct >= 100:
            return True
        return self._note(label, self._r.random() * 100 < pct) is True

    def choice(self, seq, label="choice"):
        return seq[self.randint(0, len(seq) - 1, label)]

    def clone(self):
        """Independent copy that continues the same stream. The sink is not copied."""
        c = self.__class__.__new__(self.__class__)
        c.__dict__.update(self.__dict__)
        c._r = random.Random.__new__(random.Random)   # skips Random()'s slow OS-entropy seeding
        c._r.setstate(self._r.getstate())
        c.sink = None
        return c

    def getstate(self):
        v, internal, g = self._r.getstate()
        return [v, list(internal), g]

    def setstate(self, st):
        v, internal, g = st
        self._r.setstate((v, tuple(internal), g))


class ForcedRng(Rng):
    """Replays a fixed list of outcomes (ints for randint, bools for chance). For tests."""

    def __init__(self, values=(), default=None):
        super().__init__(0)
        self.values = list(values)
        self.default = default

    def clone(self):
        c = super().clone()
        c.values = list(self.values)
        return c

    def _next(self, label):
        if self.values:
            return self.values.pop(0)
        if self.default is not None:
            return self.default
        raise AssertionError(f"ForcedRng ran out of values at {label!r}")

    def randint(self, a, b, label="randint"):
        v = self._next(label)
        return self._note(label, max(a, min(b, int(v))))

    def chance(self, pct, label="chance"):
        if pct >= 100:
            return True
        return self._note(label, bool(self._next(label)))


class LabeledRng(Rng):
    """Forced outcomes chosen by label prefix, for catalogue cases.

    rolls: {"accuracy": [False], "crit": [True]} - each key is a label prefix with a queue of outcomes.
    Once a queue is empty (or no key matches) a default applies: damage rolls 100, crit False,
    speed ties pick the first, every other chance succeeds, every other randint takes its low end.
    """
    DEFAULTS = {"damage_roll": 100, "crit": False, "speed_tie": 0}

    def __init__(self, rolls=None):
        super().__init__(0)
        self.rolls = {k: list(v) for k, v in (rolls or {}).items()}

    def clone(self):
        c = super().clone()
        c.rolls = {k: list(v) for k, v in self.rolls.items()}
        return c

    def _take(self, label):
        for prefix, queue in self.rolls.items():
            if label.startswith(prefix) and queue:
                return True, queue.pop(0)
        for prefix, v in self.DEFAULTS.items():
            if label.startswith(prefix):
                return True, v
        return False, None

    def randint(self, a, b, label="randint"):
        ok, v = self._take(label)
        return self._note(label, max(a, min(b, int(v))) if ok else a)

    def chance(self, pct, label="chance"):
        if pct >= 100:
            return True
        ok, v = self._take(label)
        return self._note(label, bool(v) if ok else True)


def _buckets(a, b, k):
    """Split a..b into at most k contiguous groups of near-equal size.
    Returns [(representative value, probability)], the representative being the group's middle."""
    n = b - a + 1
    k = max(1, min(k, n))
    out, start = [], a
    for i in range(k):
        size = n // k + (1 if i < n % k else 0)
        out.append((start + (size - 1) // 2, size / n))
        start += size
    return out


class EnumRng(Rng):
    """Walks a decision tree instead of sampling, so a solver can enumerate chance outcomes.

    Each draw is a branch point with a list of (value, probability) outcomes. `prefix` holds the
    outcome index to take at each branch point in order; past the prefix it takes index 0. After a run,
    `trace` lists (n_outcomes, probabilities, chosen_index) per draw, which is what resolve() uses to
    schedule the other branches. Draws that are certain (chance >= 100, one-value ranges) are not branch points.

    buckets: {label prefix: k} - a randint under that label is split into k groups (see _buckets).
    dists:   {label prefix: [(value, prob), ...]} - an exact distribution that replaces the uniform one.
    """
    DEFAULT_BUCKETS = {"damage_roll": 4}
    DEFAULT_DISTS = {"hit_count": [(1, 0.35), (36, 0.35), (71, 0.15), (86, 0.15)]}  # 2/3/4/5 hits

    def __init__(self, prefix=(), buckets=None, dists=None):
        super().__init__(0)
        self.prefix = list(prefix)
        self.buckets = dict(self.DEFAULT_BUCKETS if buckets is None else buckets)
        self.dists = dict(self.DEFAULT_DISTS if dists is None else dists)
        self.trace = []

    def clone(self):
        c = super().clone()
        c.prefix, c.trace = list(self.prefix), list(self.trace)
        return c

    @property
    def probability(self):
        """Probability of the path taken so far."""
        p = 1.0
        for _, probs, idx in self.trace:
            p *= probs[idx]
        return p

    def _draw(self, label, outcomes):
        if len(outcomes) == 1:
            return outcomes[0][0]
        i = len(self.trace)
        idx = self.prefix[i] if i < len(self.prefix) else 0
        self.trace.append((len(outcomes), [p for _, p in outcomes], idx))
        return outcomes[idx][0]

    def randint(self, a, b, label="randint"):
        outcomes = None
        for prefix, d in self.dists.items():
            if label.startswith(prefix):
                outcomes = d
        if outcomes is None:
            k = next((k for p, k in self.buckets.items() if label.startswith(p)), b - a + 1)
            outcomes = _buckets(a, b, k)
        return self._note(label, max(a, min(b, self._draw(label, outcomes))))

    def chance(self, pct, label="chance"):
        if pct >= 100:
            return True
        if pct <= 0:
            return self._note(label, False)
        p = pct / 100
        return self._note(label, self._draw(label, [(True, p), (False, 1 - p)]))
