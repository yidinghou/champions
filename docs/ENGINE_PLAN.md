# Battle engine and calculator: staged plan

Status: initial engine built (branch `engine-skeleton`): a seeded battle loop, calc, replay, and runnable catalogue cases for the first mechanics. See `docs/ENGINE.md` for the layout and `docs/BUILD_PLAN.md` for what was built and what is deferred. Design discussion: #25. This file remains the spec; tests use `unittest` (the repo has no pytest).

## How this was derived

The old project's docs (zip: `ENGINE.md`, `DESIGN.md`, `state-changes.md`, `BATTLE_CASES.md`) gave a coarse 6-stage outline. This plan re-derives the mechanic list from:

- the repo's data: 510 moves, 216 abilities, 165 items in `src/champions/data/`;
- Showdown's simulator source (`sim/battle-actions.ts`, `sim/battle.ts`), read via raw GitHub;
- Champions format rules from secondary sources (champdex, keengamer, champsdex).

Not read: Bulbapedia (403) and battlewiseai.com (429). Showdown's `battle.ts` was truncated before `runAction`'s `residual` case, so the residual order below comes from `fieldEvent`. Champions-specific rules are marked "to verify" and are in the open questions.

## Ground rules (carried over from the old project)

- An unmodeled mechanic is rejected with `ValueError`, never silently simulated wrong. `is_supported` is the gate.
- Test first: write a sourced case, watch it fail, then implement. Every case names its `source`.
- Each mechanic gets a positive case, a control where the effect must be absent, and at least one interaction case.
- The calc may accept an ability or item it does not model and give it no effect. The engine may not.

## Key findings

1. **Self-drops happen only if the move hit.** Showdown removes an immune, missed or Protect-blocked target before self-drops run. Close Combat into a Ghost deals 0 and leaves the user's Defense and Sp. Def unchanged.
2. **A move runs a fixed pipeline.**
   - `TryMove` → target resolution and redirect → Protect-style `TryHit` → type immunity → powder and Prankster-vs-Dark immunity → accuracy → hit loop.
   - Per hit: damage → move effects (boosts, status, heal) → self-drops → secondaries → forced switch → on-hit triggers.
   - After the loop: faint resolution, then recoil (based on total damage across hits).
   - Most edge-case tests check which stage aborted.
3. **Damage modifier order:** base damage + 2 → spread ×0.75 → weather → crit ×1.5 → random roll → STAB → type effectiveness → burn ×0.5 → other modifiers → minimum 1. Each step floors.
4. **Turn order:** actions sort by kind (switch, Mega Evolution, move), then priority, then Speed, with random ties. Priority and Speed are re-read each action. Residuals run in a fixed order: field (weather, terrain, Trick Room), side (Tailwind, screens), then per-Pokémon (status, items, abilities), each Speed-sorted.
5. **Switch-in triggers** are Speed-sorted and fire at battle start, on switch and on KO replacement: Intimidate, weather and terrain setters, Hospitality, Trace, Imposter, Frisk, Anticipation, Forewarn, Seeds.
6. **Mega Evolution is a turn action** that resolves before moves, so Speed and ability are re-read afterward.
7. **The old outline missed:** accuracy and evasion stages, crits, PP and Pressure, Substitute, confusion/sleep/freeze timers, Taunt, Encore, Disable, trapping, semi-invulnerable moves, redirection, Wide Guard and Quick Guard, future moves, recharge, forced switches, pivots, bring-4 team rules, win and draw logic.

## What the data says to model

| Data | Finding |
|---|---|
| Priority | −7 to +5 (+1 ×12, +2 ×6, +3 ×4, +4 ×6) |
| Targets | 14 kinds: normal, self, allAdjacentFoes, all, any, allAdjacent, allySide, randomNormal, adjacentAlly, scripted, foeSide, adjacentAllyOrSelf, allies, allyTeam |
| Multi-hit | `[2,5]` ×8, fixed 2 ×4, fixed 3 ×1, fixed 10 ×1 |
| Flags | recharge 7, charge 10, powder 6, sound 24, bullet 18, punch 15, slicing 18, wind 9, defrost 6, gravity 5, futuremove 1, bypasssub 51 |
| Champions overrides | 31 moves with changed power, PP or accuracy; the calc must use these, not mainline values |
| Abilities | 216; 16 trigger on entry (Anticipation, Curious Medicine, Drizzle, Drought, Electric Surge, Forewarn, Frisk, Grassy Surge, Hospitality, Imposter, Intimidate, Psychic Surge, Sand Stream, Snow Warning, Supersweet Syrup, Trace) |
| Items | 165; most are Mega Stones, berries and type boosters. Active ones: Focus Sash/Band, Sitrus/Oran/Leppa, Rocky Helmet, Shell Bell, Eject Button, Red Card, Air Balloon, Mental Herb, White Herb, Seeds, Terrain Extender, Light Clay, Big Root, King's Rock, Scope Lens, Wide/Zoom Lens, Binding Band, Shed Shell |

## Mechanic catalogue

Each row is owned by one stage (S0 fills in the Showdown source and the test names).

| Area | Mechanics | Stage |
|---|---|---|
| Stats | Level-50 stats, Stat Points (66 total, 32 per stat), natures | S1 |
| Damage | Formula, modifier order, 16 rolls, STAB, Adaptability, type chart, immunities, crit, burn, spread, weather, terrain, screens, Helping Hand, item and ability modifiers, multi-hit and variable-power moves, Champions overrides | S1 |
| State | HP, stat stages (incl. accuracy and evasion), major status, volatiles, PP, item, ability, side and field state | S2 |
| Move pipeline | Target resolution, Protect, immunity, accuracy, hit loop, effects, self-drops, secondaries, recoil, faint, replacement | S2 |
| Turn order | Priority, Speed, Trick Room, Tailwind, Mega Evolution, switching, residual order | S3 |
| Effect classes | Self-drop, self-boost, foe-drop, status, secondary, flinch, heal, drain, recoil, fixed damage, multi-hit, charge, recharge, Protect family, redirect, pivot, forced switch, weather/terrain/screen setters, hazards | S4 |
| Triggers | Entry abilities and their blockers/reactors, contact abilities, on-damage and end-of-turn items, berries, Eject Button, Red Card | S5 |
| Volatiles | Substitute, semi-invulnerable moves, Taunt, Encore, Disable, confusion, sleep and freeze counters, Pressure, trapping | S6 |
| Format | Bring 4 of 6 (doubles) or 3 (singles), open team sheets, win and draw logic | S2 |

## Stages

Ordered by dependency, one stage per session. Do not start a stage until the previous one's tests pass.

| Stage | Scope | Done when |
|---|---|---|
| **S0 Spec and oracle** | Fill the catalogue: mechanic → pipeline stage → Showdown source → test names. Fetch Showdown `data/moves.ts`, `abilities.ts`, `items.ts`, `conditions.ts`. Settle the open questions. | Every mechanic has an owner stage and a named source |
| **S1 Calc** | Damage formula in full modifier order, type chart and immunities, stat-stage maths with crit rules, spread, weather, terrain, screens, Champions overrides, rolls. | Damage cases pass, including Fighting into Ghost = 0 |
| **S2 State and move pipeline** | `Battle` with per-mon, side and field state; the ordered hit pipeline; KO, faint and replacement; the case runner; the `ValueError` gate. | A move that hits, misses, is blocked or is immune each give the expected state |
| **S3 Turn order and residuals** | Priority, Speed, Trick Room, Tailwind, Mega Evolution as an action, switching, residual order. | Order cases pass, including Speed re-read after Tailwind or Trick Room |
| **S4 Effects by class** | One handler per class, tested with a representative move and a control. | Close Combat vs Ghost: 0 damage and no self-drop |
| **S5 Triggers** | Entry abilities, contact abilities, on-damage items, end-of-turn items, berries, Eject Button, Red Card. | Intimidate drops Attack on both foes, and its edge cases pass |
| **S6 Volatiles and edge interactions** | Substitute, semi-invulnerable moves, Taunt, Encore, Disable, counters, Pressure, trapping. | Every `moves.json` entry is classified supported or rejected |

## Your two example cases, placed

- **Close Combat doesn't hit Ghosts**
  - S1: Fighting into Ghost gives 0 damage.
  - S2: the pipeline aborts at the immunity stage, before any effect.
  - S4: the self-drop class does not fire when the move was immune.
  - Interaction cases: Scrappy or Mind's Eye type overrides if present, and Protect or a miss giving the same no-drop result.
- **Intimidate drops Attack**
  - S5, but it needs stat stages as state (S2), entry ordering with weather setters and Mega Evolution (S3), and blocker and reactor abilities.
  - In doubles it hits both foes. Check Protect, switch-out resetting the stage, and that it triggers at battle start and on replacement.

## Decisions (settled)

- **Tera:** out of scope (as in the old project). `ValueError` if a case asks for it.
- **Scope:** calc and battle engine only. No solver, no UI. S7 is dropped.
- **Mega Evolution:** the Mega form persists after switching out. Once per side per battle. The Mega's ability is locked in.

## Mechanic catalogue (S0 in progress)

The catalogue lives in `data/mechanics.json` and is built one mechanic at a time. Entries use readable slug IDs (`intimidate`) and a `depends_on` list instead of a stage number. Each mechanic has many case stubs (id, group, kind, status, setup, expect). First slice done: Intimidate, 35 stubs. Decisions and open items are tracked in #24.

## Intimidate and stat-drop abilities in this game's data

Checked against `abilities.json` (216 abilities). "Absent" means the ability is not in this game's data, so no case or handler is needed.

| Ability | Present | Effect on an Intimidate (or any foe stat drop) | Case to write |
|---|---|---|---|
| Intimidate | yes | Lowers each adjacent foe's Attack by 1 on entry | the base case |
| Clear Body, White Smoke | yes | Blocks stat drops from foes | Attack stays put |
| Hyper Cutter | yes | Blocks Attack drops only | Attack stays put; other drops go through |
| Inner Focus, Oblivious, Own Tempo, Scrappy | yes | In mainline gen 8+ these four block Intimidate, in addition to their own effects; check Showdown source | blocked, control: other ability is not |
| Guard Dog | yes | Intimidate boosts its Attack by 1 instead; also blocks forced switches | +1 instead of −1 |
| Mirror Armor | yes | Reflects the drop back onto the Intimidate user | user's Attack −1 |
| Contrary | yes | Inverts the change: Attack +1 | +1 |
| Defiant | yes | Attack +2 after any foe-caused drop (net +1 after Intimidate) | net +1 |
| Competitive | yes | Sp. Atk +2 after any foe-caused drop | Attack −1, Sp. Atk +2 |
| Flower Veil | yes | Protects Grass-type allies from foe-caused drops | Grass ally unaffected |
| Supersweet Syrup | yes | Entry trigger, lowers adjacent foes' evasion by 1, once per battle | separate entry case |
| Unaware, Opportunist, Moody, Weak Armor | yes | Not Intimidate blockers; Unaware ignores stages in damage and accuracy, so it is a calc case | calc, not S5 |
| Full Metal Body, Simple, Adrenaline Orb, Mold Breaker-bypass cases, Neutralizing Gas, Mind's Eye, Mycelium Might, Clear Amulet | **absent** | none | skip |

Additional Intimidate edge cases to cover:

- Substitute blocks it (check Showdown), Protect does not.
- The drop is a stage change, so switching out resets it.
- Fires at battle start (Speed-ordered with other setters), on switch-in, on KO replacement, and when a Mega Evolves into a form with Intimidate (Manectite's Mega is in the items list, check `champions.json`).
- Doubles: hits both adjacent foes, skips an empty slot; a fainted foe is skipped.
- Does not trigger Defiant or Competitive when the drop comes from the mon's own move (Close Combat); only foe-caused drops count.

## Open questions

1. Champions-specific rule changes to verify: paralysis chance, sleep and freeze behaviour, crit rate, and any move changes beyond the 31 overrides in the data.
2. The old `battle_cases.json` and `damage_cases.json` were not in the zip, so cases are rebuilt and each must cite a source.
3. Do the four "block Intimidate" abilities (Inner Focus, Oblivious, Own Tempo, Scrappy) behave that way in Champions? Verify in S0 from Showdown's `abilities.ts`.
