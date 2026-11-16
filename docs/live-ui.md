# Live game tracker: requirements

`champions live --team FILE [--port 8001] [--no-open]` serves one page on 127.0.0.1 for tracking a **real** doubles game.
You enter what happened; the server answers Speed order and damage ranges from the repo's own engine and calc.
Look and flow follow [reference-card-solver-ui.md](reference-card-solver-ui.md) and the replay viewer ([viewer-ui.md](viewer-ui.md)).
Team file: a JSON list of specs (`species, ability, item, nature, sp, moves`); see `teams/sample.json`.

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
| LIVE-05 | Step 1: type their 6 (autocomplete from the 2nd letter, duplicates refused); click your 4 (1-2 lead, 3-4 back). | manual M1 |
| LIVE-06 | Board gestures: drag HP, click/right-click a stat (+1/-1), click a name to cycle status, click a move to mark it used (yours: PP drops at End turn; theirs: marked seen), item tab, switch via sprite click, picker or dragging a roster mini onto a card. | manual M2 |
| LIVE-07 | Conditions chips (Trick Room, Tailwind either side, Weather auto/sun/rain/sand/snow/none) re-scout within ~120 ms; a late reply never overwrites a newer one. | manual M3 |
| LIVE-08 | End turn logs the turn, drops PP, asks who comes in for each fainted slot. State survives reload; New game resets all but their 6 and your 4. | manual M4 |

## Manual checks
Run `champions live --team teams/sample.json`. M1 enter two foes, pick 4, Board. M2 drag an HP bar and see Watch out change; +2 a foe's Speed and see the order move.
M3 toggle Trick Room: the order reverses. M4 mark a move, End turn, reload: PP and the turn log persist. Resize to 1280x720: no scrollbar.

## Not done yet (from the reference)
Foe stat curves and ranges on the card, the Mega bar and Mega forms, item chips and type icons on minis, the switch tab and who-came-in display,
the mid-turn row editor (blur focus, damage box), pivot prompts, Plans.
