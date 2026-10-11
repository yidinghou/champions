# Writing battle tests (`tests/test_battle_cases.py`)

One test class per mechanic (`TurnOrder`, `Priority`, `TrickRoom`, `Paralysis`, `Accuracy`, `SpreadMoves`,
`FirstTurnMoves`, `Protect`, `Fainting`). Each class docstring cites its source (Smogon, Bulbapedia, a Showdown
test, or in-game). Add a test, watch it fail, then make the engine pass it. Damage numbers are different:
they stay data-driven in `data/damage_cases.json` (see DECISIONS 011).

```python
class Accuracy(BattleTest):
    """https://bulbapedia.bulbagarden.net/wiki/Accuracy"""
    def test_90_percent_move_hits_on_89_and_misses_on_90(self):
        b = duel(mon("garchomp", "aquatail"), mon("incineroar", "tailwind"), chance=[89, 90])
        self.assertEqual(exchange(b, "aquatail", "tailwind").missed, [])
        self.assertEqual(exchange(b, "aquatail", "tailwind").missed, ["p1a"])
```

## Helpers (top of the test file)
- `mon(species, *moves, **keys)` builds a team entry. Keys: `nature`, `sp`, `item`, `ability`, `status` (`par`
  etc.), `boosts` (`{"speed": 2}`), `turns_out`, `hp` (current HP, 1..max). Unknown keys or moves raise, and so does
  a move the engine does not model yet (`moves.is_supported`).
- `duel(p1_mon, p2_mon, **battle_kwargs)` is a 1v1 `Battle`; `exchange(b, p1_move, p2_move)` plays one turn where
  each side hits the other (`trickroom`, `tailwind`, `protect` take no target).
- `use(move, target=None)` builds an action for hand-written turns (doubles, switches). A switch is
  `{"switch": team_index}`. Every living active mon needs an action.
- `BattleTest.assertDamaged(b, "p2:0")` / `assertFull(...)` take team refs (`side:index`).
- For a KO, call `b.replace("p2a", team_index)` once `got.pending` names the slot.

## Battle options
- `active=2` for doubles. Slots are `p1a`, `p1b`, `p2a`, `p2b`.
- `field={"trick_room": 5, "tailwind_p1": 4}` sets turns remaining (0 = off).
- `chance=[...]` (percents, 0-100) forces the accuracy and full-paralysis rolls in the order they are needed: a move
  hits when roll < accuracy, a paralyzed mon is stopped when roll < 25, and moves that cannot miss (or have 100
  accuracy) consume nothing. Once the list runs out, rolls come from the seed.
- `seed` (default 0) fixes speed ties and damage rolls.

## Turn results (`got = b.turn(...)`)
`got.order` (`slot:move`, resolution order, including flinched/failed attempts), `.flinched`, `.failed`,
`.blocked` (attackers stopped by Protect), `.missed` (attackers whose move missed, once per target), `.paralyzed`,
`.pending` (slots needing a replacement), `.log`. Battle state: `b.mon(slot)`, `b.team_mon(ref)`, `b.winner`
(`"p1"`, `"p2"`, `"draw"` or `None`), `b.field`.

Pick test moves that cannot KO or be immune (Mud Slap is the default). A Normal-type Fake Out does nothing to a
Ghost, which bit the first draft.

## Watching a test in `champions play`
From a source checkout, `champions play` lists every test here under **Battle test** on the setup screen. Load one
and press **Step ▶** to play its recorded turns one at a time (Undo steps back; playing your own turn leaves the
script). The first `Battle` a test builds is the one shown, with its forced `chance` rolls and seed. Outside a
checkout the picker is hidden.

Run locally without installing: `PYTHONPATH=src python3 -m unittest discover -s tests -t . -v`
