# Battle engine

A deterministic doubles/singles battle engine and calculator, built from the mechanic catalogue in
`data/mechanics.json`. Design and tradeoffs: issue #25. Build checklist and gates: `docs/BUILD_PLAN.md`.
Status: initial stubs; the mechanics listed under "Modeled" work, everything else raises `Unsupported`.

## Idea

A game is a function of (teams, seed, choices). Same inputs, same event log. Everything else is derived.
All randomness goes through `engine/rng.py`; ordering never depends on dict or set iteration.

## Layout

```
src/champions/
  calc/        typechart.py damage.py            pure functions, never import engine/
  engine/
    state.py       Mon, Side, Battle; mutators log events
    actions.py     Move, Switch (frozen, serialisable)
    rng.py         Rng, ForcedRng, LabeledRng (tests force outcomes by label)
    events.py      Event; EVENT_KINDS and HOOK_NAMES (single source of truth)
    teams.py       build teams from specs + data/champions.json + stats.level50
    effects_table.py  hand-written effects per move/ability (moves.json only has prose)
    hooks.py       registry: @on(hook, "effect:<key>" | "ability:<id>")
    stages.py      change_stat(): stat changes go through on_try_boost
    turn.py        order_actions (kind, priority, Speed, seeded ties), residuals
    game.py        start, play_turn, validate, run_to_end
    pipeline/      one move as fixed stages; each logs why it stopped a target
    status.py      major status: apply, immunities, sleep/freeze before a move, residual damage
    handlers/      self_drop, secondary, recoil/drain, protect, entry (Intimidate), foe_drop, status
    replay.py      save/load/play replays; snapshot/restore
  catalogue/   load.py (checks) cases.py runner.py report.py cli.py
```

The pipeline order is `can_move -> targets -> protect -> immunity -> accuracy -> per hit: crit, damage,
on_hit -> on_after_all_hits`. A target removed by a stage gets no later stage, so an immune, protected or
missed target takes no damage, effects or self-drop.

## Commands

```
scripts/gate.sh                                   full test suite (python3 -m unittest)
python3 -m champions catalogue status [--verify]  coverage per mechanic; exit 1 if a case fails
python3 -m champions sim replay <file>            play a replay and print the event log
CHAMPIONS_CASE=self-drop python3 -m unittest tests.test_catalogue_cases -v     one mechanic
CHAMPIONS_CASE=self-drop::immune-no-drop python3 -m unittest tests.test_catalogue_cases    one case
CHAMPIONS_INCLUDE_VERIFY=1 ...                    also run `status: verify` stubs
```

## Catalogue cases

A stub becomes runnable when it has a `run` block:

```json
"run": {"format": "singles",
        "teams": [[{"species": "incineroar", "ability": "intimidate", "moves": []}],
                  [{"species": "garchomp", "ability": "sandveil", "moves": []}]],
        "turns": [[{"side": 0, "slot": 0, "move": "fakeout", "target": [1, 0]}]],
        "rolls": {"accuracy": [false], "crit": [true]},      // forced outcomes, by label prefix
        "stages": {"p2:garchomp": {"eva": 6}}, "arena": {"trick_room": 4},
        "check": [{"mon": "p2:garchomp", "stage": "atk", "eq": -1}]}
```

Checks: `stage`, `hp` (full/damaged/fainted), `hp_eq`, `volatile`, `event` (+`where`, `count`/`min`),
`no_event`, `order`, `recoil`/`heal` (fraction of damage dealt). A case with no checks fails. Team specs
may carry `"hp"` to start a mon damaged. A failure prints the stub's setup and expect, each failing
check with its actual value, the event log, and which upstream mechanics also fail.

## Adding a mechanic

1. In `data/mechanics.json`, resolve the stub's `verify` items against Showdown source and note the source.
2. Add `run` blocks: at least one positive, one control (the effect must be absent) and one interaction.
3. Run the cases: they fail. Add the move to `effects_table.py` if it is new.
4. Write the handler in `engine/handlers/` with `@on("<hook>", "effect:<key>")`; import it in
   `handlers/__init__.py`. Stages that stop a target must log `fail`, `immune`, `protected` or `missed`.
5. Add unit tests in `tests/test_engine_pipeline.py` for pure helpers.
6. `scripts/gate.sh` and `champions catalogue status` must be clean.

## Modeled (initial)

Type immunity (Scrappy override), Protect (1/3 chain), stat stages with blockers (Clear Body, White Smoke,
Hyper Cutter, Guard Dog), Intimidate and its blockers, first-turn-only, flinch, priority and Trick Room
ordering, self-drops, 100%/chance secondaries (flinch and stat drops), recoil and drain, accuracy and
evasion stages, crits and crit stages, multi-hit counts, spread damage and target resolution.

Major status (23 of 38 stubs): burn, poison, Toxic, paralysis speed, sleep and freeze applied by status moves
and secondaries, type immunities, one status at a time, persistence through switching, end-of-turn damage,
burn halving physical damage, and sleep/freeze stopping the move. The numbers in `engine/status.py`
(sleep 1-3 turns, 20% thaw) are Showdown's, not yet checked against Champions.

## Deferred

Substitute, volatile status, major-status leftovers (full paralysis, Rest, Heal Bell, Yawn, Guts, Magic Guard,
Corrosion, Substitute interaction and the `verify` stubs), weather and terrain, screens, items, Mega Evolution (rejected with
`Unsupported`), Tera (out of scope), Defiant/Competitive/Contrary/Mirror Armor, Triple Axel per-hit
accuracy, redirection (Follow Me, Lightning Rod), real residual effects, `verify` stubs that need a
source check. Each `TODO(...)` comment in `src/` names the mechanic it belongs to.
