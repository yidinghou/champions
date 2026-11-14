"""Handler registry. Abilities, items and move effects attach to named hook points.

A handler is registered for (hook, source) where source is "effect:<key>", "ability:<id>", "item:<id>"
or "*" (always). fire() runs "*" handlers first, then the handlers for each source in the order given.
Order is explicit, never dict or set iteration, so replays stay deterministic.
"""
from __future__ import annotations

from collections import defaultdict

from .events import HOOK_NAMES

_REGISTRY = defaultdict(list)  # (hook, source) -> [fn]


def on(hook, source="*"):
    if hook not in HOOK_NAMES:
        raise ValueError(f"unknown hook {hook!r}")

    def deco(fn):
        _REGISTRY[(hook, source)].append(fn)
        return fn
    return deco


def fire(battle, hook, ctx, sources=()):
    if hook not in HOOK_NAMES:
        raise ValueError(f"unknown hook {hook!r}")
    for fn in list(_REGISTRY.get((hook, "*"), ())):
        fn(battle, ctx)
    for src in sources:
        for fn in list(_REGISTRY.get((hook, src), ())):
            fn(battle, ctx)


def handlers_for(hook, source):
    return list(_REGISTRY.get((hook, source), ()))
