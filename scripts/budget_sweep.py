"""Time the speed-ups on the doubles demo: deeper filter narrowing, outcome collapse, parallel workers."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from champions.engine import game
from champions.solver import search
from solver_demo_doubles import TEAMS

if __name__ == "__main__":
    b = game.start(TEAMS, seed=1, format="doubles")
    B = {"damage_roll": 1}
    R3 = dict(moves=3, status=1, switches=1)
    R2 = dict(moves=2, status=1, switches=1)
    search.get_pool(10)      # warm the pool so start-up isn't timed
    cfgs = []
    for w in (1, 10):
        for name, root, deep, mo in (("root m2 / deep m1, out 2", R2, dict(moves=1, status=1, switches=1), 2),
                                     ("root m2 / deep m2, out 3", R2, R2, 3),
                                     ("root m2 / deep m1, out all", R2, dict(moves=1, status=1, switches=1), None)):
            cfgs.append((f"{name} w={w}", dict(root_filter=root, root_full=False, max_out=mo, workers=w, **deep)))
    for name, kw in cfgs:
        t0 = time.perf_counter()
        try:
            r = search.solve(b, depth=2, buckets=B, min_prob=0.05, deep_min_prob=0.05, time_limit=120, **kw)
        except search.SearchTimeout:
            print(f"{name:34} >120s"); continue
        dt = time.perf_counter() - t0
        top = max(zip(r.row_mix, r.rows))
        print(f"{name:34} {dt:6.2f}s v {r.value:+.3f} top {top[0]:.2f} {top[1]}", flush=True)
    t0 = time.perf_counter()
    r = search.solve_budget(b, budget=5.0, workers=10)
    top = max(zip(r.row_mix, r.rows))
    print(f"{'solve_budget(5s, 10 workers)':34} {time.perf_counter()-t0:6.2f}s v {r.value:+.3f} [{r.label}] top {top[0]:.2f} {top[1]}")
