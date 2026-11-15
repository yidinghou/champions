"""Plain battle state. Mutators log events, so the log is a complete record of what happened."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .events import Event
from .rng import Rng

STAT_KEYS = ("atk", "def", "spa", "spd", "spe", "acc", "eva")
STAGE_MIN, STAGE_MAX = -6, 6


def _cp(v):
    """Copy the mutable containers (dict, list) inside a value; everything else is immutable here."""
    if isinstance(v, dict):
        return {k: _cp(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_cp(x) for x in v]
    return v


@dataclass
class Mon:
    species: str
    types: List[str]            # lowercase, as in champions.json
    ability: str
    item: Optional[str]
    moves: List[str]
    stats: Dict[str, int]       # hp, atk, def, spa, spd, spe at level 50
    hp: int
    max_hp: int
    side: int = 0
    idx: int = 0                # position in the side's team
    stages: Dict[str, int] = field(default_factory=lambda: {k: 0 for k in STAT_KEYS})
    status: Optional[str] = None
    volatiles: Dict[str, Any] = field(default_factory=dict)
    status_turns: int = 0       # sleep turns left, or the Toxic damage counter
    last_move: Optional[str] = None   # Encore and Disable read this
    turns_out: int = 0
    pp: Dict[str, int] = field(default_factory=dict)
    mega: bool = False
    _log: Any = field(default=None, repr=False, compare=False)

    @property
    def ref(self):
        return f"p{self.side + 1}:{self.species}"

    @property
    def fainted(self):
        return self.hp <= 0

    def _emit(self, kind, **data):
        if self._log:
            self._log(kind, mon=self.ref, **data)

    def take(self, dmg):
        """Remove HP (floored at 0). Returns the damage actually dealt."""
        dealt = max(0, min(dmg, self.hp))
        self.hp -= dealt
        self._emit("damage", amount=dealt, hp=f"{self.hp}/{self.max_hp}")
        if self.hp == 0:
            self.volatiles = {}
            self._emit("faint")
        return dealt

    def heal(self, amount):
        gained = max(0, min(amount, self.max_hp - self.hp))
        self.hp += gained
        if gained:
            self._emit("heal", amount=gained, hp=f"{self.hp}/{self.max_hp}")
        return gained

    def boost(self, stat, n, **extra):
        """Change a stage, clamped to -6..+6. Returns the change actually applied."""
        before = self.stages[stat]
        after = max(STAGE_MIN, min(STAGE_MAX, before + n))
        self.stages[stat] = after
        self._emit("boost", stat=stat, change=after - before, stage=after, **extra)
        return after - before

    def add_volatile(self, name, value=True):
        self.volatiles[name] = value
        self._emit("volatile", add=name)

    def remove_volatile(self, name):
        if self.volatiles.pop(name, None) is not None:
            self._emit("volatile", remove=name)

    def set_status(self, status, turns=0):
        self.status, self.status_turns = status, turns
        self._emit("status", add=status)

    def cure_status(self):
        old, self.status, self.status_turns = self.status, None, 0
        if old:
            self._emit("status", cure=old)

    def clone(self, log=None):
        """Fast copy for search. Much cheaper than deepcopy: copies only the mutable fields."""
        c = Mon.__new__(Mon)
        c.__dict__.update(self.__dict__)
        c.types = list(self.types)
        c.moves = list(self.moves)
        c.stats = dict(self.stats)
        c.stages = dict(self.stages)
        c.volatiles = _cp(self.volatiles)
        c.pp = dict(self.pp)
        c._log = log
        return c

    def clear_on_switch(self):
        """Stages and volatiles reset when a mon leaves the field. A status stays; Toxic restarts at 1."""
        if self.status == "tox":
            self.status_turns = 0
        self.stages = {k: 0 for k in STAT_KEYS}
        self.volatiles = {}
        self.last_move = None
        self.turns_out = 0


@dataclass
class Side:
    team: List[Mon]
    active: List[Optional[int]]            # team index per slot, None = empty
    conditions: Dict[str, Any] = field(default_factory=dict)
    mega_used: bool = False

    def mon_at(self, slot):
        i = self.active[slot]
        return None if i is None else self.team[i]

    def alive_active(self):
        return [(s, self.team[i]) for s, i in enumerate(self.active)
                if i is not None and not self.team[i].fainted]

    def has_living(self):
        return any(not m.fainted for m in self.team)

    def clone(self, log=None):
        return Side(team=[m.clone(log) for m in self.team], active=list(self.active),
                    conditions=_cp(self.conditions), mega_used=self.mega_used)


@dataclass
class Battle:
    sides: List[Side]
    rng: Rng
    format: str = "doubles"
    arena: Dict[str, Any] = field(default_factory=dict)   # weather, Trick Room, ...
    turn: int = 0
    log: List[Event] = field(default_factory=list)
    winner: Optional[int] = None
    record: bool = True        # False = skip the event log (for search)

    def __post_init__(self):
        self.rng.sink = self.log_event
        for side in self.sides:
            for m in side.team:
                m._log = self.log_event

    def log_event(self, kind, **data):
        if self.record:
            self.log.append(Event(self.turn, kind, data))

    def clone(self, rng=None, record=None):
        """Independent copy for search. rng: a Rng to use (default: a copy of this one, same stream).
        record: keep logging in the copy (default: same as this battle; a copy that records gets this log)."""
        record = self.record if record is None else record
        b = Battle.__new__(Battle)
        b.format, b.turn, b.winner, b.record = self.format, self.turn, self.winner, record
        b.arena = _cp(self.arena)
        b.log = list(self.log) if record else []
        b.rng = rng if rng is not None else self.rng.clone()
        b.rng.sink = b.log_event if record else None
        b.sides = [s.clone(b.log_event if record else None) for s in self.sides]
        return b

    def mon(self, side, slot):
        return self.sides[side].mon_at(slot)

    def events(self, kind=None, **match):
        """Log entries of a kind whose data contains every key=value in match."""
        return [e for e in self.log if (kind is None or e.kind == kind)
                and all(e.data.get(k) == v for k, v in match.items())]
