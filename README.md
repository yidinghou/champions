# Pokémon Champions data

Local reference data for Pokémon Champions (current: Regulation M-C, Sept 9 – Dec 2, 2026; Ranked Season M-6).

## Refresh the data

```sh
python3 fetch_champions.py   # stdlib only, Python 3.8+, ~1 min
```

Writes `data/champions.json` (~143 KB: 231 species, 380 forms with types, base stats, abilities). The file is committed on purpose: it's small, and diffs show what changed between regulations.

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
