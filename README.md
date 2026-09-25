# Pokémon Champions data

Local reference data for Pokémon Champions (current: Regulation M-C, Sept 9 – Dec 2, 2026; Ranked Season M-6).

## Refresh the data

```sh
python3 fetch_champions.py   # stdlib only, Python 3.8+, ~1 min
```

Writes `data/champions.json` (~143 KB: 231 species, 380 forms with types, base stats, abilities). The file is committed on purpose: it's small, and diffs show what changed between regulations.

## Files

- `fetch_champions.py` — generates `data/champions.json` (raw base stats, types, abilities).
- `check_roster.py` — checks `new_in_mc` tags against Showdown's roster (exit 1 on mismatch). Run after `fetch_champions.py`; update `MC_COMMIT` for a new regulation.
- `fetch_reference.py` — generates `data/items.json` (165 legal held items) and `data/types.json` (18-type chart) from Pokémon Showdown.
- `fetch_moves.py` — generates `data/learnsets.json` and `data/moves.json` from Pokémon Showdown's `champions` mod, with PP from Serebii (run after `fetch_champions.py`).
- `lookup.py` — offline lookup: `python3 lookup.py baxcalibur -n jolly -s attack=32,speed=32`, `--moves` for the movepool, `--learns "fake out" --type grass --new` to filter. See its docstring.
- `data/rules.json` — hand-maintained battle rules and regulation dates (level 50, one Mega, etc.).
- `stats.py` — computes level-50 battle stats from raw base stats at lookup time (`python3 stats.py baxcalibur jolly speed=32,attack=32`). Raw data stays raw; nothing derived is saved.

`stats.py` uses Champions' Stat Point system (66 SP, max 32 per stat, +1 each at level 50, nature applied after). Formula comes from champsdex.com and totals from Game8; confirmed in-game by the user. Details in `data/rules.json`.

## Where the data comes from

- **Roster and stats:** [PokéAPI](https://pokeapi.co/api/v2/pokedex/champions) `champions` pokédex (community-contributed, no auth). It lists everything in the game but has **no regulation/season info**.
- **Regulation M-C additions:** hand-maintained `NEW_IN_MC` in `fetch_champions.py` (exact form names), verified by `check_roster.py` against Pokémon Showdown's champions roster. The [official announcement](https://www.pokemon.com/us/news/get-ready-for-regulation-set-m-c-in-pokemon-champions) is the source of truth for rules and dates.

## Known gaps

- Anything PokéAPI lists may not be legal in M-C. Over-inclusion is intentional; filter at lookup time.

## Each new regulation

1. Read the official announcement; update `NEW_IN_MC` in `fetch_champions.py` and `MC_COMMIT` in `check_roster.py` (the Showdown commit that shipped it).
2. Run `fetch_champions.py`, then `check_roster.py` until it passes, then `fetch_moves.py`.
3. Review the `data/` diff.
