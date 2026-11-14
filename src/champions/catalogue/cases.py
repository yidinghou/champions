"""Which catalogue stubs can run: those with a `run` block. `verify` stubs are skipped by default,
because their expected value has not been checked against a source (set CHAMPIONS_INCLUDE_VERIFY=1)."""
from __future__ import annotations

import os

from .load import load_compositions, load_mechanics


def include_verify():
    return os.environ.get("CHAMPIONS_INCLUDE_VERIFY") == "1"


def all_cases(mechanics=None, compositions=None):
    """Every (owner, case) pair, runnable or not."""
    mechanics = load_mechanics() if mechanics is None else mechanics
    compositions = load_compositions() if compositions is None else compositions
    return [(o, c) for o in list(mechanics) + list(compositions) for c in o.get("cases", [])]


def runnable_cases(mechanics=None, compositions=None, verify=None):
    verify = include_verify() if verify is None else verify
    return [(o, c) for o, c in all_cases(mechanics, compositions)
            if "run" in c and (verify or c["status"] != "verify")]


def case_name(owner, case):
    return f"{owner['id']}::{case['id']}"
