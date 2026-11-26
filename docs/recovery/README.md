# Recovered notes

Saved from work done on another computer. **Most of the code these notes describe is not in this repo yet.** Treat
them as specs for rebuilding it, not as a description of the current code. Measurements and test counts in them came
from that computer.

| File | What it is | Code here? |
|---|---|---|
| `DECISIONS.md` | Decision log with 030 and 031 | 030 yes, 031 no |
| `ENGINE.md` | Engine doc with charge moves and the explorer | No for those two parts |
| `ISSUE_DRAFT_damage_estimate.md` | The damage-estimate fix, marked "fixed locally" | No |
| `ISSUE_DRAFT_charge_moves.md` | Charge moves, two batches | No |
| `ISSUE_DRAFT_root_filter_switches.md` | The shortlist doesn't anticipate switches | Not started |
| `SPIKE_mcts_no_shortlist.md` | MCTS shortlist experiments (its `.tmp/` scripts are lost) | No scripts |
| `charge-moves-decisions.html` | Charge-move choices and Showdown rules, with citations | No |
| `explorer_template.html` | Front end of the MCTS explorer, from a saved copy of the page. `__DATA__` stands for the embedded data. | No server |

A sample of the explorer's data is in `tests/fixtures/explorer_data_sample.json`. It is trimmed (no images, and only a
few catalog entries), so it shows the shape of the data and can't run the page by itself.

`engine-explained.html` and `rollout-vs-live.html` matched the copies in `docs/`, so they aren't repeated.

The current docs are still `docs/DECISIONS.md` and `docs/ENGINE.md`. Move each newer section there when its code is
rebuilt. The rebuild stages are tracked in the local `TODO.md`.
