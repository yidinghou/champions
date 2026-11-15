"""Time the endgame solver: depth x chance-splitting x pruning, on a few positions.

    python scripts/solver_bench.py [seconds_per_run]      (default 60)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from champions.engine import game                      # noqa: E402
from champions.solver import SearchTimeout, solve      # noqa: E402

LIMIT = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0


def sp(s, m, a=None, **kw):
    return dict(species=s, moves=m, ability=a, **kw)


POSITIONS = {
    "1v1, 4 moves each (4x4)": (
        [[sp("gyarados", ["surf", "earthquake", "icebeam", "stoneedge"])],
         [sp("dragonite", ["dragonclaw", "earthquake", "icebeam", "extremespeed"])]], "singles"),
    "2v2 singles with switching (5x5)": (
        [[sp("gyarados", ["surf", "earthquake", "icebeam", "stoneedge"]),
          sp("venusaur", ["gigadrain", "sludgebomb", "earthquake", "sleeppowder"])],
         [sp("gengar", ["shadowball", "sludgebomb", "thunderwave", "icebeam"]),
          sp("dragonite", ["dragonclaw", "earthquake", "icebeam", "extremespeed"])]], "singles"),
    "2v1 endgame with switching (5x4)": (
        [[sp("gyarados", ["surf", "earthquake", "icebeam", "stoneedge"], hp=90),
          sp("venusaur", ["gigadrain", "sludgebomb", "earthquake", "sleeppowder"], hp=60)],
         [sp("dragonite", ["dragonclaw", "earthquake", "icebeam", "extremespeed"], hp=80)]], "singles"),
}
CONFIGS = [("1 bucket, keep=3", dict(buckets={"damage_roll": 1}, keep=3)),
           ("4 buckets, prune", dict(buckets={"damage_roll": 4}, keep=3)),
           ("4 buckets, no prune", dict(buckets={"damage_roll": 4}, keep=None))]

print(f"time limit per run: {LIMIT:.0f}s\n")
for pname, (teams, fmt) in POSITIONS.items():
    b = game.start(teams, seed=1, format=fmt)
    print(pname)
    print(f"  {'config':<22}{'depth':>5}{'value':>9}{'time':>9}{'nodes':>8}{'cells':>8}{'outcomes':>10}{'memo hits':>10}{'pruned':>8}")
    for cname, kw in CONFIGS:
        for depth in (1, 2, 3):
            try:
                r = solve(b, depth=depth, time_limit=LIMIT, **kw)
            except SearchTimeout:
                print(f"  {cname:<22}{depth:>5}{'-':>9}{'>' + str(int(LIMIT)) + 's':>9}")
                break
            s = r.stats
            print(f"  {cname:<22}{depth:>5}{r.value:>+9.3f}{s.seconds:>8.2f}s{s.nodes:>8}{s.cells:>8}{s.outcomes:>10}{s.memo_hits:>10}{s.pruned_cells:>8}", flush=True)
    print()
