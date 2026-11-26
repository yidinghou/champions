# Spike: MCTS without the shortlist, and with a longer one

Status: done (2026-11-25), local. Every option: worse. Top 3 vs top 2: no measurable difference.

## Question

If MCTS stops using the quick damage estimate to cut its options, and considers every legal option instead, is it
still fast enough? Does it play at least as well?

## Why

MCTS doesn't try every option at every position. Before searching, it keeps a **shortlist** per Pokémon: the 2
attacks the quick damage estimate rates highest, Protect, and every switch (`rollout.ROOT`). Issue 1
(`ISSUE_DRAFT_damage_estimate.md`) shows that estimate gets abilities and items wrong. For example, it can spend one
of the 2 attack spots on Earthquake into a Levitate Rotom.

With its default random playouts, the shortlist is the **only** place MCTS uses the estimate. Everything else goes
through the real engine. So if MCTS works without the shortlist, issue 1 no longer affects MCTS at all, without
fixing the estimate. It also follows the "widen the options and let the search decide" approach.

Not covered: the greedy opponent and position scoring still use the estimate. MCTS with random playouts uses neither.

## What changes

Only a setting. No solver code changes.

- Today: `ROOT = dict(moves=2, status=0, switches=2, protect=1)`.
- Spike: `ALL = dict(moves=99, status=99, switches=99)`, which keeps every legal option at every position.

## What we measure

On random doubles positions from `scripts/position_audit.py` (8 Pokémon that include Levitate Rotom and five
Earthquake users):

1. **Size:** how many options each side has per turn (the size of the table MCTS searches), shortlist vs all.
2. **Speed:** within the usual 5-second budget, how many iterations MCTS runs, and how well it covers the first
   turn's options (how many first-turn pairs it tries, and how often).
3. **Strength:** whole games of "MCTS, every option" vs "MCTS, shortlist" with the same budget and sides swapped
   (`scripts/compare_solvers.py --match`).

## Success criteria

- **Fast enough:** a 5-second solve still takes about 5 seconds (no big setup cost), and it still tries most
  first-turn pairs at least a few times.
- **At least as good:** it wins at least half its games against the shortlist version. With a few dozen games,
  only a big gap means something.

## Results

### 1–2. Size and speed (8 random positions, 5 s, one core)

Raw output: `.tmp/spike_sizes_8x5s.txt`, `.tmp/spike_rerun_8x5s.txt` (scripts `.tmp/spike_sizes.py`, `.tmp/spike_rerun.py`).

| Median over 8 positions | Shortlist (today) | Every option |
|---|---|---|
| Options per side on the first turn | 14 | ~70–90 |
| First-turn pairs (table cells) | 196 | 6,160 (31× more) |
| Iterations in 5 s | 1,246 | 1,000 (20% fewer) |
| First-turn pairs tried at least once | 70% | 11% |
| Tries per pair (median) | 2 | 0 |
| Wall time | 5.0 s | 5.1 s |

The machine was busier during this run than during experiment 2. The same top-2 solves later ran about 2.8× more
iterations. Both columns here ran on the same busy machine, so the comparison is fair, but the absolute iteration
counts are low.

- **No setup cost.** Building the option lists takes about 1–3 ms either way, and the solve still finishes in about 5 s.
- **Coverage collapses.** Each iteration gets about 20% slower, but the real problem is the table size. With
  about 1,000 iterations for about 6,000 first-turn pairs, MCTS tries roughly 1 pair in 9, and most pairs are never
  tried. Untried pairs are scored as "this position's average so far", so the pick is mostly guesswork.
- **Top picks:** "every option" matched the shortlist's top pick on **0 of 8** positions. For a baseline, the
  shortlist version rerun with a different seed agreed with itself on only **4 of 8**. So today's MCTS is itself
  noisy at 5 s on one core, and "every option" is noisier still.

### 3. Strength (games)

20 games, 5 s per decision, one core per bot. Random teams from the same 8-Pokémon pool (no Protect), each team
pair played twice with sides swapped. Raw output: `.tmp/spike_match_20x5s.txt` (script `.tmp/spike_match.py`).

| | Every option | Shortlist (today) |
|---|---|---|
| Games won | **5** | **15** |
| Team pairs won both games | 0 | 5 (other 5 pairs split 1–1) |
| Switches, share of choices | 11% | 25% |

Games were short (median 6 turns). With a fair coin, a 5–15 result or more lopsided happens about 4% of the time,
so it's very unlikely to be luck. The match ran 10 games at once on a machine that already had other work running,
so both bots got fewer iterations than they would on a quiet machine. The comparison is fair, but with more time per
move the gap could be smaller.

## Decision

**Removing the shortlist doesn't work at today's speed.** The search has about 31× more first-turn pairs to cover
in the same time, tries only about 1 in 9 of them, and loses 5–15 to the shortlist version. MCTS still needs a
shortlist.

What this means for issue 1:

- MCTS can't avoid the damage estimate by skipping the shortlist. The shortlist has to be **right**, so fixing the
  estimate (`ISSUE_DRAFT_damage_estimate.md`) still matters.
- Making the search much faster wouldn't be enough either. On a quiet machine (about 2,800 iterations in 5 s), 10×
  the iterations would still give only about 4–5 tries per first-turn pair, each try a single random game.

## Experiment 2: top 3 attacks vs top 2

Same as today's shortlist, but it keeps the 3 highest-rated attacks per Pokémon instead of 2:
`{**ROOT, "moves": 3}`.

### Size and speed (the same 8 positions, 5 s, one core)

Raw output: `.tmp/spike_sizes_top3_8x5s.txt` (`.tmp/spike_sizes.py 8 5 top3`).

| Median over 8 positions | Top 2 (today) | Top 3 |
|---|---|---|
| Options per side on the first turn | 14 | 23 |
| First-turn pairs (table cells) | 196 | 529 (2.7× more) |
| Iterations in 5 s | 3,450 | 3,296 (4% fewer) |
| First-turn pairs tried at least once | 84% | 64% |
| Tries per pair (median) | 3 | 1 |

Same top pick on **5 of 8** positions.

### Strength (games)

40 games, 5 s per decision, one core per bot, 8 games at a time. Raw output: `.tmp/spike_match_top3_40x5s.txt`;
pair check: `.tmp/spike_pairs.py`.

| | Top 3 | Top 2 (today) |
|---|---|---|
| Games won | **19** | **21** |
| Team pairs won both games | 1 | 2 |
| Switches, share of choices | 16% | 21% |

In the other **17 of 20** team pairs, each bot won one game, and in every one of them the **same team** won both
games, whichever bot played it. So the teams decided almost every game, and the difference between the bots was
too small to show. (In experiment 1, by comparison, the shortlist bot won 5 of the 10 pairs outright, so there the
bot clearly mattered.)

### Experiment 2 conclusion

**Top 3 and top 2 play about the same.** A 19–21 result is what a coin flip gives. A small difference could still
be hiding, but finding it would take hundreds of games, or a test that removes the team effect, such as judging
individual positions against a stronger reference solve.

## What both experiments say together

- **Some shortlist is needed.** With no shortlist, MCTS spreads its time over about 30× more first-turn pairs and
  loses clearly (5–15).
- **The exact length doesn't matter much.** Going from 2 attacks to 3 (2.7× more pairs) made no measurable
  difference.
- **For issue 1** this is a weak hint, not proof. Top 3 keeps an extra attack, so a blocked attack in the top 2
  doesn't push out the only good one. That this didn't help suggests the estimate's mistakes cost MCTS little in
  this 8-Pokémon pool, where Levitate Rotom is the only blocking ability. Pools with more blocking abilities (e.g.
  Lightning Rod partners) could be different. The greedy opponent and switch scoring are still affected either way.

## Possible follow-ups

- Today's MCTS is itself noisy at 5 s on one core: in experiment 1, rerun with another seed, it picked the same top
  option only half the time. That's worth its own look, separate from issue 1.
- Top 2 attacks by the damage estimate vs 2 random attacks: does the estimate's choice beat chance?
- In experiment 2, side 1 won 29 of 40 games (in experiment 1, 11 of 20). This is probably just which teams were
  drawn, but worth checking if it shows up again.
