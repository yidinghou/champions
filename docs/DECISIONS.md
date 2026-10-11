# Decisions

Short log of choices and why, newest last. Add an entry when we pick between real alternatives.

## 001 — PokéAPI for base data (2026-09-25)
Base stats, types, abilities and Mega forms come from PokéAPI's `champions` pokédex. Free, no auth, has Champions forms incl. Z-Megas.
**Trade-off:** no regulation info. Over-inclusion is fine; we filter at lookup time. M-C additions are tagged by hand from the official announcement (source of truth).

## 002 — Keep raw data raw; compute level-50 stats in code (2026-09-25)
Level 50 isn't a single number: it depends on nature and stat investment. So `data/champions.json` holds base stats and `stats.py` computes at lookup. No derived file to keep in sync.

## 003 — Commit `data/` to git (2026-09-25)
It's ~150 KB. Diffs between regulations are useful history. Revisit if it grows large or noisy.

## 004 — Champions stat system = Stat Points (2026-09-25)
66 SP total, max 32 per stat, +1 each at level 50, no IVs, nature applied after SP. Formula from champsdex.com, totals from Game8, confirmed in-game by the user. See `data/rules.json`.

## 005 — Showdown's `champions` mod for moves and learnsets (2026-09-25)
PokéAPI has no Champions learnsets (Megas have zero moves). Options considered: (A) raw files from `smogon/pokemon-showdown` `data/mods/champions/`, (B) `@pkmn/*` npm packages, (C) scraping Serebii.
**Chose A:** official, open-source, updated the same day M-C shipped, no Node dependency. Serebii scraping is the fallback if A breaks.
**Caveat:** the mod's `moves.ts` only holds *overrides* on the main-series moves, so we merge it onto Showdown's compiled `moves.json`.

## 006 — Champions PP from Serebii (2026-09-25)
Showdown doesn't model Champions PP, and Serebii's values differ from main series for 411 of 510 moves (e.g. Acrobatics 16 vs 15, Assurance 12 vs 10). So `fetch_moves.py` reads PP from Serebii's Champions moves page: one request, ~280 KB, robots.txt allows it.
**Trade-off:** this is the one field that depends on scraping HTML. If the page layout changes the fetch prints "no PP" and leaves `pp` null rather than guessing. Everything else stays on Showdown.

## 007 — Guard M-C tags with Showdown's roster (2026-09-25)
Our hand list disagreed with the official "24 new Pokémon". Showdown's champions mod flips newly legal Pokémon from Past/Illegal to legal in the commit that ships a regulation, so `check_roster.py` diffs legality before/after that commit. Result: 35 added forms (29 non-Mega + 6 Megas); Game8's list had missed Farfetch'd, Sirfetch'd and non-Alolan Persian, and the multi-form species (Toxtricity, Indeedee, Squawkabilly, Alolan Persian).
`NEW_IN_MC` stays hand-maintained (exact form names) but the check fails loudly if it drifts. Deriving it automatically was rejected: it would make the PokéAPI fetch depend on Showdown.

## 008 — Items and type chart from Showdown; legality = base flag + champions override (2026-09-25)
Showdown's compiled `items.js` has names/descriptions but drops availability flags, so `fetch_reference.py` reads `isNonstandard` from the base `items.ts`, overlays the champions mod's overrides (null = available, e.g. Mega Stones), and keeps items with no flag. Result: 165 legal items.
**Cross-check:** Serebii's Champions items page lists the same 165, in both directions. Notably not legal: Assault Vest, Choice Band, Lagging Tail.
Type chart: 18 types from `typechart.js` (Stellar dropped, Tera-only).

## 009 — Ability text from PokéAPI, override flag from Showdown (2026-09-25)
Showdown's compiled `abilities.js` nests objects in a way that's fragile to parse without a JS engine. PokéAPI's ability endpoint has descriptions keyed by the same slugs we already store, and `is_hidden` per Pokémon (now saved as `hidden_ability`). Showdown's champions mod only supplies a `champions_override` flag for 7 abilities (Berserk, Emergency Exit, Healer, Natural Cure, Regenerator, Run Away, Unseen Fist).
**Limits:** descriptions are main-series text, and the flag doesn't say what changed. Verify a flagged ability in-game or on Serebii before relying on it.

## 010 — Own damage calculator, small modeled surface (2026-09-25)
Built `calc.py` on the standard Gen 9 formula (level 50) using our own stats, moves, types and items, instead of wrapping Showdown's calc. It applies modifiers in game order with a floor after each step, and prints which modifiers it used so unmodeled effects are visible rather than silently wrong.
**Modeled:** STAB (incl. Adaptability), type effectiveness, crit, spread, burn, stat stages, sun/rain, Life Orb, Expert Belt, type-boost items, Huge/Pure Power, Technician, Levitate, Thick Fat.
**Not modeled:** terrain, screens, most abilities and items, multi-hit and variable-power moves. 

## 011 — Pikalytics' Champions calculator is the source of truth for damage (2026-09-25)
The user picked https://www.pikalytics.com/damage-calculator (a Smogon-calc UI with a Champions ruleset, Stat Points as the EV field). We drive it in a browser via `tools/pikalytics_harness.js` and store its results, including all 16 rolls, as `data/damage_cases.json`; `test_damage_cases.py` runs our calculator against them.
**Result:** 20 site cases (each modifier: STAB, SP, nature, 4x/resisted, crit, spread, Life Orb, burn, stages, sun/rain, special, type-boost item, Body Press, Expert Belt, Adaptability, Huge Power, Technician, Thick Fat, Levitate) match exactly. The first run had 3 off-by-one failures, all items: the game applies modifiers in 4096ths with half-down rounding, and type-boost items (Charcoal) boost base power, not final damage. Fixed in `calc.py` (`poke_round`, `bp_mods`).
**Limits:** the site's Blank Sets have junk default abilities (see the harness header); Levitate isn't a discriminating check (Rotom takes 0 from Earthquake on the site either way); it's a third-party site, not the game. Still unchecked in-game.

## 012 — Battle engine built test-first from data-file scenarios (2026-10-09)
`src/champions/battle/` resolves turns (priority, then Speed, re-sorted after every action; Trick Room, Tailwind, Fake Out, Protect, switching). Behavior is specified as named scenarios in `tests/test_battle_cases.py` (how-to: `docs/BATTLE_CASES.md`), one test class per mechanic, each class docstring citing its source. A scenario is written and seen failing before the engine change that satisfies it. *(Originally a data file, `data/battle_cases.json`; moved into per-mechanic test classes on 2026-10-11 so setup, dice and expectation sit together. Damage cases stay data-driven per 011.)*
**Source of truth:** Pikalytics only covers damage, so turn mechanics are checked against Smogon/Bulbapedia (cited per test class). Showdown's `test/sim` suite is the next oracle to port from. Not yet checked in-game.
Fainting works between turns: `pending_replacements()` / `replace()`, an emptied doubles slot when no reserve is left, `winner`, and a move aimed at a fainted foe redirects to its partner. `legal_actions()`, `snapshot()` and per-action `TurnResult.frames` exist for the UI.
**Limits:** no accuracy, full-paralysis, spread moves, abilities or weather yet. `moves.is_supported` lets in only plain single-target damaging moves (secondary effects ignored) plus Protect, Trick Room and Tailwind (257 of 510 moves); everything else is rejected with `ValueError`, never silently mis-simulated.

## 013 — `champions play`: stdlib server, state = (config, action history) (2026-10-09)
`src/champions/play/` serves a JSON API and one static page with `http.server`; no dependencies. The browser holds no game logic: it posts actions and renders the view the engine returns (snapshot, legal actions, per-action frames).
**State:** the server keeps only the team config (with a seed) and the list of turns/replacements. Every change replays history onto a fresh `Battle`, so undo and restart are a shorter list, and a rejected action is tried on a replay copy first and never recorded.
**Errors:** all bad input is `{error}` with HTTP 400 (lookup `KeyError`/`SystemExit` and wrong JSON types are converted to `ValueError`); unknown routes are 404; anything else is a 500 with the exception name only.
**Limits:** one game per process, no auth or persistence, and the page is a minimal vanilla-JS UI (no type icons). Spec: `tests/test_play_api.py`.

