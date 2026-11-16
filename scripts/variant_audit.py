"""Compare intermediate widening settings to the wide reference on the audit positions."""
import sys, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import position_audit as pa
from champions.solver import search

if __name__ == "__main__":
    search.get_pool(10)
    R2s0 = dict(moves=2, status=0, switches=1)
    V = {
     "A1 deep m2 s0 sw1 out1": dict(root_filter=pa.R2, root_full=False, max_out=1, moves=2, status=0, switches=1),
     "F root s0, A out2": dict(root_filter=R2s0, root_full=False, max_out=2, moves=2, status=0, switches=1),
     "G root s0, A out1": dict(root_filter=R2s0, root_full=False, max_out=1, moves=2, status=0, switches=1),
     "H root s0, deep m2 s0 sw1 out1 m1root": dict(root_filter=dict(moves=1, status=0, switches=1), root_full=False, max_out=1, moves=2, status=0, switches=1),
    }
    rnd = random.Random(1)
    res = {k: [] for k in V}
    for n in range(10):
        b = pa.position(rnd)
        ref = pa.run(b, pa.REF)
        for k, kw in V.items():
            r = pa.run(b, kw); res[k].append((abs(r[0] - ref[0]), r[1] == ref[1], r[2]))
    for k, rs in res.items():
        print(f"{k:26} err {sum(x[0] for x in rs)/10:.3f} same {sum(x[1] for x in rs)}/10 mean {sum(x[2] for x in rs)/10:.1f}s max {max(x[2] for x in rs):.1f}s")
