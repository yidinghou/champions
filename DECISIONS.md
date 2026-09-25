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

**Known gap:** Showdown doesn't model Champions PP. Serebii shows different values (e.g. Acrobatics 16 vs main-series 15), so `moves.json` calls it `pp_main_series`. Cross-check: 510 moves and Rillaboom's 67-move pool match Serebii exactly.
