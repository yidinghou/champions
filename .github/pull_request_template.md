Closes #

## What changed

## Checklist
- [ ] Scenario tests were added to `tests/test_battle_cases.py` **before** the engine change, and I saw them fail first
- [ ] Each new scenario's class docstring cites a source (Smogon, Bulbapedia, Showdown test, or in-game)
- [ ] `PYTHONPATH=src python3 -m unittest discover -s tests -t . -v` passes
- [ ] New moves are added to `battle/moves.py` only if the engine models them correctly
