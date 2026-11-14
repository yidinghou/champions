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
