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
