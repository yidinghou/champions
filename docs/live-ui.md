# Live game tracker: requirements

`champions live --team FILE [--port 8001] [--no-open]` serves one page on 127.0.0.1 for tracking a **real** doubles game.
You enter what happened; the server answers Speed order and damage ranges from the repo's own engine and calc.
Look and flow follow [reference-card-solver-ui.md](reference-card-solver-ui.md) and the replay viewer ([viewer-ui.md](viewer-ui.md)).
Team file (optional): a JSON list of specs (`species, ability, item, nature, sp, moves`); see `teams/sample.json`. Without it you pick your team on step 1.

## Principles
L1 standard library only (plain HTML/CSS/JS, `ThreadingHTTPServer`). L2 the page computes no battle rules: Speed is `engine.turn.speed`,
damage is `calc.damage.damage`; the page only applies stat stages to the shown numbers. L3 nothing moves or resizes as results arrive; the
board fits the window with no scrollbar. L4 errors always show in the caption line. L5 state lives in the browser (`localStorage["champions-live-v1"]`); the server keeps none.

## Requirements
| ID | Requirement | Accepted by |
|---|---|---|
| LIVE-01 | Serves `/`, `/sprites/<species>.png` (name-pattern checked), `/api/dex`, `/api/team` (re-read each call); anything else is 404. | `test_live_server.py::test_page_and_data`, `::test_only_known_routes_and_sprites` |
| LIVE-02 | `POST /api/scout` takes `{mine, foes, weather, tailwind, trick_room}` and returns `order` (foes as min-max ranges), `calc`, `threats` (Watch out: >=10% OHKO or >=40% 2HKO), `board`. | `test_live_scout.py::Speed`, `::Calc`, `test_live_server.py::test_scout_a_board` |
| LIVE-03 | Bad input is a 400 with `{"error": text}`. | `test_live_scout.py::Errors`, `test_live_server.py::test_errors_are_400_with_a_message` |
| LIVE-04 | Foe builds are the commonest MunchStats set; seen moves are pinned first. | `test_live_scout.py::Errors::test_seen_moves_are_pinned` |
| LIVE-05 | Step 1 is two panels like the board (theirs red, yours blue). Their side is optional: type any of their 6 (autocomplete, duplicates refused) or add who they led from an empty slot on the board. Your team comes from the team file (6 in `teams/sample.json`); click the 4 you bring (1-2 lead, 3-4 back). | manual M1 |
| LIVE-11 | **No team file:** `/api/team` is empty and step 1 lets you pick your 6 by name (datalist); ⚙ sets ability, item, nature, Stat Points and moves. `POST /api/team/build {specs}` returns the team as the page shows it (400 on a bad spec); the page sends `team` (the specs) with each `/api/scout`. The team lives in the browser. | `test_live_server.py::NoTeamFile`, manual M6 |
| LIVE-06 | Edits on the board: drag HP, click/right-click a stat (+1/-1; undoable), click a name to cycle status (undoable), item tab, switch via sprite click, picker or dragging a roster mini onto a card. | manual M2 |
| LIVE-09 | **Logging a turn is a click-through.** Click a move on any card (in the order things happened) > click the target card (skipped when the move has none, spreads, or only one can be hit) > a box over the target asks what happened: damaging moves take the target's HP (preset to the calc's middle; yours in HP, theirs in %; KO, Missed, Protected), status moves ask Hit / Missed / Protected. A target that Protected earlier in the turn defaults to Protected. | manual M5 |
| LIVE-10 | **Certain effects apply by themselves**, read from the move's `short_desc` by `live/moveflow.py`: stat changes on user or target, a sure status (Sleep Powder once it hits, unless the target's type blocks it), Fake Out's flinch (the target is marked as flinched if it hasn't moved), recoil and drain from the damage entered, heals, Trick Room, Tailwind, weather, Protect. **Chance effects are asked** after the HP ("Frozen 10%", "Flinched 30%"; a flinch is offered only to a mon that hasn't moved), with a manual status row. Pivot moves ask who came in. A moved mon is locked for the turn; a flinched one shows a tag you can click if it didn't. Undo last reverts a whole action. | `test_live_scout.py::MoveFlow`, manual M5 |
| LIVE-07 | Conditions chips (Trick Room, Tailwind either side, Weather auto/sun/rain/sand/snow/none) re-scout within ~120 ms; a late reply never overwrites a newer one. | manual M3 |
| LIVE-08 | End turn logs the turn, drops PP, asks who comes in for each fainted slot. State survives reload; New game resets all but their 6 and your 4. | manual M4 |

## Manual checks
M5 click Fake Out on their Rillaboom, click your Garchomp, type its HP, Done: your Garchomp is tagged flinched; Undo last puts it back. Click Rock Slide on yours: both foes are targets; enter HP, then Flinched 30% chips appear. Run `champions live --team teams/sample.json`. M1 enter two foes, pick 4, Board. M2 drag an HP bar and see Watch out change; +2 a foe's Speed and see the order move.
M3 toggle Trick Room: the order reverses. M4 mark a move, End turn, reload: PP and the turn log persist. Resize to 1280x720: no scrollbar.

M6 run `champions live` with no `--team`, type Garchomp and Incineroar, click their numbers, Board: Speed order shows.

## Not done yet (from the reference)
Foe stat curves and ranges on the card, the Mega bar and Mega forms, item chips and type icons on minis, the switch tab and who-came-in display,
the mid-turn row editor (blur focus, damage box), pivot prompts, Plans.
