# DRAFT issue: the solver's quick damage estimate ignores abilities and items that block moves

Status: fixed locally on `feature/mcts` (2026-11-25), not filed. See "Done" below.

## What goes wrong

The solver can't simulate every move every time it decides, so it uses a quick estimate of "how much of the
target's HP would this move remove?". That estimate only checks the **type chart**.

When a move is actually used, the engine also checks **abilities and items** that stop it. Some make the target
immune (Levitate, Air Balloon, Bulletproof), some absorb the move (Volt Absorb, Water Absorb, Sap Sipper, Motor
Drive), and some pull it away from the Pokémon it was aimed at (Lightning Rod, Storm Drain). The estimate knows
none of these, so it rates blocked moves as strong. A few things work the other way, making a move hit when the
type chart says it shouldn't (Scrappy, Iron Ball).

## Examples (checked against the engine)

| Attack | Solver's estimate | What really happens |
|---|---|---|
| Gyarados Earthquake → Rotom (Levitate) | removes 74% of Rotom's HP | 0 damage: Rotom is floating |
| Venusaur Sludge Bomb → Chesnaught (Bulletproof) | removes 86% | 0 damage: Bulletproof blocks it |
| Rotom Thunderbolt → Gyarados, whose partner Raichu has Lightning Rod | knocks Gyarados out | 0 damage: Raichu pulls the Thunderbolt to itself, takes nothing and gets +1 Sp. Atk |
| Rotom Thunderbolt → Jolteon (Volt Absorb) | removes 19% | 0 damage: Jolteon heals instead |

Type-chart immunities are already handled correctly. For example, the estimate knows Earthquake does nothing to a
Flying type.

## Why it matters

The same estimate is used in four places, so the mistake shows up in all of them:

1. **Which attacks MCTS considers.** MCTS only looks at the two strongest-looking attacks per Pokémon. A blocked
   attack can take one of those two spots and push out a real option, so the search never considers it.
2. **The greedy test opponent.** It always uses its strongest-looking attack, so it repeats a blocked attack every
   turn. (In the replay, Gyarados and Dragonite Earthquake into Levitate Rotom almost every turn.) That makes it
   weaker than intended, so "MCTS beats greedy" proves less than it seems.
3. **Judging switches.** A switch is scored by how hard the incoming Pokémon hits minus how hard it gets hit. Rotom
   switching in against an Earthquake user looks dangerous, when Rotom is actually immune to Earthquake.
4. **Judging positions.** The search scores positions partly by who threatens whom. That uses the same type-chart-only
   damage, so a blocked attack still counts as a threat.

## Why it happens (in the code)

Two separate pieces of code answer "does this move hit this target?", and they don't agree:

- **The engine**, when a move is actually used, runs it through a series of steps (`engine/pipeline/__init__.py`).
  Some steps remove targets the move can't touch: `absorb.check` (Volt Absorb, Water Absorb, Sap Sipper, Motor
  Drive, Lightning Rod, Storm Drain) and `immunity.check` (type chart, plus Levitate, Air Balloon, Bulletproof,
  Iron Ball, Scrappy). Lightning Rod and Storm Drain first pull the move onto themselves (`redirect_target`). Each
  step does two jobs at once: it **decides** ("Rotom has Levitate, so Earthquake misses") and **acts on it**. Acting
  means writing "immune" or "redirect" to the battle log, healing Jolteon, or boosting Raichu. Because the deciding
  and the acting are mixed together, nothing outside the engine can ask the question without also changing the
  battle.
- **The solver's estimate** (`pressure`, and the similar helpers for switch and position scoring) skips those steps
  and goes straight to the damage formula (`calc.damage`). That formula only knows the type chart, because in the
  engine it runs *after* the steps above have already removed blocked targets. It was never meant to answer "is
  this blocked?" on its own.

So the solver only sees the type chart part of the rules. Everything else the engine checks before damage is
invisible to it.

## Fix (decided 2026-11-25)

**One shared rulebook.** Split each engine step into a part that *decides* ("is this blocked?", "who does this
really hit?") and a part that *acts* (log, heal, boost). The deciding part becomes a small function that changes
nothing. The engine calls it and then acts as before. The solver calls the same function, so there is only one copy
of the rules, and a new ability added to the engine reaches the solver automatically. The engine's behaviour and
battle logs don't change.

What the solver's guess will then get right:

- **Blocked moves:** Levitate, Air Balloon, Bulletproof, and the absorbing abilities (Volt Absorb, Water Absorb,
  Sap Sipper, Motor Drive, Lightning Rod, Storm Drain). Mold Breaker turning them off is included.
- **Stolen moves:** Lightning Rod and Storm Drain pull an Electric or Water move onto the holder, even when it was
  aimed at the partner.
- **Moves that do land:** Scrappy (Normal and Fighting hit Ghost) and Iron Ball (Ground hits a Flying holder). The
  guess currently scores these as 0.
- **Moves that change type:** Pixilate and the other "-ate" abilities, and Weather Ball. The guess will use the type
  the engine uses.
- **Psychic Terrain:** it stops priority moves aimed at grounded foes.
- **The "hits several targets" cut:** applied only when 2 or more Pokémon are actually hit, as the engine does.

Who uses it:

- The solver's estimate (the MCTS shortlist, the greedy opponent) and switch scoring.
- Position scoring, which gets the ability and item rules. It doesn't look at the board, so redirection and terrain
  stay out there.
- The live scout's damage calculator, so it shows "immune" instead of a damage range for blocked moves.

**Agreement test.** A test plays each blocking case through the real engine and checks that the solver's guess
agrees on which Pokémon are actually hit. A second test sweeps every ability and item the engine models, so a new
one is checked automatically, without anyone verifying it by hand.

## Done

- **Engine:** the deciding parts are now their own functions that change nothing: `immunity.blocked_by`,
  `absorb.absorbed_by` and `redirect.redirected_to`. `pipeline.blocked` and `pipeline.landing` combine them in the
  engine's step order. The engine steps call them and then act as before. The full test suite passed unchanged.
- **Solver estimate:** `prior.hit_targets` asks those functions who a move really hits, and `pressure` and switch
  scoring use it.
- **Position scoring:** `evaluate._hit_frac` uses them too. Its cache key now includes the attacker's item and the
  target's ability and item.
- **Live scout:** the calculator shows "immune" for blocked moves.
- **Tests:** `tests/test_estimate_parity.py` plays each rule through the engine and checks the estimate hits the same
  Pokémon. A sweep does the same for every modeled ability and item: about 5,000 single turns, 0 disagreements. The
  test fails if the fix is undone. `tests/test_engine_blocked.py` covers the new engine functions.
- **Result on the examples above:** Earthquake into Levitate Rotom, Thunderbolt past a Lightning Rod Raichu, Sludge
  Bomb into Bulletproof and Thunderbolt into Volt Absorb now all estimate 0. The no-ability Rotom control went from
  92 to 122 damage, because the 25% cut no longer applies when only Rotom can be hit.
- **Speed cost:** measured old vs new in the same process, alternating runs (`.tmp/ab_speed.py`). Building the
  shortlist takes about 320 µs per call, up from 249 µs (+28%). MCTS runs about 8% fewer iterations per second
  (474 vs 517 per second, 1,500 iterations on 3 positions). That's small next to the spike, where a 2.7× bigger
  table made no measurable difference in games.

## Follow-ups (not done)

- **Mold Breaker vs Lightning Rod / Storm Drain.** The engine still redirects (a TODO in `redirect.py`). The estimate
  copies whatever the engine does, so fixing the engine fixes both.
- **The engine's spread-cut rule vs Showdown.** The engine applies the 0.75× cut only when 2 or more Pokémon are
  actually hit. `data/mechanics.json` case `spread-with-protect` is still marked "verify". It wasn't checked here,
  because the sandbox couldn't reach GitHub.
- **The live scout** doesn't use the move's changed type (-ate abilities, Weather Ball) and doesn't handle
  redirection. It's a one-attacker, one-target calculator.
- **Duplicate targeting in `live/solve.py`.** It has its own `_targets` logic, which may have drifted from the
  engine's.
- **The two cleanups below.**

## Not part of this issue (related cleanups, to file separately)

- **Rename the estimate.** `pressure` reads like the Pressure ability. It means "expected fraction of the target's HP
  removed". It also returns `None` for non-damaging moves, and every caller handles that separately.
- **Make the greedy opponent smarter and more predictable.** It picks each Pokémon's move separately, so both can
  attack the same foe. It never switches, Protects or uses status moves. When nothing scores, it falls back to a
  random move. It also plays a random move 10% of the time, which is built in rather than a setting, so replays
  aren't repeatable.

## Where in the code

- Solver estimate: `src/champions/solver/prior.py` (`hit_targets`, `pressure`; also `_best_attack` for switch scoring)
- Position scoring: `src/champions/solver/evaluate.py` (`_hit_frac`)
- Greedy opponent: `src/champions/solver/rollout.py` (`_strongest`, `greedy_choices`), which uses `pressure`
- Live scout calc: `src/champions/live/scout.py` (`_hit`)
- Damage formula (type chart only, by design): `src/champions/calc/damage.py`
- The shared decisions: `src/champions/engine/pipeline/__init__.py` (`blocked`, `landing`),
  `src/champions/engine/pipeline/absorb.py`, `src/champions/engine/pipeline/immunity.py`,
  `src/champions/engine/redirect.py` (Lightning Rod / Storm Drain)
