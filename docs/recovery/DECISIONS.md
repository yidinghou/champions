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

## 031 · Charge moves: one forced release, Showdown's rules

**Choice.** Electro Shot, Meteor Beam, Solar Beam, Solar Blade and Sky Attack are modeled. Dig, Fly, Dive, Bounce and
Phantom Force (semi-invulnerable on the charge turn) are a later issue. The choices were made in
`docs/charge-moves-decisions.html`:
- **Release turn.** `legal_choices` offers one `Move`: the stored move at the stored slot, with no switch and no Mega
  Evolution. So MCTS branches by 1 there, and an RL action mask has one action.
- **Anything else is refused.** `validate` raises on any other choice. Showdown instead quietly swaps a move choice
  for the locked one (but refuses a switch). Refusing makes a bug in a UI or an agent's mask show up at once. Encore
  keeps its quiet override.
- **State.** The charge is `volatiles["charging"] = {move, target: [side, slot]}`, read through
  `volatiles.locked_move`. It isn't a volatile status in the game's sense. It lives there so switching, fainting,
  cloning and the MCTS key handle it with no new code.
- **Log.** A new `prepare` event carries the game's line ("absorbed electricity!"). The `charging` volatile's own
  add and remove events are hidden from the text log.
- **Solver.** No evaluator weight for a charging Pokémon. The +1 Sp. Atk already counts, and the search plays the
  release.
- **Mechanics.** All 14 rulings follow Showdown, checked against `smogon/pokemon-showdown` master on 2026-11-26:
  - PP is spent on the charge turn only.
  - The weather is read when the move is used (Mega Sol counts as sun).
  - The charge turn can't be blocked or miss.
  - A failed move on the release turn loses the charge.
  - The release targets the slot, not the Pokémon.
  - Solar Beam and Solar Blade hit at half power in rain, sand or snow.

**Why.** Electro Shot is on 96% of Archaludon sets and Solar Beam on 63% of Charizard's. Both are top-used Pokémon,
and the engine refused them, so the explorer, the belief model and the solver played them with the wrong sets.

**Measured.**
- `tests/test_charge.py` pins each ruling, and the 13 scripted cases in `data/mechanics.json` (`charge-moves`) run.
- A random self-play fuzz (150 doubles games, 2,119 turns, 1,194 charge turns, with 577 Protect blocks, 148 sleep
  and 89 flinch failures) holds three invariants:
  - a charging slot has exactly one legal choice;
  - a charge and its release spend exactly 1 PP between them;
  - no charge outlives its release turn.
- The full suite passes (534 tests).

**Not done.**
- The explorer's charging chip on the board card and the "forced" tag in Choices (option b). They are waiting on a
  static POC; for now the charge turn shows as a move with no target and the game's line as a note.
- The semi-invulnerable moves.
- Sheer Force's boost on Electro Shot. Only Archaludon learns the move, and it can't have Sheer Force.

**Reproduce.**

```
PYTHONPATH=src .venv/bin/python -m unittest tests.test_charge
CHAMPIONS_CASE=charge-moves PYTHONPATH=src .venv/bin/python -m unittest tests.test_catalogue_cases
```
