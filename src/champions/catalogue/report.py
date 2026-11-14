"""Per-mechanic coverage: how many stubs are runnable and passing, and which kinds are missing."""
from __future__ import annotations

from .cases import all_cases, include_verify
from .load import load_compositions, load_mechanics
from .runner import run_case

KINDS = ("positive", "control", "interaction")


def build(verify=None):
    """Return one row per mechanic/composition: stubs, runnable, passing, failing ids, kinds missing."""
    verify = include_verify() if verify is None else verify
    mechanics, compositions = load_mechanics(), load_compositions()
    by_id = {}
    for owner, case in all_cases(mechanics, compositions):
        row = by_id.setdefault(owner["id"], {
            "id": owner["id"], "type": owner.get("type", "composition"), "depends_on": owner.get("depends_on", []),
            "stubs": 0, "runnable": 0, "passing": 0, "failing": [], "kinds_runnable": set()})
        row["stubs"] += 1
        if "run" not in case or (case["status"] == "verify" and not verify):
            continue
        row["runnable"] += 1
        if run_case(owner, case).passed:
            row["passing"] += 1
            row["kinds_runnable"].add(case["kind"])
        else:
            row["failing"].append(case["id"])
    for row in by_id.values():
        row["missing"] = [k for k in KINDS if k not in row["kinds_runnable"]] if row["runnable"] else list(KINDS)
        row["upstream_failing"] = [d for d in row["depends_on"] if by_id.get(d, {}).get("failing")]
    return list(by_id.values())


def format_table(rows):
    out = [f"{'mechanic':<20}{'stubs':>6}{'runnable':>10}{'passing':>9}  missing kinds"]
    for r in rows:
        miss = ",".join(r["missing"]) if r["runnable"] else "(stub only)"
        note = f"  FAILING: {', '.join(r['failing'])}" if r["failing"] else ""
        up = f"  upstream failing: {', '.join(r['upstream_failing'])}" if r["failing"] and r["upstream_failing"] else ""
        out.append(f"{r['id']:<20}{r['stubs']:>6}{r['runnable']:>10}{r['passing']:>9}  {miss}{note}{up}")
    tot = lambda k: sum(r[k] for r in rows)
    out.append(f"{'total':<20}{tot('stubs'):>6}{tot('runnable'):>10}{tot('passing'):>9}")
    return "\n".join(out)
