"""Load data/mechanics.json and data/compositions.json and check they are consistent."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
CASE_KEYS = ("id", "group", "kind", "status")
KINDS = {"positive", "control", "interaction", "edge"}
STATUSES = {"ok", "verify"}


def load_mechanics(path=None):
    return json.loads(Path(path or DATA / "mechanics.json").read_text())["mechanics"]


def load_compositions(path=None):
    return json.loads(Path(path or DATA / "compositions.json").read_text())["compositions"]


def find_cycle(graph):
    """Return one cycle in {node: [deps]} as a list of nodes (first == last), or None."""
    WHITE, GREY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}
    stack = []

    def visit(n):
        color[n] = GREY
        stack.append(n)
        for d in graph.get(n, ()):
            if d not in color:
                continue
            if color[d] == GREY:
                return stack[stack.index(d):] + [d]
            if color[d] == WHITE:
                found = visit(d)
                if found:
                    return found
        stack.pop()
        color[n] = BLACK
        return None

    for n in graph:
        if color[n] == WHITE:
            found = visit(n)
            if found:
                return found
    return None


def check_catalogue(mechanics=None, compositions=None):
    """Return a list of problem strings; empty means the catalogue is consistent."""
    mechanics = load_mechanics() if mechanics is None else mechanics
    compositions = load_compositions() if compositions is None else compositions
    problems = []
    ids = [m["id"] for m in mechanics]
    for i in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"duplicate mechanic id: {i}")
    known = set(ids)

    for m in mechanics:
        for dep in m.get("depends_on", []):
            if dep not in known:
                problems.append(f"{m['id']}: depends_on unknown mechanic {dep!r}")
        case_ids = set()
        for c in m.get("cases", []):
            problems += _check_case(m["id"], c, case_ids)
    cycle = find_cycle({m["id"]: m.get("depends_on", []) for m in mechanics})
    if cycle:
        problems.append("depends_on cycle: " + " -> ".join(cycle))

    comp_ids = [c["id"] for c in compositions]
    for i in sorted({i for i in comp_ids if comp_ids.count(i) > 1}):
        problems.append(f"duplicate composition id: {i}")
    for comp in compositions:
        uses = set(comp.get("uses", []))
        for u in comp.get("uses", []) + comp.get("depends_on", []):
            if u not in known:
                problems.append(f"{comp['id']}: unknown mechanic {u!r}")
        case_ids = set()
        for c in comp.get("cases", []):
            problems += _check_case(comp["id"], c, case_ids)
            for inv in c.get("involves", []):
                if inv not in uses:
                    problems.append(f"{comp['id']}::{c.get('id')}: involves {inv!r} not in uses")
    return problems


def _check_case(owner, case, seen):
    out = []
    for k in CASE_KEYS:
        if k not in case:
            out.append(f"{owner}: case {case.get('id', '?')} missing {k!r}")
    cid = case.get("id")
    if cid in seen:
        out.append(f"{owner}: duplicate case id {cid!r}")
    seen.add(cid)
    if case.get("kind") not in KINDS:
        out.append(f"{owner}::{cid}: bad kind {case.get('kind')!r}")
    if case.get("status") not in STATUSES:
        out.append(f"{owner}::{cid}: bad status {case.get('status')!r}")
    return out
