# Plan: build the engine (Option A, issue #25) with a checklist and gates

## Context

Issue #25 settled the design: Option A (stage-grouped pipeline plus hook registry), deterministic replays, and catalogue-driven tests. This plan builds it end to end, skipping edge cases but leaving a working stub: a seeded doubles battle that plays turns, logs events, saves and replays, and runs catalogue cases for the first mechanics.

The plan is persisted in the repo as `docs/BUILD_PLAN.md` (step 1 of Phase 0) and the work is done by ticking its checkboxes. Each phase ends with a **gate**: commands that must pass before the next phase starts. After each gate passes, make one local commit on branch `engine-skeleton` (off `new_main`). No push, no PR.

## Findings that shape the plan

- **Tests use `unittest`, not pytest** (`tests/test_data.py`; pytest is not installed; `pyproject.toml` has `dependencies = []`). The runner uses `unittest` with `subTest`, so no new dependency. Run: `python3 -m unittest discover -s tests`. This replaces the pytest parametrize sketch in #25.
- **`moves.json` has no structured effects**, only `short_desc` (e.g. Close Combat: "Lowers the user's Defense and Sp. Def by 1."). It has `priority`, `target`, `flags`, `multihit`, `base_power`, `accuracy`. So the engine needs a hand-written effect table for the moves it supports. Anything not in the table raises `Unsupported` (ground rule from ENGINE_PLAN).
- **Reusable code:** `stats.level50(base, nature, sp)` for stats; `types.json["chart"]` is `chart[attacker][defender]` multipliers; `champions.json["pokemon"]` entries have `types`, `stats`, `abilities`; `cli.py` registers subcommands in a `COMMANDS` dict.
- **Catalogue cycles to fix** (`data/mechanics.json`): `move-pipeline` <-> `target-resolution`, `multi-hit` <-> `crit`. Fix: keep `move-pipeline -> target-resolution` and `multi-hit -> crit`; remove the reverse edges.
- Python 3.14 locally, `requires-python >=3.8`: keep syntax compatible (`typing.Optional`, no `X | Y` at runtime, `from __future__ import annotations`).

## Layout (Option A, as in #25)

```
src/champions/
  calc/        typechart.py damage.py
  engine/
    errors.py rng.py events.py state.py actions.py teams.py
    hooks.py game.py turn.py replay.py
    effects_table.py            # hand-written per-move/ability effect data
    pipeline/  __init__.py can_move.py targets.py protect.py immunity.py accuracy.py hit.py after.py
    handlers/  self_drop.py secondary.py flinch.py foe_drop.py entry.py recoil.py multi_hit.py crit.py
  catalogue/   load.py cases.py runner.py report.py
tests/
  test_catalogue_load.py test_engine_*.py test_calc.py test_catalogue_cases.py test_replay.py
docs/BUILD_PLAN.md              # this checklist, ticked as work proceeds
```

## Phases (each: tasks, then gate)

### Phase 0: Setup
- [x] Create branch `engine-skeleton` off `new_main`.
- [x] Copy this plan to `docs/BUILD_PLAN.md` as the live checklist.
- [x] Add `scripts/gate.sh` that runs the full test suite (`python3 -m unittest discover -s tests`) and exits non-zero on failure.

**Gate 0:** `scripts/gate.sh` passes on the untouched repo (baseline). Commit: "Add build plan and gate script".

### Phase 1: Catalogue hygiene and loader
- [ ] Fix the two `depends_on` cycles in `data/mechanics.json` (see Findings).
- [ ] Split free-text prerequisites out of `depends_on` into a new `needs` list on every mechanic; `depends_on` holds mechanic ids only.
- [ ] `catalogue/load.py`: `load_mechanics()`, `load_compositions()`, `check_catalogue()` (ids unique; `depends_on`, `uses`, `involves` exist; `involves` subset of `uses`; no cycles; every case has id, group, kind, status).
- [ ] `tests/test_catalogue_load.py` calls `check_catalogue()`, plus a test that a deliberately cyclic fixture is rejected.
- [ ] Update `_about` in both JSON files to mention `needs` and the optional `run` block.

**Gate 1:** `check_catalogue()` passes on the real files; cycle fixture test fails as intended; full suite green. Commit: "Catalogue: fix depends_on cycles, add loader and checks".

### Phase 2: Engine core (state, RNG, events, teams)
- [ ] `errors.py`: `Unsupported(ValueError)`.
- [ ] `rng.py`: seeded `Rng` (wraps `random.Random`, logs each draw as an `rng` event) and `ForcedRng(values)` for tests.
- [ ] `events.py`: frozen `Event(turn, kind, data)`; the fixed list of event kinds and hook names (single source of truth).
- [ ] `state.py`: dataclasses `Mon`, `Side`, `Battle` (as in #25); methods that mutate state also append events: `Mon.take(dmg)`, `Mon.boost(stat, n)`, `Mon.add_volatile(name)`, `Battle.log_event(...)`.
- [ ] `actions.py`: frozen `Move`, `Switch`, with `to_dict` / `from_dict`.
- [ ] `teams.py`: `build_mon(spec)` from `champions.json` + `stats.level50`; spec is `{"species", "ability", "item", "moves", "sp", "nature"}`; `build_teams(...)`.
- [ ] `tests/test_engine_state.py`: stats match `stats.level50` (reuse the Garchomp numbers from `tests/test_data.py`), `boost` clamps at -6/+6, `take` floors at 0 and logs faint.

**Gate 2:** state, boost-clamp and team-building tests pass; suite green. Commit: "Engine core: state, RNG, events, teams".

### Phase 3: Calc and pipeline skeleton
- [ ] `calc/typechart.py`: `effectiveness(move_type, defender_types)` from `types.json`; `is_immune`.
- [ ] `calc/damage.py`: Showdown-order damage (base + 2, spread, crit, roll, STAB, type, burn, minimum 1), flooring each step; `rolls` parameter so tests can pin it. Weather, screens and item/ability modifiers: stubbed to 1.0 with `# TODO(S1)`.
- [ ] `hooks.py`: registry with `on(event_name)` decorator and `fire(battle, name, ctx, ...)`; handlers run in Speed order; `HOOK_NAMES` from `events.py`; unknown name raises.
- [ ] `effects_table.py`: hand-written data for the supported moves/abilities (initial set: Fake Out, Close Combat, Flare Blitz, Dragon Claw, Protect, Intimidate, plus what Phase 5 mechanics need). Lookup of anything else raises `Unsupported`.
- [ ] `pipeline/`: `run_move(battle, act)` running stages in order; each stage removes targets from `ctx.targets` or aborts, and logs the abort (`fail`, `immune`, `protected`, `missed`): `can_move`, `targets` (singles + doubles, adjacency simplified), `protect`, `immunity`, `accuracy`, then `hit` loop and `after` (recoil, faint).
- [ ] `turn.py`: `order_actions` (switch, Mega flag split out, priority, Speed, seeded tie-break; Trick Room reverses Speed), `run_residuals` (weather and status ticks stubbed, flinch clears).
- [ ] `game.py`: `start`, `play_turn`, `legal_choices` (simple), `validate` (raises `Unsupported`), `run_to_end(teams, seed, policy)`, `check_winner`, `request_replacements` (auto-pick first living mon for now).
- [ ] Tests: type immunity (Fighting into Ghost = 0), damage known value for one fixed roll, `order_actions` (Fake Out before a faster mon), Fake Out turn from #25 produces the expected event list.

**Gate 3:** the Fake Out vs Garchomp turn test passes (Garchomp flinched, its move logged as `fail(flinch)`); an unsupported move raises `Unsupported` in `validate`; suite green. Commit: "Calc and move pipeline skeleton with a playable turn".

### Phase 4: Replay and saving
- [ ] `replay.py`: `save_replay(path, teams, seed, turns)`, `load_replay`, `replay(path) -> Battle`, `save_log(path, battle)`; replay JSON has `version`, `format`, `seed`, `teams`, `turns` (see #25).
- [ ] `snapshot(b)` / `restore(d)` as plain dicts including RNG state (stub: round-trip test only).
- [ ] A recorded sample replay in `tests/replays/fakeout_turn.json`.
- [ ] Tests: replay twice gives identical logs; snapshot/restore round trip equals the original; a replay with a `version` mismatch is rejected with a clear error.
- [ ] CLI: `champions sim replay <file>` prints the event log (register in `COMMANDS` in `cli.py`).

**Gate 4:** determinism and round-trip tests pass; `champions sim replay tests/replays/fakeout_turn.json` prints the log and exits 0; suite green. Commit: "Replay, save and snapshot".

### Phase 5: Initial mechanics (stubbed but working)
For each mechanic below: (a) add structured `run` blocks and `source` to a representative positive, control and interaction stub in `data/mechanics.json`; (b) write the handler; (c) the cases pass. Edge cases and `verify` stubs stay "stub only". Order follows dependencies:

- [ ] `type-immunity` (2 stubs): immunity stage; Scrappy override stubbed.
- [ ] `protect`: block, blocked-effects, no stacking chain beyond a 1/3 stub.
- [ ] `stat-stages` and `foe-stat-drop` and `entry-trigger` with `intimidate` (composition): drop on entry, blockers (Inner Focus, Oblivious, Own Tempo, Scrappy), Guard Dog flip, doubles both foes.
- [ ] `first-turn-only` and `flinch` and `move-priority` with `fake-out` (composition): the full turn from #25.
- [ ] `self-drop`: Close Combat drop; control: immune into Ghost gives no drop; control: Protect gives no drop.
- [ ] `secondary-effect`: chance roll via `ForcedRng`; Substitute stub skipped.
- [ ] `recoil-drain-heal`: recoil fraction after the hit loop; drain fraction; capped by remaining HP.
- [ ] `accuracy-evasion`: roll against accuracy; stage multipliers.
- [ ] `crit` and `multi-hit`: crit stage chance table, 1.5x; fixed and 2-5 hit counts with 35/35/15/15.
- [ ] `target-resolution`, `substitute`, `damage-calc`, `move-pipeline`: covered by the above or left "stub only", recorded in the status report (Phase 6).

**Gate 5:** every mechanic listed above has at least one runnable positive, one control and one interaction case, all passing; `pytest`-free `python3 -m unittest tests.test_catalogue_cases` green; suite green. Commit one per 2-3 mechanics, last one: "Initial mechanics: handlers and runnable cases".

### Phase 6: Catalogue runner and report
- [ ] `catalogue/cases.py`: `runnable_cases()` (stubs with `run`; skips `status: verify` unless `CHAMPIONS_INCLUDE_VERIFY=1`).
- [ ] `catalogue/runner.py`: `run_case(mech, case)` builds teams, plays `run.turns`, evaluates all `check` entries (`stage`, `hp`, `status`, `volatile`, `event`, `no_event`); returns every failing check, not just the first; a `ForcedRng` when `run.rolls` is present.
- [ ] Failure message format from #25: id, kind, status, setup, expect, source, failing checks with actual values, the turn's event log, and a note when an upstream `depends_on` mechanic has failing cases.
- [ ] `tests/test_catalogue_cases.py`: one `unittest` `subTest` per runnable case, named `mechanic::case`. Filter with `CHAMPIONS_CASE=self-drop` (substring match on the id).
- [ ] `catalogue/report.py` and CLI `champions catalogue status`: per mechanic, counts of stub-only / runnable / passing, split by kind; flags mechanics missing a positive, control or interaction case.
- [ ] A test that deliberately breaks one handler through a fixture and checks the failure message contains the stub's `expect` and the event log.

**Gate 6:** `champions catalogue status` prints the table with no errors; the broken-handler test shows the readable failure; suite green. Commit: "Catalogue runner and status report".

### Phase 7: Wrap up
- [ ] Update `docs/ENGINE_PLAN.md`: status section (what exists), point to `docs/BUILD_PLAN.md` and #25; note the unittest decision.
- [ ] Update `docs/DATA.md` or a new `docs/ENGINE.md`: layout, how to add a mechanic (steps from #25), how to run one case.
- [ ] Final checklist review: every box in `docs/BUILD_PLAN.md` ticked or marked "deferred" with a reason; list the deferred edge cases.
- [ ] Post a short comment on #25 with the outcome and the deferred list (do this only if the user wants it; otherwise report in the chat).

**Gate 7:** full suite green; `git status` clean; `git log --oneline` shows one commit per gate. Final commit: "Docs: engine status and how to add a mechanic".

## How execution works

1. Work top to bottom. Tick a box in `docs/BUILD_PLAN.md` only after its work is done.
2. At each gate, run `scripts/gate.sh` plus the gate's extra commands; if anything fails, fix it before moving on and note the failure in the plan file under the phase.
3. Commit locally after each gate with a clear message ending in the Co-Authored-By line from the session. No push, no PR, no `--no-verify`.
4. Skipped edge cases get a `# TODO(S?)` comment in code and a line under "Deferred" in `docs/BUILD_PLAN.md`; unmodeled mechanics raise `Unsupported`, never silently pass.
5. Single session throughout (per the discussion in #25's follow-up): no parallel agents.

## Out of scope (deferred on purpose)

Weather and terrain, screens, Tera, Mega Evolution details beyond the ordering flag, held-item effects other than a stub or two, abilities beyond Intimidate and its blockers, Substitute, semi-invulnerable moves, Taunt, Encore, Disable, full legal-move generation, a UI or search bot.

## Verification (end to end)

- `scripts/gate.sh` (the full `unittest` suite) passes.
- `python3 -m champions sim replay tests/replays/fakeout_turn.json` prints the Fake Out turn log: Garchomp flinched, `fail(flinch)`.
- `python3 -m champions catalogue status` shows per-mechanic coverage and no mechanic marked done without positive, control and interaction cases.
- `CHAMPIONS_CASE=self-drop python3 -m unittest tests.test_catalogue_cases -v` runs only the self-drop cases; the Close Combat into Ghost control case passes.
- Break `handlers/self_drop.py` on purpose (drop even when immune): the failure shows the stub's `expect`, the failing check and the event log; then revert.
