"""Feasibility spike: how fast is one turn, one clone, and how big is a joint-action matrix?"""
import copy, itertools, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from champions.engine import game, teams

def sp(s, m, a=None): return dict(species=s, moves=m, ability=a)
TEAMS = [
    [sp("incineroar", ["fakeout", "flamethrower", "closecombat", "protect"]),
     sp("garchomp", ["earthquake", "dragonclaw", "rockslide", "protect"]),
     sp("venusaur", ["gigadrain", "sleeppowder", "protect", "toxic"]),
     sp("rotom", ["thunderwave", "protect", "surf", "shadowball"])],
    [sp("garchomp", ["earthquake", "dragonclaw", "rockslide", "protect"]),
     sp("incineroar", ["fakeout", "flamethrower", "closecombat", "protect"]),
     sp("venusaur", ["gigadrain", "sleeppowder", "protect", "toxic"]),
     sp("rotom", ["thunderwave", "protect", "surf", "shadowball"])],
]
try:
    b = game.start(TEAMS, seed=1, format="doubles")
except Exception as e:
    print("start failed:", repr(e)); sys.exit()

def per_slot(b, side):
    out = {}
    for c in game.legal_choices(b, side):
        out.setdefault(c.slot, []).append(c)
    return out

def joints(b, side):
    ps = per_slot(b, side)
    res = []
    for combo in itertools.product(*ps.values()):
        try: game.validate(b, list(combo)); res.append(list(combo))
        except Exception: pass
    return res

j0, j1 = joints(b, 0), joints(b, 1)
print(f"joint actions: side0={len(j0)} side1={len(j1)} matrix cells={len(j0)*len(j1)}")

def quiet(b):
    b.log_event = lambda *a, **k: None          # spike only: kill logging
    b.rng.sink = None
    for s in b.sides:
        for m in s.team: m._log = None
    return b

def clone(b):
    return b.clone(record=False)

N = 200
t = time.perf_counter()
for _ in range(N): c = clone(b)
t_clone = (time.perf_counter() - t) / N

t = time.perf_counter()
n = 0
for i in range(N):
    c = clone(b)
    game.play_turn(c, j0[i % len(j0)] + j1[(i * 7) % len(j1)])
    n += 1
t_turn_incl_clone = (time.perf_counter() - t) / N
t_turn = t_turn_incl_clone - t_clone
print(f"clone: {t_clone*1e6:.0f} us   play_turn: {t_turn*1e6:.0f} us")

# branching: sample outcomes of one cell with different seeds to count distinct end states
import random
cell = j0[0] + j1[0]
ends = set()
for seed in range(300):
    c = clone(b); c.rng._r.seed(seed); game.play_turn(c, cell)
    ends.add(tuple((m.hp, m.status) for s in c.sides for m in s.team))
print(f"distinct end states from ONE cell over 300 seeds: {len(ends)}")

per_cell = t_clone + t_turn
for branches in (1, 10, 30):
    cells = len(j0) * len(j1)
    print(f"1-ply matrix, {branches:>2} outcomes/cell: {cells*branches*per_cell:.1f} s")
print(f"depth-2 (naive, 10 outcomes/cell): {(len(j0)*len(j1)*10)**2*per_cell/60:.0f} min")
