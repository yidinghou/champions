# Dev log

Timeline of what we did and learned, newest first. Decisions live in `DECISIONS.md`; open work at the bottom.

## 2026-09-25
- Researched Champions moves. PokéAPI has none; Showdown's `champions` mod does (decision 005). Built `fetch_moves.py` -> `data/learnsets.json` (380 forms) and `data/moves.json` (510 moves). Matches Serebii on move count and Rillaboom's pool. PP comes from Serebii's Champions page (decision 006): Showdown lacks it and main-series PP is wrong for 411/510 moves.
- Confirmed the Stat Point formula in-game (`6ddc803`, decision 004).
- Added `stats.py` and `data/rules.json`; level 50, SP system (`4f689e4`, `0aa7255`).
- First commit: fetcher, README, data snapshot of 231 species / 380 forms (`80ba0d6`). Decisions 001–003.
- Started from the question "where does Champions season/roster data live?". Answer: web pages only for season/rules; PokéAPI added a `champions` pokédex in April 2026.
- Current season: Regulation M-C (Sept 9 – Dec 2, 2026), Ranked Season M-6.

## Open
- Official says 24 new Pokémon in M-C; our list has 21 species + 6 Megas. Find the missing ones.
- Multi-form species (Toxtricity, Indeedee, Squawkabilly) only tag the default form as `new_in_mc`.
- Items and type chart not yet in the data (Showdown `items.ts` is the likely source).
- Lookup CLI.
- Cross-check Showdown `formats-data.ts` against our M-C roster.
