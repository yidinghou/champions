# Replay viewer: requirements

`champions sim view FILE` writes one self-contained HTML page that steps through a replay. Its job is to let a
person **check the engine by eye**. Look and process are borrowed from [reference-card-solver-ui.md](reference-card-solver-ui.md), the requirements of a sibling project's live card-solver UI (reference only; not part of this repo's build).

## Principles

| # | Rule |
|---|---|
| V1 | **Standard library only.** The page is plain HTML, CSS and JS: no framework, no build step, no network. Sprites are embedded. |
| V2 | **The page computes no battle rules.** State comes from the engine, captured after every logged event. The only thing the page works out is the stage-adjusted stat number. |
| V3 | **Nothing moves or resizes** as steps change. Show change with colour, opacity, outline and `transform`. |
| V4 | **A result is never shown for less than the time it takes to read it.** Misses, "No effect" and protects outlive the animation (see V-06). |
| V5 | Errors are never silent. A replay the engine can't play fails with the engine's own message. |

## Requirements

| ID | Requirement | Accepted by |
|---|---|---|
| V-01 | `sim view FILE [-o OUT] [--no-open]` writes a single HTML file and opens it. | `test_viewer.py::test_writes_self_contained_html` |
| V-02 | One step per visible event, plus an "End of turn N" step where the engine changes state without logging (counters ticking down, volatiles expiring). The last step equals the engine's final state. | `test_viewer.py::test_every_replay_ends_on_the_engines_final_state` |
| V-03 | A move step names its targets and each target's outcome (`hit`, `missed`, `immune`, `protected`, `blocked`), plus the move's type, category and whether it spreads. | `test_viewer.py::test_move_frames_name_their_targets_and_outcomes` |
| V-04 | Controls: ← → step, Shift+← → turn, Space play, slider, click a log line to jump, raw-event toggle, exact-HP toggle, attack-animation toggle. | manual |
| V-05 | Attack animation whenever you land on a move step (stepping, play, a turn jump or a log click; not while dragging the slider): the attacker lunges (contact moves close in, others rear back); a beam and orb go to **every** target, including an ally hit by a spread move. | manual, `tests/replays/spread_doubles.json` |
| V-06 | **Outcomes persist and come first.** A miss, "No effect" or protect is announced before the hit animations of the other targets, and its result stays on screen until the next move (see "Outcome style" below). A blocked shot fizzles short and grey instead of reaching its target. | manual |
| V-07 | While playing, a step that has outcomes to read adds dwell time. | manual |

## Outcome style (V-06): decided

Chosen after comparing three proofs of concept (sticky badges, one-target-at-a-time with card tints, and this one):
a big label over the target card, misses and "No effect" first, then the hits. The label **stays until the next move**
(it clears when another move starts or the turn changes), and playback adds 1.2 s of dwell on a move that has one.
The losers are removed; their ideas (damage pills held to end of turn, per-target sequencing) are not planned.
