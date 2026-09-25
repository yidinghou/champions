# Dev log

Timeline of what we did and learned, newest first. Decisions live in `DECISIONS.md`; open work at the bottom.

## 2026-09-25
- Damage tests are data-driven: `data/damage_cases.json` + `test_damage_cases.py`, using a new `calc.damage()` function.
- Added `calc.py` damage calculator and `test_calc.py` (decision 010). Not yet checked against in-game damage.
- Abilities: `data/abilities.json` (216, PokéAPI text, 7 flagged as overridden in Showdown's Champions mod), `hidden_ability` on each form, and `lookup.py` shows ability text plus `--ability` search (decision 009).
- `lookup.py --type` now takes dual types (`ghost/fire` or repeated flags) and rejects unknown types; before, a second `--type` silently overrode the first.
- Added `fetch_reference.py` (items, type chart) and taught `lookup.py` weaknesses and `--item` search. 165 legal items match Serebii's list exactly (decision 008).
- Added `check_roster.py`. Showdown says M-C added 35 forms; our list had 27. Missing: Farfetch'd, Sirfetch'd, and the extra forms of Toxtricity, Indeedee, Squawkabilly and Persian. That explains the official "24" vs Game8's 22 (decision 007). `NEW_IN_MC` is now exact form names and the check passes.
- Added `lookup.py`: name lookup with level-50 stats (nature and SP options), movepool, and filters by move/type/new-in-M-C.
- Researched Champions moves. PokéAPI has none; Showdown's `champions` mod does (decision 005). Built `fetch_moves.py` -> `data/learnsets.json` (380 forms) and `data/moves.json` (510 moves). Matches Serebii on move count and Rillaboom's pool. PP comes from Serebii's Champions page (decision 006): Showdown lacks it and main-series PP is wrong for 411/510 moves.
- Confirmed the Stat Point formula in-game (`6ddc803`, decision 004).
- Added `stats.py` and `data/rules.json`; level 50, SP system (`4f689e4`, `0aa7255`).
- First commit: fetcher, README, data snapshot of 231 species / 380 forms (`80ba0d6`). Decisions 001–003.
- Started from the question "where does Champions season/roster data live?". Answer: web pages only for season/rules; PokéAPI added a `champions` pokédex in April 2026.
- Current season: Regulation M-C (Sept 9 – Dec 2, 2026), Ranked Season M-6.

## Open
- Verify the 7 overridden abilities (what actually changed in Champions).
- Verify `calc.py`: add real hits to `data/damage_cases.json` (only one hand-worked case so far).
- Ideas: a team builder (item clause, one Mega, no duplicate dex numbers per `data/rules.json`) with team-wide type coverage.
