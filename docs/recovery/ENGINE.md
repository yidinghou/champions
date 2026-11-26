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
  calc/        typechart.py damage.py field.py items.py   pure functions, never import engine/ (field.py: grounded, weather and terrain
               modifiers; items.py: type boosts, Life Orb, Expert Belt, resist berries, Light Ball;
               abilities.py: Huge Power, Tough Claws, -ate, Thick Fat, Multiscale and the other damage abilities)
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
    handlers/substitute.py + pipeline/substitute.py   Substitute and Shed Tail (the decoy is mon.volatiles["substitute"] = {hp})
    pivot.py       pivot moves (U-turn, Baton Pass...) and forced switches (Dragon Tail, Roar...)
    mega.py        Mega Evolution: stone -> form, once-per-side rule, the form change
    items.py       held items: which are modeled, consume(), Update checks, Focus Sash/Band
    redirect.py    Follow Me, Rage Powder, Lightning Rod, Storm Drain redirection; type-absorbing abilities
    (handlers/protect.py, pipeline/protect.py: Protect family, Wide Guard, Quick Guard; screens.py also holds Safeguard)
    screens.py     side conditions: Reflect, Light Screen, Aurora Veil, Tailwind (state in side.conditions)
    arena.py       weather and terrain: state in battle.arena, setting, residuals, speed, blocks
    status.py      major status: apply, immunities, sleep/freeze before a move, residual damage
    handlers/      items (berries, herbs, seeds, Leftovers, Rocky Helmet, Life Orb, Eject Button, Red Card...), self_drop, secondary, recoil/drain, protect, entry (Intimidate), foe_drop, status, volatile
    replay.py      save/load/play replays; snapshot/restore
    viewer/        replay -> one HTML page; engine state captured after every event (build.py, viewer.html)
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
python3 -m champions sim view <file> [-o out.html]  step through a replay in the browser, one action at a time (self-contained page)
python3 -m champions live --team FILE            serve the live-game tracker page (docs/live-ui.md)
python3 -m champions explore --case charge-moves  open a seeded case from cases/ in the explorer; prints what to look for
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
`no_event`, `order`, `recoil`/`heal` (fraction of damage dealt), `holds` (the held item, null = none or used), `pp_eq`, `arena` (+`eq`: `weather`, `weather_turns`, `terrain`, `terrain_turns`, `trick_room`; null = absent). A case may preset `"arena"` after the leads enter, so ability setters need their own case. A case with no checks fails. Team specs
may carry `"hp"` to start a mon damaged. A failure prints the stub's setup and expect, each failing
check with its actual value, the event log, and which upstream mechanics also fail.

## Adding a mechanic

1. In `data/mechanics.json`, resolve the stub's `verify` items against Showdown source and note the source.
2. Add `run` blocks: at least one positive, one control (the effect must be absent) and one interaction.
3. Run the cases: they fail. Add the move to `effects_table.py` if it is new.
4. Write the handler in `engine/handlers/` with `@on("<hook>", "effect:<key>")`; import it in
   `handlers/__init__.py`. Stages that stop a target must log `fail`, `immune`, `protected` or `missed`.
5. Add unit tests in `tests/test_engine_pipeline.py` for pure helpers.
6. Seed an explorer case in `cases/<mechanic>.json` to check it by eye. It holds `title`, `look_for` (numbered steps
   with the exact lines and numbers to expect), `teams` (doubles), and optionally `seed` and `turns` (played before
   the page opens). Keep Player 1's options at 6 or fewer, so every one gets a clickable grid row: MCTS's root has
   no status moves, and only the top 6 options get cells. Give the opponents Protect and a move that barely hurts.
   Set the weather with a lead's ability, so editing a set at State 0 brings it back.
   `tests/test_explore.py::SeededCases` checks that every case opens.
7. `scripts/gate.sh` and `champions catalogue status` must be clean.

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

Held items (91 of 103 stubs run): see `engine/items.py` and `handlers/items.py`. A team spec's `item` is checked
at `start()`: modeled items run, Mega Stones are carried inert, and Leek, Metronome, Normal Gem and
anything unknown raise `Unsupported`. After every action and at the end of the turn each active mon gets an Update
(berries, herbs, seeds), in Speed order. Modeled: Sitrus, Oran, the five status berries, Lum, Persim, Leppa, the
17 resist berries and Chilan, White and Mental Herb, the four terrain seeds, Leftovers, Life Orb, Shell Bell, Rocky
Helmet, Focus Sash and Band, King's Rock, Air Balloon, Iron Ball (grounding, Speed), Eject Button, Red Card, Binding
Band, Shed Shell, Big Root, Choice Scarf (Speed and the move lock), Scope Lens, Wide and Zoom Lens, Bright Powder,
Light Ball, Expert Belt, Muscle Band, Wise Glasses, the 18 type items, the weather rocks and Terrain Extender. Unnerve
now stops foes eating berries, and Levitate and Air Balloon now make a mon immune to Ground moves. A mon switched out
mid-turn (Eject Button, Red Card) loses its queued action. Damage numbers are checked in `tests/test_items.py`.
The Eject Button holder's replacement is the first living bench mon (TODO: let the policy choose).

Screens and Tailwind (30 of 40 stubs run; 20 + 10): see `engine/screens.py`. Reflect, Light Screen, Aurora Veil (snow only)
and Tailwind live in `side.conditions` as turns left; 5 turns (8 with Light Clay) for screens, 4 for Tailwind, the
turn they are used counts. A screen takes damage x0.5 in singles and x2732/4096 in doubles, not on a crit, never
stacking, chained with Life Orb and berries. Brick Break and Psychic Fangs remove the target side's screens before the
hit (not if the target is immune or Protected). Speed is now re-read after every action (gen 8+), so Tailwind, Trick
Room or paralysis set mid-turn reorders the actions still to come. `side` checks: `condition`; `sides` presets
conditions. Damage numbers are in `tests/test_screens.py`.

Redirection and absorbing abilities (30 of 31 stubs; one is `verify`): see `engine/redirect.py`. In doubles a
single-target move ("normal"/"any") is redirected while targets are chosen: Follow Me and Rage Powder (a volatile for
the turn, the latest user wins, Rage Powder skips Grass and Overcoat), then Lightning Rod (Electric) and Storm Drain
(Water) on any other mon, the fastest first. Spread moves and singles are never redirected. A new `absorb` stage
(after Protect) lets Volt Absorb, Water Absorb, Lightning Rod, Storm Drain, Sap Sipper and Motor Drive eat their type
and heal 1/4 or boost. The log has a `redirect` event. Numbers in `tests/test_redirect.py`.

Mega Evolution (19 stubs, all run): see `engine/mega.py`. A Move choice with `mega=True` is legal for a mon holding
the Mega Stone for its species, once per side per battle (`ValueError` otherwise). The `mega` action runs before any
move, in Speed order; the mon takes the form's types, ability and stats (HP kept, the rest recomputed with its own
nature and Stat Points, so `Mon` now stores `nature` and `sp`), the new ability starts at once, and Speed is re-read.
`state_key` and snapshots include the changed fields. All 82 Mega forms are playable (a test asserts it); a team
whose stone leads to an unmodeled ability is still rejected at `start()`. Abilities added with Mega Evolution: Huge
Power, Pure Power, Tough Claws, Adaptability, Mega Launcher, Strong Jaw, Iron Fist, Sharpness, Technician, Pixilate,
Aerilate, Refrigerate, Dragonize, Thick Fat (was inert), Multiscale, Filter, Shell Armor, No Guard, Skill Link, Speed
Boost, Unseen Fist, Piercing Drill, Infiltrator, Stalwart, Bulletproof, Eelevate, Regenerator, Contrary, Defiant,
Competitive, Solar Power. Numbers in `tests/test_mega.py`.

Mega-form abilities (66 stubs, 58 run; the rest are numbers in `tests/test_abilities.py`): Prankster (+1 priority on
status moves, re-read after a Mega Evolution; Dark foes immune), Shadow Tag (`is_trapped` now takes the battle),
Magic Bounce (a `bounce` stage after Protect; the reflected move runs as `run_bounced`, once), Trace (copies a random
foe's ability and starts it, also when a Mega form gets it), Mold Breaker (`calc.abilities.breaks`: ignores Levitate,
the absorbing abilities, Clear Body and friends, Shell Armor, Thick Fat, Multiscale, Filter, Magic Bounce, Sand Veil),
Sheer Force (secondary effects dropped, x1.3, no Life Orb recoil), Parental Bond (second hit at 1/4 power; not for
status, spread, multi-hit, charge or `noparentalbond` moves), Healer, Thermal Exchange, Spicy Spray, Berserk, Innards
Out, Protean (first move after entering; undone on switch-out), Aura Guard, Fire Mane, Fairy Aura, Mega Sol.

Pivot moves and forced switches (36 stubs, all run): see `engine/pivot.py`. After U-turn, Volt Switch, Flip Turn, Parting
Shot, Chilly Reception or Baton Pass has done its work (it hit, the user is alive, a bench exists) the user switches out.
The player names the replacement in the choice (`Move.pivot_to`, a team index; `legal_choices` lists each option),
otherwise the first living bench mon comes in. Parting Shot switches only if a stat actually dropped, Chilly Reception
only if snow started, Baton Pass hands over stages, confusion and Leech Seed before the entry effects. Dragon Tail,
Circle Throw, Roar and Whirlwind swap the surviving target for a random bench mon (rng label `forceswitch`) before any
Eject Button reacts. A mon pulled out mid-turn loses its queued action. The `switch` event now carries `cause`.

Substitute and Shed Tail (39 stubs, all run): the decoy is the volatile `substitute` = `{hp}`. Using it costs max HP // 4
(fails at or below that, or if one is up). A damaging hit goes to the decoy (damage worked out as usual, capped at its
HP, no overflow, later hits of a multi-hit move reach the mon) and then nothing else reaches the target: no secondary,
flinch, stat drop, Rocky Helmet or Eject Button. `ctx.dealt_total()` counts decoy damage, so recoil, drain, Shell Bell
and Life Orb still work, and the user's self-drop and pivot still happen. Status moves fail with reason `substitute`
(a stage after accuracy) unless the move has the `bypasssub` flag or the user has Infiltrator. Intimidate skips the
holder. Baton Pass keeps the decoy (copied); Shed Tail costs half max HP rounded up and gives the replacement half of that.
New `substitute` event. Numbers in `tests/test_substitute.py`.

Guard moves (46 stubs, 45 run): `handlers/protect.py` and `pipeline/protect.py`. Protect, Detect, King's Shield (damaging
moves only; contact -1 Atk), Spiky Shield (contact: 1/8 max HP), Baneful Bunker (contact: poison), Endure (left on 1
HP) and Wide and Quick Guard (side conditions that last the turn) share the 1/3 stalling chain, and any of them fails
if nothing is left to act after it (`arena["pending"]`, set per action in `play_turn`, counts the actions still to
come; a Mega is not one). Wide Guard stops spread moves aimed at its side, Quick Guard moves with natural positive
priority (so not a Prankster-boosted one). Safeguard is a 5-turn side condition in `screens.py`: it stops status and
confusion another mon inflicts (not Rest, not a Yawn already applied, not Infiltrator). The Protect volatile's value is
the shield kind; `protected` events carry `by`. Numbers in `tests/test_guards.py`.

Charge moves (13 stubs, all run; decision 031): Electro Shot, Meteor Beam, Solar Beam, Solar Blade and Sky Attack.
`pipeline.charge` runs on the first turn after the PP is spent and before any target stage, so Protect and accuracy
can't stop it. It logs a new `prepare` event, applies the `charge.boost` (+1 Sp. Atk for Electro Shot and Meteor
Beam), and then either hits at once (the `charge.skip` weather, read through `weather_for`, so Mega Sol counts as sun)
or stores `volatiles["charging"] = {move, target}`. On the second turn `volatiles.locked_move` makes the release
the slot's only legal choice: no switch, no Mega Evolution. `validate` refuses anything else, and the release
spends no PP. A failed `can_move` or leaving the field drops the charge. Solar Beam and Solar Blade hit at half
power in rain, sand or snow (`calc/field.field_bp_mod`). Tests are in `tests/test_charge.py`, including a random
self-play fuzz of the invariants.

## Deferred

volatile-status leftovers (Torment, U-turn pivot, the 14 `verify` stubs), major-status leftovers (the 8 `verify` stubs: full paralysis, freeze applies/thaw, sleep wake,
counters on switch, Corrosion, Substitute interaction), Cloud Nine and Air Lock, Hydration, Dry Skin, Forecast, the semi-invulnerable charge moves (Dig, Fly, Dive, Bounce, Phantom Force), the terrain moves (Terrain Pulse,
Rising Voltage, Expanding Force, Grassy Glide, Steel Roller), Teleport, Spotlight, Stalwart, Flash Fire, Dry Skin, Earth Eater, Mist, Silk Trap, Burning Bulwark, Obstruct, hazards, the items in the catalogue's open lists (Metronome, Normal Gem, Leek), Tera (out of scope), Defiant/Competitive/Contrary/Mirror Armor, Triple Axel per-hit
accuracy, real residual effects, `verify` stubs that need a
source check. Each `TODO(...)` comment in `src/` names the mechanic it belongs to.
