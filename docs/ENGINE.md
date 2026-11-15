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
  calc/        typechart.py damage.py field.py   pure functions, never import engine/ (field.py: grounded, weather and terrain modifiers)
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
    volatiles.py   confusion, Taunt, Encore, Disable, Leech Seed, trapping
    arena.py       weather and terrain: state in battle.arena, setting, residuals, speed, blocks
    status.py      major status: apply, immunities, sleep/freeze before a move, residual damage
    handlers/      self_drop, secondary, recoil/drain, protect, entry (Intimidate), foe_drop, status, volatile
    replay.py      save/load/play replays; snapshot/restore
  catalogue/   load.py (checks) cases.py runner.py report.py cli.py
```

The pipeline order is `can_move -> targets -> protect -> terrain -> immunity -> accuracy -> per hit: crit, damage,
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
`no_event`, `order`, `recoil`/`heal` (fraction of damage dealt), `arena` (+`eq`: `weather`, `weather_turns`, `terrain`, `terrain_turns`, `trick_room`; null = absent). A case may preset `"arena"` after the leads enter, so ability setters need their own case. A case with no checks fails. Team specs
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

Major status (30 of 38 stubs): burn, poison, Toxic, paralysis speed, sleep and freeze applied by status moves
and secondaries, Rest, Heal Bell, Yawn, Guts (Attack x1.5, ignores the burn halving), Magic Guard, type immunities, one status at a time, persistence through switching, end-of-turn damage,
burn halving physical damage, and sleep/freeze stopping the move. The numbers in `engine/status.py`
(sleep 1-3 turns, 20% thaw) are Showdown's, not yet checked against Champions.

Volatile status (20 of 34 stubs): confusion (2-5 turns, 1/3 self-hit, 40-power typeless), Taunt, Encore,
Disable, Leech Seed (Grass immune), Fire Spin and Mean Look trapping (Ghost immune), cleared on switch or
faint, several at once, and a repeat application changes nothing. Timers and chances live in
`engine/volatiles.py`, again Showdown's values pending a Champions check.

Weather and terrain (114 of 131 stubs): see `engine/arena.py`. Sun, rain, sand, snow and Electric, Grassy, Misty,
Psychic Terrain, set by moves and entry abilities (slower setter wins), 5 turns or 8 with the matching rock or Terrain
Extender, one of each at a time. The weather ends before its residual effect on its last turn; the terrain ends after
everything, so Grassy Terrain still heals on its last turn. Effects: Sun/Rain damage, Sand Sp. Def and Snow Def for
Rock/Ice, sand chip and its immunities, Rain Dish, Ice Body, the four speed abilities and Surge Surfer, Sand Force,
Sand Veil and Snow Cloak, no freezing in sun, Thunder/Hurricane/Blizzard accuracy, Weather Ball, Moonlight-style healing,
terrain base-power boosts, Grassy healing, Electric (no sleep, Rest, Yawn), Misty (no status, no confusion), Psychic
(priority moves blocked). Damage and accuracy numbers are checked in `tests/test_weather.py`, not as replay cases.
The numbers (5 turns, x1.3 terrain, 1/16) are Showdown's gen 9, not yet checked against Champions.

## Deferred

Substitute, volatile-status leftovers (Torment, U-turn pivot, the 14 `verify` stubs), major-status leftovers (the 8 `verify` stubs: full paralysis, freeze applies/thaw, sleep wake,
counters on switch, Corrosion, Substitute interaction), Cloud Nine and Air Lock, Hydration, Dry Skin, Solar Power, Forecast, Solar Beam and the other terrain moves (Terrain Pulse,
Rising Voltage, Expanding Force, Grassy Glide, Steel Roller), terrain seeds, screens, items, Mega Evolution (rejected with
`Unsupported`), Tera (out of scope), Defiant/Competitive/Contrary/Mirror Armor, Triple Axel per-hit
accuracy, redirection (Follow Me, Lightning Rod), real residual effects, `verify` stubs that need a
source check. Each `TODO(...)` comment in `src/` names the mechanic it belongs to.
