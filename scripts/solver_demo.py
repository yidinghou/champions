"""Build scripts/solver_demo.html: an interactive picture of the solver on a real 2v2 position.

    python scripts/solver_demo.py            # writes scripts/solver_demo.html, then open it in a browser

The engine runs here; the page is static (data is embedded), so it can be opened anywhere.

Three searches of the same position are shown:
  * one turn            - every pair of choices is played once under all chance outcomes and scored
  * two turns, exact    - each outcome is itself solved one turn deeper
  * two turns, pruned   - after the first turn, only each side's most promising choices are searched deeper
Every matrix cell is a probability-weighted average over its chance outcomes, and the matrix game is
solved exactly for each side's best mix.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from champions.engine import game                        # noqa: E402
from champions.engine.resolve import resolve             # noqa: E402
from champions.solver import solve                       # noqa: E402
from champions.solver.actions import joint_actions       # noqa: E402
from champions.solver.evaluate import evaluate           # noqa: E402


def sp(species, moves, ability=None):
    return dict(species=species, moves=moves, ability=ability)


TEAMS = [[sp("gyarados", ["surf", "earthquake", "icebeam", "stoneedge"]),
          sp("venusaur", ["gigadrain", "sludgebomb", "earthquake", "sleeppowder"])],
         [sp("gengar", ["shadowball", "sludgebomb", "thunderwave", "icebeam"]),
          sp("dragonite", ["dragonclaw", "earthquake", "icebeam", "extremespeed"])]]

# (name, depth, damage-roll buckets, keep)
VARIANTS = [("One turn", 1, 4, None),
            ("Two turns, exact", 2, 2, None),
            ("Two turns, pruned", 2, 2, 1)]
MIN_PROB = 0.01


def team_view(b):
    return [[{"name": m.species.title(), "hp": m.hp, "max": m.max_hp, "status": m.status,
              "active": i in s.active} for i, m in enumerate(s.team)] for s in b.sides]


def next_value(b, depth, buckets):
    """What the position after a first-turn outcome is worth, with `depth` more turns to look ahead."""
    if b.winner is not None or depth <= 0:
        return evaluate(b)
    return solve(b, depth=depth, buckets=buckets, min_prob=MIN_PROB).value


def build():
    base = game.start(TEAMS, seed=1, format="singles")
    out = {"teams": team_view(base), "variants": []}
    for name, depth, k, keep in VARIANTS:
        buckets = {"damage_roll": k}
        r = solve(base, depth=depth, buckets=buckets, min_prob=MIN_PROB, keep=keep)
        rows, cols = joint_actions(base, 0), joint_actions(base, 1)
        cells = []
        for i, row in enumerate(rows):
            crow = []
            for j, col in enumerate(cols):
                ev = r.matrix[i][j]
                if ev is None:
                    crow.append({"pruned": True})
                    continue
                res = resolve(base, row + col, buckets=buckets, min_prob=MIN_PROB, record=True)
                res.sort(key=lambda pc: -pc[0])
                outcomes = []
                for p, b in res[:10]:
                    outcomes.append({
                        "p": p, "now": evaluate(b), "next": next_value(b, depth - 1, buckets) if depth > 1 else None,
                        "winner": b.winner, "teams": team_view(b),
                        "log": [str(e) for e in b.log if e.turn == b.turn and e.kind != "rng"][:40]})
                crow.append({"ev": ev, "n": len(res), "outcomes": outcomes})
            cells.append(crow)
        out["variants"].append({
            "name": name, "depth": depth, "buckets": k, "keep": keep, "matrix": cells,
            "value": r.value, "row_mix": r.row_mix, "col_mix": r.col_mix,
            "stats": {"seconds": r.stats.seconds, "cells": r.stats.cells, "nodes": r.stats.nodes,
                      "outcomes": r.stats.outcomes, "pruned": r.stats.pruned_cells}})
        out["rows"], out["cols"] = r.rows, r.cols
    return out


def main():
    data = build()
    html = (HERE / "solver_demo_template.html").read_text().replace("__DATA__", json.dumps(data))
    dest = HERE / "solver_demo.html"
    dest.write_text(html)
    for v in data["variants"]:
        s = v["stats"]
        print(f"{v['name']:<20} value {v['value']:+.3f}  {s['seconds']:.2f}s  cells {s['cells']}  pruned {s['pruned']}")
    print("wrote", dest)


if __name__ == "__main__":
    main()
