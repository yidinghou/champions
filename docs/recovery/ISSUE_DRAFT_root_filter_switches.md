# DRAFT issue: the root filter does not anticipate switches

Status: local draft, not filed. Split out of `ISSUE_DRAFT_damage_estimate.md`; not yet rewritten in plain language.

`candidate_slot_choices` keeps the top N damaging (move, target) choices per slot, scored against the board as it
stands. It never asks who will be in that slot after a switch, so a move that is only good against the incoming
Pokemon is cut before the search sees it.

Seen in the replay (MCTS vs MCTS, turn 1): MCTS expected "Garchomp switches to Venusaur". The opponent's Gengar had
Ice Beam -> Garchomp and Sludge Bomb -> Incineroar in its table, but not Sludge Bomb -> Garchomp's slot (Poison does
half damage to Garchomp right now, so it ranks low). The engine does reward it: checked directly, a Sludge Bomb aimed
at the slot hits the incoming Venusaur for 66, because switches resolve first and attacks hit whoever is in the slot.

Also note: "expected" in the replay is the highest-share option of the mix, not a certain prediction.

Possible fix: keep an attack aimed at each slot where the other side's best switch lands (or one option per target
slot). This grows the table, so measure the speed cost.
