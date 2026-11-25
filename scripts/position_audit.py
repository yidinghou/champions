"""Run the speed settings on many random doubles positions; compare each to a wide reference.

    python scripts/position_audit.py [n_positions] [seed]
"""
import random, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from champions.engine import game
from champions.solver import search
from champions.solver.evaluate import evaluate, evaluate_hp

def sp(s, m, a, **kw): return dict(species=s, moves=m, ability=a, **kw)
POOL = [("incineroar", ["fakeout", "flamethrower", "closecombat", "nightslash"], "intimidate"),
        ("garchomp", ["earthquake", "dragonclaw", "rockslide", "stoneedge"], "sandveil"),
        ("venusaur", ["gigadrain", "sludgebomb", "sleeppowder", "earthquake"], "overgrow"),
        ("rotom", ["thunderwave", "surf", "shadowball", "willowisp"], "levitate"),
        ("gengar", ["shadowball", "sludgebomb", "thunderwave", "icebeam"], "cursedbody"),
        ("dragonite", ["dragonclaw", "extremespeed", "icebeam", "earthquake"], "innerfocus"),
        ("gyarados", ["surf", "icebeam", "stoneedge", "earthquake"], "intimidate"),
        ("salamence", ["dragonclaw", "flamethrower", "earthquake", "rockslide"], "intimidate")]

def with_protect(m): return m[:3] + ["protect"]

def position(rnd, protect=False):
    """A random doubles board. protect=True swaps each mon's last move for Protect; the random draws are the same
    either way, so the board is the same one with or without it."""
    mons = rnd.sample(POOL, 8)
    teams = []
    for half in (mons[:4], mons[4:]):
        t = []
        for s, m, a in half:
            kw = {"hp": rnd.choice([100, 100, 100, 70, 40])} if rnd.random() < 0.5 else {}
            t.append(sp(s, with_protect(m) if protect else m, a, **kw))
        teams.append(t)
    return game.start(teams, seed=1, format="doubles")

R2 = dict(moves=2, status=1, switches=1); D1 = dict(moves=1, status=1, switches=1)
FAST = dict(root_filter=R2, root_full=False, max_out=2, **D1)
MID = dict(root_filter=R2, root_full=False, max_out=3, **R2)
REF = dict(root_filter=R2, root_full=False, max_out=None, **R2)
B = {"damage_roll": 1}

def run(b, kw, w=10, depth=2):
    t0 = time.perf_counter()
    r = search.solve(b, depth=depth, buckets=B, min_prob=0.05, deep_min_prob=0.05, time_limit=300, workers=w, **kw)
    top = max(zip(r.row_mix, r.rows))[1]
    return r.value, top, time.perf_counter() - t0

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    rnd = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    search.get_pool(10)
    rows = []
    for k in range(n):
        b = position(rnd)
        try:
            ref = run(b, REF); mid = run(b, MID); fast = run(b, FAST)
            d1 = run(b, dict(root_filter=dict(moves=3, status=1, switches=1), root_full=False), depth=1)
            t0 = time.perf_counter(); bud = search.solve_budget(b, 5.0, workers=10); tb = time.perf_counter() - t0
            btop = max(zip(bud.row_mix, bud.rows))[1]
            # same position, old HP-diff evaluation, wide reference
            search.evaluate = evaluate_hp; old = run(b, REF, w=1) if False else None; search.evaluate = evaluate
        except Exception as e:
            print(f"pos {k}: skipped ({type(e).__name__}: {e})"); continue
        rows.append((ref, mid, fast, d1, (bud.value, btop, tb, bud.label)))
        print(f"pos {k}: ref {ref[0]:+.3f} {ref[2]:5.1f}s | mid {mid[0]:+.3f} {mid[2]:5.1f}s {'=' if mid[1]==ref[1] else 'X'} | "
              f"fast {fast[0]:+.3f} {fast[2]:4.1f}s {'=' if fast[1]==ref[1] else 'X'} | d1 {d1[0]:+.3f} {d1[2]:4.1f}s {'=' if d1[1]==ref[1] else 'X'} | "
              f"budget {bud.value:+.3f} {tb:4.1f}s [{bud.label}] {'=' if btop==ref[1] else 'X'}", flush=True)
    if rows:
        m = len(rows)
        for name, i in (("mid", 1), ("fast", 2), ("d1", 3)):
            err = sum(abs(r[i][0] - r[0][0]) for r in rows) / m
            same = sum(r[i][1] == r[0][1] for r in rows)
            t = sum(r[i][2] for r in rows) / m
            print(f"{name:6} mean |value err| {err:.3f}  same top action {same}/{m}  mean {t:.1f}s")
        same = sum(r[4][1] == r[0][1] for r in rows)
        print(f"budget mean |value err| {sum(abs(r[4][0]-r[0][0]) for r in rows)/m:.3f}  same top {same}/{m}  "
              f"max time {max(r[4][2] for r in rows):.1f}s")
