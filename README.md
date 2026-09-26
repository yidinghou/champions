# Pokémon Champions data

Local reference data for Pokémon Champions (current: Regulation M-C, Sept 9 – Dec 2, 2026; Ranked Season M-6).

## Refresh the data

```sh
pip install -e .              # stdlib only, Python 3.8+; gives you the `champions` command
champions fetch champions     # ~1 min
```

Writes `src/champions/data/champions.json` (~143 KB: 231 species, 380 forms with types, base stats, abilities). The file is committed on purpose: it's small, and diffs show what changed between regulations.

## Files

- `champions/fetch/champions.py` — generates `src/champions/data/champions.json` (raw base stats, types, abilities).
- `champions/fetch/roster_check.py` (`champions check-roster`) — checks `new_in_mc` tags against Showdown's roster (exit 1 on mismatch). Run after `champions/fetch/champions.py`; update `MC_COMMIT` for a new regulation.
- `champions/fetch/reference.py` — generates `src/champions/data/items.json` (165 legal held items), `src/champions/data/types.json` (18-type chart) and `src/champions/data/abilities.json` (216 abilities with descriptions) from Showdown and PokéAPI.
- `champions/fetch/moves.py` — generates `src/champions/data/learnsets.json` and `src/champions/data/moves.json` from Pokémon Showdown's `champions` mod, with PP from Serebii (run after `champions/fetch/champions.py`).
- `champions/calc.py` — damage calculator: `champions calc garchomp earthquake baxcalibur --atk-nature jolly --atk-sp attack=32 --item lifeorb`. Level 50, Gen 9 formula, min-max over 16 rolls, % of HP, hits to KO. Scope and limits in its docstring; tests: `python3 -m unittest discover -s tests -t .`. Add real in-game hits to `src/champions/data/damage_cases.json` (format described in its `_format` key).
- `champions/lookup.py` — offline lookup: `champions lookup baxcalibur -n jolly -s attack=32,speed=32`, `--moves` for the movepool, `--learns "fake out" --type grass --new` to filter, `--item focus` to search items, `--ability regenerator` for ability text and who has it. Also shows type weaknesses. See its docstring.
- `src/champions/data/rules.json` — hand-maintained battle rules and regulation dates (level 50, one Mega, etc.).
- `champions/stats.py` — computes level-50 battle stats from raw base stats at lookup time (`champions stats baxcalibur jolly speed=32,attack=32`). Raw data stays raw; nothing derived is saved.

`champions/stats.py` uses Champions' Stat Point system (66 SP, max 32 per stat, +1 each at level 50, nature applied after). Formula comes from champsdex.com and totals from Game8; confirmed in-game by the user. Details in `src/champions/data/rules.json`.

## Where the data comes from

- **Roster and stats:** [PokéAPI](https://pokeapi.co/api/v2/pokedex/champions) `champions` pokédex (community-contributed, no auth). It lists everything in the game but has **no regulation/season info**.
- **Regulation M-C additions:** hand-maintained `NEW_IN_MC` in `champions/fetch/champions.py` (exact form names), verified by `champions/fetch/roster_check.py` (`champions check-roster`) against Pokémon Showdown's champions roster. The [official announcement](https://www.pokemon.com/us/news/get-ready-for-regulation-set-m-c-in-pokemon-champions) is the source of truth for rules and dates.

## Known gaps

- `champions/calc.py` models STAB, type effectiveness, crit, spread, burn, stages, weather, terrain, screens, Helping Hand, multi-hit moves, resist berries, flag-based power abilities (Tough Claws, Iron Fist...), -ate abilities, several defender abilities, and a handful of variable-power moves. 45 cases in `src/champions/data/damage_cases.json` match Pikalytics' Champions calculator (regenerate with `tools/pikalytics_harness.js`); Fluffy is hand-derived because Pikalytics doesn't apply it. Not modeled: weight/HP-based power moves, Sheer Force, most other items/abilities. Nothing is checked against in-game damage yet.
- Ability descriptions are main-series text (e.g. Ice Body still says "hail"). `champions_override` marks abilities Showdown's Champions mod overrides; that can be a real change (Regenerator) or an implementation detail (Berserk).
- Anything PokéAPI lists may not be legal in M-C. Over-inclusion is intentional; filter at lookup time.

## Each new regulation

1. Read the official announcement; update `NEW_IN_MC` in `champions/fetch/champions.py` and `MC_COMMIT` in `champions/fetch/roster_check.py` (the Showdown commit that shipped it).
2. Run `champions fetch champions`, then `champions check-roster` until it passes, then `champions fetch moves`.
3. Review the `src/champions/data/` diff.

## Version history

Development is tagged linearly (`git tag -n`): v0.1.0 data fetcher, v0.2.0 stats/Stat Points, v0.3.0 moves & learnsets, v0.4.0 lookup CLI, v0.5.0 items & type chart, v0.6.0 abilities, v0.7.0 damage calculator, v0.8.0 calculator verified against Pikalytics, v0.9.0 installable package (`src/` layout, `champions` CLI), v0.10.0 broader damage calc and CI. Tags before v0.9.0 use the old flat-script layout. Design notes live in `docs/DECISIONS.md` and `docs/DEVLOG.md`.
