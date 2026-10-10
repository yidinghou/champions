# Battle scenario format (`data/battle_cases.json`)

Each case is run by `tests/test_battle_cases.py`. Add a case, watch it fail, then make the engine pass it.

```json
{
 "name": "Trick Room reverses speed order",
 "source": "https://www.smogon.com/dex/sv/moves/trick-room",
 "active": 1,
 "field": {"trick_room": 5},
 "teams": {"p1": [{"species": "incineroar", "moves": ["mudslap"]}], "p2": [{"species": "dragapult", "moves": ["mudslap"]}]},
 "turns": [{"p1a": {"move": "mudslap", "target": "p2a"}, "p2a": {"move": "mudslap", "target": "p1a"}}],
 "expect": {"turns": [{"order": ["p1a:mudslap", "p2a:mudslap"]}], "final": {"field": {"trick_room": 4}}}
}
```

- **Slots:** `p1a`, `p1b`, `p2a`, `p2b` (`active` = 1 or 2 per side). Team index refs look like `p1:0`.
- **Pokémon keys:** `species`, `moves`, `nature`, `sp`, `item`, `ability`, `status` (`par` etc.), `boosts` (`{"speed": 2}`), `turns_out`, `hp` (current HP, 1..max). Unknown keys or moves raise, and so does a move the engine does not model yet (`moves.is_supported`).
- **Field keys** (turns remaining, 0 = off): `trick_room`, `tailwind_p1`, `tailwind_p2`.
- **Actions:** `{"move": id, "target": slot}` or `{"switch": team_index}`. Every living active mon needs one; a mon can only use moves listed in its `moves`. A turn entry `{"_replace": {"p2a": 1}}` fills a slot after a KO (put `{}` in `expect.turns` at that position).
- **Per-turn expectations** (any subset): `order` (`slot:move`, in resolution order, including flinched/failed attempts), `flinched`, `failed`, `blocked` (attackers stopped by Protect), `missed` (attackers whose move missed, once per target), `paralyzed` (attackers fully paralyzed), `pending` (slots needing a replacement), `log`.
- **`final`:** `active` (slot -> species, or `null` for an emptied slot), `damaged` / `full` / `fainted` (team refs), `winner` (`"p1"`, `"p2"`, `"draw"` or `null`), `field`.
- `chance` (list of percents, 0-100) forces the accuracy and full-paralysis rolls in the order they are needed; a move hits when roll < accuracy, a paralyzed mon is stopped when roll < 25, and moves that cannot miss (or have 100 accuracy) consume nothing. Once the list runs out the rolls come from the seed.
- `seed` (default 0) fixes speed ties and damage rolls; `skip: true` parks a case.
- Pick test moves that cannot KO or be immune (Mud Slap is the default). A Normal-type Fake Out does nothing to a Ghost, which bit the first draft.

Run locally without installing: `PYTHONPATH=src python3 -m unittest discover -s tests -t . -v`
