# DRAFT issue: the cheap damage estimate ignores ability immunities, and `_strongest` / `pressure` need a rethink

Status: local draft, not filed. Fix to be decided later.

> **NOTE TO SELF: this needs a clearer, plain-language explanation for a human reader before it is filed.**
> It is written as shorthand (function names, engine internals). Rewrite the summary so someone who has not read
> the solver code can see: what goes wrong, a concrete example, and why it matters.

## Summary

`solver/prior.pressure()` estimates how much damage a move does using `calc.damage`, which applies only the
type chart. The engine's real immunity check (`engine/pipeline/immunity.py`) also honours abilities and items
(Levitate, Bulletproof, Air Balloon, Iron Ball, Scrappy, ...). So the estimate calls a move strong
that the engine then resolves as "immune". Two things consume that estimate, and both are affected:

1. **MCTS / live solver root filter** (`prior.candidate_slot_choices`, used by `candidate_joint_actions`): keeps
   the top 2 damaging moves per slot by `pressure`. A blocked move can take a slot, and a useful move can be dropped.
2. **The "greedy" playout / opponent policy** (`rollout._strongest`, `rollout.greedy_choices`): plays the highest
   `pressure` move every turn.

## Repro

Seen in `scripts/replay_demo.py` (greedy opponent): Gyarados and Dragonite use Earthquake nearly every turn into
Rotom, and the replay shows "avoided (immune)" on every one of them.

```python
b = game.start([[rotom(levitate), venusaur], [gyarados, dragonite]], seed=1, format="doubles")
damage(gyarados, rotom, earthquake, roll=92, spread=True)   # 92, of 125 HP: Ground is super effective on Electric
pressure(b, gyarados, Move("earthquake", ...))               # ~1.0, the best-scoring move on the board
# engine.resolve: Rotom -> event "immune" (Levitate). Real damage: 0.
```

The Flying partner (Dragonite) is correctly treated as immune, because that comes from the type chart. Only the
ability / item immunities are missed.

## Why it matters

- Greedy as a baseline opponent is weaker and more predictable than intended, so "MCTS beats greedy" says less.
- The MCTS root filter and the playouts (`rollout.py`) share this estimate, so the bias is inside the search too.

## Other problems in the same area

**Naming.** `pressure` reads as the Pressure ability (PP drain), which exists in the data (`champions.json`).
It is really "expected fraction of target HP removed". Something like `expected_damage_fraction` /
`damage_score` would be clearer. It also returns `None` for non-damaging moves, a convention that callers
(`candidate_slot_choices`, `_strongest`) each re-handle.

**`rollout._strongest` / `greedy_choices`:**
- Picks each slot independently, so both slots can target the same foe and overkill while the other foe is untouched.
- Never switches, Protects, or uses status moves (Thunder Wave, Will-O-Wisp, Fake Out is only valued by damage).
- Falls back to `rnd.choice(moves or legal)` when nothing scores, which can pick any status move at random.
- 10% fully random exploration is hard-coded and applied per call; "greedy" is not deterministic, which makes
  replays harder to reason about.
- `evaluate._threat` / `_hit_frac` (static evaluation) is a third "how hard does this hit" estimate; worth checking whether it shares the same blind spot and could share one helper.

## Related: the root filter does not anticipate switches

`candidate_slot_choices` keeps the top N damaging (move, target) choices per slot, scored against the board as it
stands. It never asks who will be in that slot after a switch, so a move that is only good against the incoming
Pokemon is cut before the search sees it.

Seen in the replay (MCTS vs MCTS, turn 1): MCTS expected "Garchomp switches to Venusaur". The opponent's Gengar had
Ice Beam -> Garchomp and Sludge Bomb -> Incineroar in its table, but not Sludge Bomb -> Garchomp's slot (Poison does
half damage to Garchomp right now, so it ranks low). The engine does reward it: checked directly, a Sludge Bomb aimed
at the slot hits the incoming Venusaur for 66, because switches resolve first and attacks hit whoever is in the slot.

Also note: "expected" in the replay is the highest-share option of the mix, not a certain prediction.

Possible fix: keep an attack aimed at each slot where the other side's best switch lands (or one option per target
slot). This grows the table, so measure the speed cost.

## Possible fixes (not decided)

1. In `pressure`, ask the engine whether the target would be immune (reuse `immunity.check` logic or factor out a
   shared `is_blocked(user, move, target)`), instead of re-listing abilities in the solver.
2. Rename `pressure`, and give it one clear return contract (0.0 rather than `None` for non-damaging moves, or a
   separate predicate).
3. Rewrite greedy to choose a joint action (one scoring pass over both slots, spreading targets), and make
   exploration a parameter.
4. Add a test: for each ability immunity the engine models, `pressure` agrees with `resolve` on "does this move hit".

## Files

- `src/champions/solver/prior.py` (`pressure`, `candidate_slot_choices`)
- `src/champions/solver/rollout.py` (`_strongest`, `greedy_choices`)
- `src/champions/calc/damage.py` (type chart only), `src/champions/engine/pipeline/immunity.py` (the real check)
