"""solve_budget(5s) vs the wide reference on random doubles positions.   python scripts/budget_audit.py [n] [seed]"""
import random, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import position_audit as pa
from champions.solver import search

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    rnd = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    search.get_pool(10)
    errs, same, times, fb = [], 0, [], 0
    for k in range(n):
        b = pa.position(rnd)
        ref = pa.run(b, pa.REF)
        t0 = time.perf_counter(); r = search.solve_budget(b, 7.0, workers=10); dt = time.perf_counter() - t0
        top = max(zip(r.row_mix, r.rows))[1]
        errs.append(abs(r.value - ref[0])); same += top == ref[1]; times.append(dt); fb += r.label != "2 turns"
        print(f"pos {k}: ref {ref[0]:+.3f} | budget {r.value:+.3f} {dt:4.1f}s [{r.label}] {'=' if top == ref[1] else 'X'}", flush=True)
    print(f"mean |value err| {sum(errs)/n:.3f}  same top {same}/{n}  mean {sum(times)/n:.1f}s  max {max(times):.1f}s  fell back {fb}/{n}")
