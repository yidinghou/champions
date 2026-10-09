Closes #

## What changed

## Checklist
- [ ] Scenarios were added to `src/champions/data/battle_cases.json` (or tests added) **before** the engine change, and I saw them fail first
- [ ] Each new scenario cites a `source` (Smogon, Bulbapedia, Showdown test, or in-game)
- [ ] `PYTHONPATH=src python3 -m unittest discover -s tests -t . -v` passes
- [ ] New moves are added to `battle/moves.py` only if the engine models them correctly
