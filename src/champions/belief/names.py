"""Resolve usage-data names ('ninetalesalola', 'Mr. Rime', 'garchomp-mega-z') to engine species slugs.

Usage sites name some species by base name ('mimikyu') where champions.json names a form ('mimikyu-disguised').
Resolution order: exact form key, explicit alias, '<key>breed' (Paldean Tauros), then the species' default form.
"""
from __future__ import annotations

import difflib
from typing import Iterable, List, Optional

from ..sources.common import key
from .reference import species_table

ALIASES = {"indeedeef": "indeedee-female", "basculegionf": "basculegion-female", "meowsticf": "meowstic-female",
           "vivillonfancy": "vivillon"}


class NameIndex:
    """Index of champions.json form names by their join key. Built once; cheap to query."""

    def __init__(self, slugs: Optional[Iterable[str]] = None):
        table = species_table()
        self.slugs = sorted(table if slugs is None else slugs)
        self._by_key = {key(s): s for s in self.slugs}
        self._default = {}                       # base species key -> default form slug
        for s in self.slugs:
            e = table.get(s)
            if e and e["is_default"]:
                self._default[key(e["species"])] = s

    def resolve(self, name: str) -> Optional[str]:
        k = key(name)
        if k in self._by_key:
            return self._by_key[k]
        if k in ALIASES and ALIASES[k] in self.slugs:
            return ALIASES[k]
        if k + "breed" in self._by_key:
            return self._by_key[k + "breed"]
        return self._default.get(k)

    def suggest(self, name: str, n: int = 5) -> List[str]:
        close = difflib.get_close_matches(key(name), list(self._by_key), n=n, cutoff=0.6)
        return [self._by_key[c] for c in close]
