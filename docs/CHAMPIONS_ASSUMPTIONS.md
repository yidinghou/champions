# Champions vs Showdown: what is confirmed and what is a guess

Most engine numbers are Showdown's Gen 9 values. Pokémon Champions changes some of them. This page
records what was checked (2026-11-15), the source, and how sure we are.

Confidence: **confirmed** = a Champions source states it; **likely** = sources agree but timing is
marked "to be confirmed"; **guess** = no Champions source found, Showdown value kept.

## Changed to the Champions value

| Rule | Value in engine | Was | Confidence | Source |
|---|---|---|---|---|
| Paralysis full-para | 12.5% | 25% | likely | Serebii, Smogon research thread (1/8) |
| Freeze thaw | 25% per move attempt, forced on 3rd attempt | 20%, no cap | likely | Serebii, Smogon changelog (timing "to be confirmed") |
| Sleep length | asleep on attempt 1; wakes on attempt 2 with 1/3 chance, else attempt 3 | 1-3 turns uniform | likely | Serebii, Pokémon Zone. A Smogon post says "1-2 turns", so not settled |
| Sun blocks freeze | yes | yes | confirmed | Pokémon Zone (already modeled) |
| Electric Terrain blocks sleep, Misty Terrain blocks status and confusion | yes | yes | confirmed | Pokémon Zone (already modeled) |

Sleep wake-up: we assume the mon acts on the turn it wakes, as in the main games.

## Kept at the Showdown value (guess, no Champions source found)

Treat these as educated guesses. None has a Champions source that contradicts it.

- Confusion length (2-5 turns), Taunt (3), Encore (3), Disable (4).
- Weather and terrain: 5 turns, 8 with the extending item. Fan guides agree on 5 turns for both
  ability- and move-set weather, so the engine keeps 5 even though `abilities.json` prose says
  "indefinitely".
- Tailwind: 4 turns including the turn it is used (fan guides agree, with some wording
  disagreement). Trick Room: 5 turns.
- Screens: 5 turns, 2/3 reduction in doubles.
- Terrain boost x1.3, type items x1.2, Life Orb x1.3.
- Protean (once per entry vs every move), Oran Berry heal (10 HP).

## Edge cases left alone

These come up rarely and a human player would seldom choose them, so Showdown behaviour stays:
Safeguard vs Yawn, two Follow Me users, Brick Break on a miss.

## Other Champions differences found, not yet in the engine

From the Smogon thread. Worth a look when those moves are modeled:
Toxic Thread -2 Speed, Moonblast secondary 10%, Iron Head 20%, Dire Claw 30%, Salt Cure 1/16
(1/8 vs Steel/Water), Piercing Drill and Unseen Fist deal 1/4 through protection, Synthesis heals
66% in sun, 33% recoil moves deal 33%, Dragonize is x1.2. Leech Seed is reported at about 12% in game
(unconfirmed).
