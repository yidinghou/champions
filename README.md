# Pokémon Champions data

Local reference data for Pokémon Champions (current: Regulation M-C, Sept 9 – Dec 2, 2026; Ranked Season M-6).

## Refresh the data

```sh
python3 fetch_champions.py   # stdlib only, Python 3.8+, ~1 min
```

Writes `data/champions.json` (~143 KB: 231 species, 380 forms with types, base stats, abilities). The file is committed on purpose: it's small, and diffs show what changed between regulations.

## Files

- `fetch_champions.py` — generates `data/champions.json` (raw base stats, types, abilities).
- `fetch_moves.py` — generates `data/learnsets.json` and `data/moves.json` from Pokémon Showdown's `champions` mod, with PP from Serebii (run after `fetch_champions.py`).
- `lookup.py` — offline lookup: `python3 lookup.py baxcalibur -n jolly -s attack=32,speed=32`, `--moves` for the movepool, `--learns "fake out" --type grass --new` to filter. See its docstring.
- `data/rules.json` — hand-maintained battle rules and regulation dates (level 50, one Mega, etc.).
- `stats.py` — computes level-50 battle stats from raw base stats at lookup time (`python3 stats.py baxcalibur jolly speed=32,attack=32`). Raw data stays raw; nothing derived is saved.

`stats.py` uses Champions' Stat Point system (66 SP, max 32 per stat, +1 each at level 50, nature applied after). Formula comes from champsdex.com and totals from Game8; confirmed in-game by the user. Details in `data/rules.json`.

## Where the data comes from

- **Roster and stats:** [PokéAPI](https://pokeapi.co/api/v2/pokedex/champions) `champions` pokédex (community-contributed, no auth). It lists everything in the game but has **no regulation/season info**.
- **Regulation M-C additions:** hand-maintained in `NEW_IN_MC` / `NEW_MEGAS_MC` in `fetch_champions.py`, taken from the [official announcement](https://www.pokemon.com/us/news/get-ready-for-regulation-set-m-c-in-pokemon-champions) (source of truth). Cross-checked against [Game8](https://game8.co/games/Pokemon-Champions/archives/618064).

## Known gaps

- Official post says 24 new Pokémon; Game8 lists ~22 and our list has 21 species + 6 Megas. Unresolved.
- Multi-form species (Toxtricity, Indeedee, Squawkabilly) only tag the default form as `new_in_mc`.
- Anything PokéAPI lists may not be legal in M-C. Over-inclusion is intentional; filter at lookup time.

## Each new regulation

1. Read the official announcement, update the two sets in `fetch_champions.py`.
2. Re-run the script and review the `data/champions.json` diff.
