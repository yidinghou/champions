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
