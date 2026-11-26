# DRAFT issue: the engine has no two-turn (charge) moves

Status: local draft, not filed. Found 2026-11-25 while building the explorer's set editor: Archaludon's Electro Shot
isn't offered.

**Update 2026-11-26:** the first batch is done (decision 031 in `docs/DECISIONS.md`; choices in
`docs/charge-moves-decisions.html`). Still open:
- the explorer's charging chip and "forced" tag (waiting on a POC);
- the second batch: Dig, Fly, Dive, Bounce, Phantom Force.

## What's wrong

The engine simulates none of the 10 moves that `moves.json` flags as charging (`"charge"` in `flags`). A team that
holds one is refused (`Unsupported: move not modeled`). So everything built on the engine plays these Pokémon with the
wrong sets:
- the explorer's set editor hides the move behind "Show the N moves the engine can't simulate yet", and its
  randomizer never draws it;
- the opponent belief's `project` view (`belief/support.py`) deletes it from every set.

| move | effect (short_desc) | who runs it (share of that Pokémon's sets, MunchStats) | how common that Pokémon is (Pikalytics, % of teams) |
|---|---|---|---|
| Electro Shot | +1 SpA, hits turn 2; no charge in rain | Archaludon 96% | 21% |
| Solar Beam | charges turn 1, hits turn 2; no charge in sun | Charizard 63%, Torkoal 27%, Venusaur 11%, Meganium 97% | 21%, 5%, 4%, 1% |
| Phantom Force | vanishes turn 1, hits turn 2; breaks protection | Dragapult 38%, Annihilape 22%, Ceruledge 8% | 2%, 3%, 2% |
| Solar Blade | as Solar Beam, physical | Leafeon 85% | ~0% |
| Dig | underground turn 1, hits turn 2 | Flareon 20% | ~0% |
| Meteor Beam | +1 SpA on turn 1, hits turn 2 | (none at 5%+) | |
| Fly, Dive, Bounce, Sky Attack | | (none at 5%+) | |

MunchStats data is from 2026-10-06. Archaludon (Electro Shot in rain) and Charizard (Solar Beam in sun) are two of the
most used Pokémon, and both are weather plays.

## What the mechanic needs

Check each rule against Showdown and `docs/CHAMPIONS_ASSUMPTIONS.md` before building it.

1. **Charge turn.** The move charges instead of hitting: Electro Shot and Meteor Beam raise Sp. Atk by 1. The
   Pokémon gets a `charging` volatile holding the move and its target. PP is spent on this turn only.
2. **Weather skips the charge.** Electro Shot in rain, Solar Beam and Solar Blade in sun: the move hits on turn 1 (still
   +1 SpA for Electro Shot). Check whether Solar Beam's power drops in other weather.
3. **Release turn.** On the next turn the Pokémon must use that move at the same target, with no switch.
   - `game.legal_choices` and `validate` gain the lock (Encore does the same in `volatiles.can_choose`).
   - `solver/actions.slot_choices` reads `legal_choices`, so MCTS would see one forced choice per charging slot.
4. **Interruptions.**
   - Switching out or fainting clears it: `clear_on_switch` already clears volatiles.
   - Flinching, sleep or paralysis on the release turn cancels the charge (check this).
   - Protect blocks the release. If the target has fainted, the move retargets as usual.
5. **Semi-invulnerable moves** (Dig, Fly, Dive, Bounce, Phantom Force): during the charge turn the user can only be hit
   by certain moves (Earthquake hits Dig, Surf hits Dive), and Phantom Force goes through Protect. This is a bigger
   change; do it second.
6. **Explorer and viewer.** A charge step in the turn animation ("Archaludon took in electricity"). The Choices card
   shows the forced release as the only option.

Suggested split:
- **First** (no invulnerability): Electro Shot, Meteor Beam, Solar Beam, Solar Blade, Sky Attack.
- **Second**: Dig, Fly, Dive, Bounce, Phantom Force.

Power Herb (skip the charge) isn't in `items.json`, so it's out of scope.

## Done when

- The first five moves are in `effects_table.MOVES`, with tests for:
  - the charge turn: no damage, +1 SpA where the move gives it;
  - the weather skip;
  - the forced release (only one legal choice, a switch refused);
  - PP spent once;
  - a flinch or sleep cancelling the charge;
  - Protect blocking the release;
  - switching out clearing the charge.
- In the explorer, Archaludon's editor lists Electro Shot near the top (about 95% of its sets), and a random Archaludon
  draws it.
