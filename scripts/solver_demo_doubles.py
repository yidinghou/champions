"""Build scripts/solver_demo_doubles.html: the one-turn solver on a real doubles (2 vs 2 active) position.

    python scripts/solver_demo_doubles.py     # writes scripts/solver_demo_doubles.html, then open it in a browser

In doubles each side picks an action for BOTH active Pokemon at once, so a side's choices are the product of
its two slots' choices. The page shows the full payoff matrix (every pair of joint actions, played under all
chance outcomes), then how much of it a top-k pruning keeps, and whether the pruned game gives the same answer.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from champions.engine import game                                   # noqa: E402
from champions.engine.resolve import resolve                        # noqa: E402
from champions.solver import solve                                  # noqa: E402
from champions.solver.actions import joint_actions, slot_choices    # noqa: E402
from champions.solver.evaluate import evaluate                      # noqa: E402
from champions.solver.matrix import prune_top_k, solve_matrix       # noqa: E402


def sp(species, moves, ability):
    return dict(species=species, moves=moves, ability=ability)


# Purple leads Incineroar + Garchomp (bench Venusaur, Rotom); Crimson leads Gengar + Dragonite (bench Gyarados, Salamence)
TEAMS = [[sp("incineroar", ["fakeout", "flamethrower", "closecombat", "nightslash"], "intimidate"),
          sp("garchomp", ["earthquake", "dragonclaw", "rockslide", "stoneedge"], "sandveil"),
          sp("venusaur", ["gigadrain", "sludgebomb", "sleeppowder", "earthquake"], "overgrow"),
          sp("rotom", ["thunderwave", "surf", "shadowball", "willowisp"], "levitate")],
         [sp("gengar", ["shadowball", "sludgebomb", "thunderwave", "icebeam"], "cursedbody"),
          sp("dragonite", ["dragonclaw", "extremespeed", "icebeam", "earthquake"], "innerfocus"),
          sp("gyarados", ["surf", "icebeam", "stoneedge", "earthquake"], "intimidate"),
          sp("salamence", ["dragonclaw", "flamethrower", "earthquake", "rockslide"], "intimidate")]]

BUCKETS = {"damage_roll": 1}      # 1 bucket: fastest; see the solver benchmark for the accuracy tradeoff
MIN_PROB = 0.01
KEEPS = [1, 2, 3, 5]
# Two-turn search: at every turn (the first included) each Pokemon only considers its top 2 damaging moves, best
# status move and best switch by the cheap ranking in solver/prior.py. Pruning the first turn by one-turn payoff
# (keep=k) was tried and is NOT used: it picked the wrong action on 2 of 4 positions that could be solved exactly.
DEEP = dict(moves=2, status=1, switches=1, root_full=False)


def team_view(b):
    return [[{"name": m.species.title(), "hp": m.hp, "max": m.max_hp, "status": m.status,
              "active": i in s.active} for i, m in enumerate(s.team)] for s in b.sides]


def outcome_view(b, p):
    return {"p": p, "score": evaluate(b), "winner": b.winner, "teams": team_view(b),
            "log": [str(e) for e in b.log if e.turn == b.turn and e.kind != "rng"][:60]}


def lift(sub_mix, kept, n):
    full = [0.0] * n
    for a, i in enumerate(kept):
        full[i] = sub_mix[a]
    return full


def _top_outcomes(base, i, j, n=8):
    res = resolve(base, joint_actions(base, 0)[i] + joint_actions(base, 1)[j], buckets=BUCKETS, min_prob=MIN_PROB)
    res.sort(key=lambda pc: -pc[0])
    return res[:n]


def build():
    base = game.start(TEAMS, seed=1, format="doubles")
    r = solve(base, depth=1, buckets=BUCKETS, min_prob=MIN_PROB)      # exact solve of the whole matrix
    M, nr, nc = r.matrix, len(r.rows), len(r.cols)
    row_order = sorted(range(nr), key=lambda i: -sum(M[i]) / nc)                          # best for Purple first
    col_order = sorted(range(nc), key=lambda j: sum(M[i][j] for i in range(nr)))          # best for Crimson first
    prunes, need = [], set()
    for k in KEEPS:
        kr, kc = prune_top_k(M, k)
        t0 = time.perf_counter()
        v, sx, sy = solve_matrix([[M[i][j] for j in kc] for i in kr])
        secs = time.perf_counter() - t0
        x, y = lift(sx, kr, nr), lift(sy, kc, nc)
        row_guarantee = min(sum(x[i] * M[i][j] for i in range(nr)) for j in range(nc))   # what Purple's pruned mix really gets
        col_cap = max(sum(y[j] * M[i][j] for j in range(nc)) for i in range(nr))         # what Crimson's pruned mix really holds Purple to
        supp = lambda m: sorted(i for i, p in enumerate(m) if p > 1e-6)
        prunes.append({"k": k, "rows": kr, "cols": kc, "value": v, "row_guarantee": row_guarantee, "col_cap": col_cap,
                       "same_support": supp(x) == supp(r.row_mix) and supp(y) == supp(r.col_mix),
                       "row_mix": x, "col_mix": y, "solve_ms": secs * 1000})
        need |= {(i, j) for i in kr for j in kc}
    detail = {}
    for i, j in sorted(need):
        res = resolve(base, joint_actions(base, 0)[i] + joint_actions(base, 1)[j], buckets=BUCKETS,
                      min_prob=MIN_PROB, record=True)
        res.sort(key=lambda pc: -pc[0])
        detail[f"{i},{j}"] = {"n": len(res), "outcomes": [outcome_view(b, p) for p, b in res[:8]]}
    per_slot = [{str(s): len(v) for s, v in slot_choices(base, side).items()} for side in (0, 1)]

    # --- two turns ahead -------------------------------------------------------------------------------
    d2 = solve(base, depth=2, buckets=BUCKETS, min_prob=MIN_PROB, **DEEP)
    # d2's matrix covers only the candidate actions it searched; put it back on the full 78 x 88 grid by label
    assert len(set(r.rows)) == nr and len(set(r.cols)) == nc, "action labels must be unique"
    row_at, col_at = {lab: i for i, lab in enumerate(r.rows)}, {lab: j for j, lab in enumerate(r.cols)}
    deep_matrix = [[None] * nc for _ in range(nr)]
    deep_row_mix, deep_col_mix = [0.0] * nr, [0.0] * nc
    for a, la in enumerate(d2.rows):
        deep_row_mix[row_at[la]] = d2.row_mix[a]
        for b, lb in enumerate(d2.cols):
            deep_matrix[row_at[la]][col_at[lb]] = d2.matrix[a][b]
    for b, lb in enumerate(d2.cols):
        deep_col_mix[col_at[lb]] = d2.col_mix[b]
    searched = {(i, j) for i, row in enumerate(deep_matrix) for j, v in enumerate(row) if v is not None}
    deep_filter = {k: DEEP[k] for k in ("moves", "status", "switches")}
    for i, j in sorted(searched):
        key = f"{i},{j}"
        if key not in detail:
            res = resolve(base, joint_actions(base, 0)[i] + joint_actions(base, 1)[j], buckets=BUCKETS,
                          min_prob=MIN_PROB, record=True)
            res.sort(key=lambda pc: -pc[0])
            detail[key] = {"n": len(res), "outcomes": [outcome_view(b, p) for p, b in res[:8]]}
        for o, (p, b) in zip(detail[key]["outcomes"], _top_outcomes(base, i, j)):
            o["next"] = evaluate(b) if b.winner is not None else solve(
                b, depth=1, buckets=BUCKETS, min_prob=MIN_PROB, root_full=False, **deep_filter).value
    deep = {"value": d2.value, "row_mix": deep_row_mix, "col_mix": deep_col_mix,
            "matrix": [[None if v is None else round(v, 4) for v in row] for row in deep_matrix],
            "config": DEEP, "stats": {"seconds": d2.stats.seconds, "nodes": d2.stats.nodes, "cells": d2.stats.cells,
                                      "outcomes": d2.stats.outcomes, "memo_hits": d2.stats.memo_hits}}
    return {
        "teams": team_view(base), "rows": r.rows, "cols": r.cols,
        "matrix": [[round(v, 4) for v in row] for row in M], "row_order": row_order, "col_order": col_order,
        "value": r.value, "row_mix": r.row_mix, "col_mix": r.col_mix, "prunes": prunes, "detail": detail, "deep": deep,
        "per_slot": per_slot,
        "stats": {"seconds": r.stats.seconds, "cells": r.stats.cells, "outcomes": r.stats.outcomes}}


def main():
    data = build()
    html = (HERE / "solver_demo_doubles_template.html").read_text().replace("__DATA__", json.dumps(data))
    dest = HERE / "solver_demo_doubles.html"
    dest.write_text(html)
    s = data["stats"]
    print(f"{len(data['rows'])} x {len(data['cols'])} joint actions, {s['cells']} cells, {s['seconds']:.1f}s, value {data['value']:+.3f}")
    d = data["deep"]
    print(f"two turns: value {d['value']:+.3f}  {d['stats']['seconds']:.1f}s  {d['stats']['cells']} cells")
    for p in data["prunes"]:
        print(f"keep={p['k']}: {len(p['rows'])}x{len(p['cols'])} value {p['value']:+.3f} guarantee {p['row_guarantee']:+.3f} cap {p['col_cap']:+.3f} same support {p['same_support']}")
    print("wrote", dest, f"({dest.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
