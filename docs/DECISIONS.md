# Decisions

Numbering continues the old codebase's decision log (001–029). Each entry says what was chosen, what was measured, and how to reproduce it.

## 030 · MCTS and rollouts offer Protect and every switch

**Choice.** The root options of `solver/rollout.py` and `solver/mcts.py` (`rollout.ROOT`) are the top 2 damaging moves, Protect, and every switch per slot: `dict(moves=2, status=0, switches=2, protect=1)`. Bring-4 doubles has at most 2 on the bench, so `switches=2` is every switch. The root table grows from 8×8 to 14×14 on teams without Protect and 23×23 on teams with it. `search.LIVE`, `FALLBACK` and `recommend.py` are unchanged (`protect=0` ranks Protect with the other status moves, as before). The old options stay available as `OLD_ROOT` for comparisons.

**Why.** The old root could not choose Protect at all, and offered only the best switch. A known-answer position (`tests/test_rollout.py::protect_or_lose`: Protect beats a burned 1 HP Extreme Speed user) is worth +1 with the new options and −1 with the old ones, in both rollouts and MCTS.

**Measured: does it win games?** Not shown. Each row is 10 games on Protect teams (every mon's last move is Protect), 2 s per move, one core, new options (`mcts`) against old (`mcts-old`), sides swapped on each team pair:

| Bot picks its move by | Playouts | New | Old |
|---|---|---|---|
| sampling its mix | random | 5 | 5 |
| sampling its mix | greedy | 6 | 4 |
| its top option | random | 5 | 5 |
| its top option, second seed | random | 5 | 5 |

The new bots chose Protect for 20–28% of their choices and switched 11–19% of the time; the old ones never Protected and switched 8–14%. So the options are used, but 10 games cannot separate a 5–5 from a real difference of a few points. These runs did not reproduce the loss that sampling a mix spread over 23 options might be expected to cause, and they do not show a gain either.

**Not done.** Longer runs (20+ games, 5 s per move, more seeds). If sampling the wide mix does turn out to cost games, the next step is to drop options with a tiny share of the mix in `solve_mcts` and renormalize.

**Reproduce.**

```
PYTHONPATH=src .venv/bin/python scripts/compare_solvers.py 1 --match 10 --bots mcts,mcts-old --budget 2 --protect
PYTHONPATH=src .venv/bin/python scripts/compare_solvers.py 1 --match 10 --bots mcts-greedy,mcts-greedy-old --budget 2 --protect
PYTHONPATH=src .venv/bin/python scripts/compare_solvers.py 1 --match 10 --bots mcts,mcts-old --budget 2 --protect --top
PYTHONPATH=src .venv/bin/python scripts/compare_solvers.py 8 2 --match 10 --bots mcts,mcts-old --budget 2 --protect --top
```

Add `--shard I/N` to split games over processes, and `--json FILE` to keep every game (winner, turns, and each bot's choices, Protects and switches).
