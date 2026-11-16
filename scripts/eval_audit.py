"""Compare static evaluations on the doubles demo position: one-turn value, top actions, and time.

    python scripts/eval_audit.py
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from champions.engine import game
from champions.solver import search
from champions.solver.evaluate import evaluate, evaluate_hp
from solver_demo_doubles import TEAMS, DEEP

b = game.start(TEAMS, seed=1, format="doubles")
for name, ev in (("hp-diff", evaluate_hp), ("new", evaluate)):
    search.evaluate = ev
    for depth in (1, 2):
        kw = dict(buckets={"damage_roll": 1}, **(DEEP if depth > 1 else {}))
        t0 = time.perf_counter()
        r = search.solve(b, depth=depth, time_limit=600, **kw)
        dt = time.perf_counter() - t0
        top = sorted(zip(r.row_mix, r.rows), reverse=True)[:4]
        print(f"{name:8} depth {depth}: value {r.value:+.3f}  {dt:6.1f}s  cells {r.stats.cells}")
        for p, a in top:
            print(f"      {p:5.2f}  {a}")
