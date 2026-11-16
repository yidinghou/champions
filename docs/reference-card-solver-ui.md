# Scout UI (card solver): requirements to rebuild it from scratch

This is the one file a person or a fresh agent needs to rebuild the scout page, `champions scout --team FILE`, from an empty `static/cards/` folder. It covers:

- what the page is for, and the principles behind every choice;
- the numbered requirements and how each is accepted;
- the look, as design tokens, HTML skeletons and the CSS that defines it;
- every gesture and what it does;
- the server contract the page talks to.

Other docs go deeper on a single part: [board-ui.md](board-ui.md) (behaviour), [DESIGN.md](../DESIGN.md) §3 and §6 (IDs and manual checks), and [DECISIONS.md](../DECISIONS.md) 023–030 (why). Nothing here should contradict them. If they disagree, the code in `src/champions/play/static/cards/` wins, and the doc that drifted gets fixed.

Snapshot: 2026-11-15. It includes the uncommitted work on bench builds and showing who came in mid-switch ([SCOUTUI-18](#3-requirements), proposed).

---

## 1. Purpose and scope

The page is used **during a real game** of Pokémon Champions doubles, at level 50 with open team sheets. It follows the game's own flow:

1. **Team preview.** Type their 6. Click the 4 you bring, in order: 1–2 lead, 3–4 back.
2. **The game.** Keep a board of the two Pokémon on each side up to date: HP, status, stat stages, seen moves, items, Megas and the conditions. The page tells you who moves first (**Speed**) and which hits matter (**Watch out**).
3. **Each turn.** Lock in your moves on your cards, enter what happened as the turn plays, then End turn. The board updates and the turn folds into a log.
4. **Deciding.** **Plans** is a matrix of your plans × their likely replies, each cell played through the real battle engine.

**In scope:** the page at `/` and `/cards`, the test page at `/cards/test`, and the HTTP server that serves them and answers `/api/*`.

**Out of scope:** the battle viewer (`champions play`, see [battle-ui.md](battle-ui.md)), the terminal scout report, and the old scout page, which was deleted on 2026-11-11 and must not come back. Features from the old page are new work, built on the cards.

---

## 2. Principles

### 2.1 Hard constraints

| # | Rule |
|---|---|
| P1 | **Standard library only.** Python 3.8–3.12 with `dependencies = []`. The page is plain HTML, CSS and JavaScript, with no libraries, no framework and no build step. |
| P2 | **One command, one server.** `champions scout --team FILE` serves the page and the API from one process, so there's no second terminal, no static server and no CORS. The input step asks only for *their* 6, because your side comes from the team file. |
| P3 | **The page computes no battle rules.** It sends the board and draws what comes back. Speed, the weather, threats, calcs and builds all come from the server. The only exceptions are the turn log's order consequences (§9) and applying stat stages to builds for the stat cells. |
| P4 | **One copy of each rule.** Plans plays turns through the same `battle` engine the RL environment uses. It never ports a simulator to JS. |
| P5 | **Localhost only.** The server binds `127.0.0.1`. Bad input is a 400 with `{"error": text}`, an unknown route is a 404, and anything else is a 500 that names only the exception type. |
| P6 | **Errors are never silent.** Every failure shows in the caption line, including "Can't reach the scout server … Is `champions scout` still running?". |

### 2.2 UI principles

These came from the user's picks and rejections across decisions 023–030. Apply them to anything new.

| # | Principle | Where it came from |
|---|---|---|
| U1 | **Nothing moves or resizes** as results arrive, a menu opens, or a turn is played. Show change only with colour, opacity, outline, filter and `transform`. Empty slots are the exact size of a real card. | Elements that grew when a target was picked "felt bad". |
| U2 | **The board fits the window, with no scrollbar,** at 1920×1080 and smaller. No name or damage number is ever cut off. | Decision 025. |
| U3 | **Every assumption is a visible chip** you can flip. Lit = on, dim = off, dashed = assumed (not set by you), with a one-line reason ("Drizzle · auto"). | Plain toggles didn't read as "conditions". |
| U4 | **One readout per thing, details on hover.** Don't repeat a name or a number. Put breakdowns in `title` tooltips. | The HP-left popup was "too busy". |
| U5 | **Rule out impossible picks** rather than allow them and fix them later. There is no free dragging onto the field during a turn. A Pokémon comes in only by a lead pick, a switch or a replacement, and fainted or absent ones are greyed out of every list. | The game log was flooded by stray drags. |
| U6 | **Follow the real game's flow,** as a workflow in order (team preview → board → turn → plans). Don't build a dashboard of everything at once. Check you understand the flow before you lay anything out. | Three layout mockups were rejected for that. |
| U7 | **Separate things visually.** Use one tinted panel per side (red theirs, blue yours), each wrapping its roster and its two cards. Results go in their own panels (Log, Speed, Watch out). | Stacked, mixed sections were hard to scan. |
| U8 | **Enter things where the eye already is.** A turn's move and target are clicked on the cards, and damage is entered in a box over the target card, while everything else blurs. The Log only records. | Decision 027. |
| U9 | **Confirm explicitly.** A slider doesn't commit when you let go. ✓ Done does. A choice, once made, folds to one line with "change". | Decision 026 / playing POCs. |
| U10 | **Few buttons.** Your locked-in rows open straight to the damage. Rare actions (didn't move, other move, didn't flinch) are small links in one strip. | "Too many buttons". |
| U11 | **The order is dragged, never clicked.** Rows start in the expected order and move only when dragged. The one exception is a move changed into another priority bracket, which moves its own row. | Click-to-reorder "happened by accident". |
| U12 | **Styled after the game.** The big card copies the in-game HP plate and move menu: slanted bands, a stepped HP bar, big italic numbers, purple pills. | Decision 025, from the user's screenshot. |

### 2.3 How look decisions are made

Every look change goes through this loop. A rebuild that changes the look should too.

1. **Build 2–5 throwaway static POCs** in `tools/scout_poc/` (untracked). They are plain `.html` files opened straight from disk, with no server. They load the real `static/cards/*.js|css` by relative path and use data snapshotted into a `*-data.js` file (a small `snapshot_*.py` writes it). When several POCs share code, put it in `*-common.js/.css`.
2. **Put every open choice in as a toggle** on one POC, rather than asking questions or drawing ASCII. Where sizing matters, show a live readout (vh, how many items fit).
3. **Draw the real neighbours** (the item tab, the Mega bar, the roster), or collisions stay hidden. The switch tab first went on the right, where it hit the item tab.
4. **The user picks.** Wire in the pick, record it in `DECISIONS.md` (what was chosen and what lost), add or adjust a SCOUTUI requirement and an M check, then delete the POCs.

---

## 3. Requirements

"Accepted by" names an automated test in `tests/test_scout_server.py` (prefix `ScoutServer::`), `tests/test_scout.py` or `tests/test_plans.py`, or a manual check M# from §13.

| ID | Requirement | Accepted by |
|---|---|---|
| SCOUTUI-01 | Serves the page at `/` and `/cards` and the test page at `/cards/test`, plus only their files (fixed name patterns under `static/`). `/api/team` re-reads the team file and gives max HP. `/api/dex` gives learnsets, Pikalytics move usage, and each move's PP, priority and target. | `test_page_and_data`, `test_card_pages_and_their_files`, `test_dex_has_move_usage_and_pp`, `test_dex_moves_have_priority_and_target` |
| SCOUTUI-02 | `POST /api/scout` round-trips the board: HP, Tailwind, `ability_off`, seen moves, stat stages and status. | `test_scout_a_board`, `test_ability_off_round_trips`, `test_seen_moves_round_trip`, `test_stages_and_status_round_trip` |
| SCOUTUI-03 | Bad input is a 400 with a readable message. | `test_errors_are_400_with_a_message` |
| SCOUTUI-04 | Step 1:<br>• Type their 6 with autocomplete. A duplicate is refused.<br>• Click your 4 in order: 1–2 lead, 3–4 back. Clicking a numbered one drops it and the rest renumber.<br>• Board → needs your 4 and at least one of theirs. It opens with your leads in and their side empty.<br>• The 2 you don't bring are gone from the game.<br>• `/api/scout` accepts zero foes. | `test_scout_your_side_before_their_leads`, M5 |
| SCOUTUI-05 | Drag a roster Pokémon onto a card on its own side. Dropping it on the partner's slot swaps the two. Or pick it from the sprite. A fainted one can't come in. | M6 |
| SCOUTUI-06 | Edit on the cards: drag HP, click a stat (+1) or right-click it (−1), click the name to cycle status, click a foe move to mark it seen. HP, status and seen moves stay with a Pokémon across switches; stages reset. | M7 |
| SCOUTUI-07 | Layout: one panel per side, theirs over yours, in the left 3/4, fitted to the window. Speed and Watch out are in the right 1/4. Cards have the HP plate, the five stats beside it and the moves full width below. Stages and status change the numbers. | `test_scout.py::StagesAndStatus::*`, M8 |
| SCOUTUI-08 | The condition chips (weather, speed abilities off, Tailwind for either side, Trick Room) re-scout within about 120ms. | `test_ability_off_round_trips`, M9 |
| SCOUTUI-09 | State survives a reload (`localStorage` key `champions-cards-v1`), the turn log included. New game resets everything except their 6, your 4, the step and the switch rate. | M10 |
| SCOUTUI-10 | No panel jumps or resizes as results update. `/cards/test` plays every state-change animation. | M11 |
| SCOUTUI-11 | `POST /api/plans` plays every plan against every likely reply through the engine, and names Best vs likely and Safe pick. (This is the model half; see engine.md §E4.) | `test_plans.py::*`, `test_plans_a_board`, `test_plans_with_benches` |
| SCOUTUI-12 | Step 3: the matrix (plans × replies, each cell the end state and its KOs), the score column, and the Best and Safe tags. A cell opens its turn full screen, 1st to 4th, with a tab per Speed order. | M12 |
| SCOUTUI-13 | Plans shows only plans that nothing beats, with ties merged into one row. It holds at most 4 rows × 6 columns and keeps Best, Safe and the best switch on each side. "Show N more" unfolds the rest. | `test_plans.py::Plans::test_shows_only_plans_nothing_beats`, `…::Switching::test_caps_hold_and_the_best_switch_is_kept_on_each_side`, M13 |
| SCOUTUI-14 | The turn log: ① Lock in on the cards, ② Playing with independent rows (blur focus, entry on the cards, a slider box over each target), ③ End turn writes the board. §8 and §9 have the details. | M14 |
| SCOUTUI-15 | Megas and items on the server: Mega → stone mapping, item odds and Megas in `/api/dex`, allowed Megas in `/api/team`, an entry's `mega` / `item` / `item_used` in the calc. | `test_scout.py::MegaAndItems::*`, `test_dex_has_items_and_megas`, `test_mega_and_items_round_trip` |
| SCOUTUI-16 | Items and Megas on the board: the item tab, the mini's item chip, the Mega bar (armed, done, blocked), one Mega per side, a flash and an in-place morph. | M15 |
| SCOUTUI-17 | Switching on the cards: a ↔ tab on the left of each card's top edge (Switch at ①, Switched at ②). Pivot moves ask who came in, and that Pokémon takes the later hits on its slot. | M16 |
| **SCOUTUI-18** *(proposed, uncommitted)* | **Bench builds and showing who came in.**<br>• `POST /api/scout` takes `also: {mine: [entries], foes: [entries]}` (who's in the back, not fainted) and returns `also: [{side, name, builds}]`, so a card that switches one in has its stats at once. `also` that isn't that shape is a 400: `also is {"mine": [...], "foes": [...]}`.<br>• Once a switch is set (at ①) or has happened mid-turn (at ②, as of the open row), the card **draws the one coming in**: its sprite, name, HP, item and stats, with fresh stages.<br>• That card can be targeted, but you can't act with it or edit it until End turn.<br>• It has no Mega bar this turn, no move selected, and its turn tag reads "1st · ↔ Charizard out".<br>• The switch tab's tooltip says "Charizard switches to Garchomp". | `test_scout_sends_builds_for_the_back` |

---

## 4. Design tokens

### 4.1 Colours and type

```css
:root {
  /* page */
  --bg:        radial-gradient(circle at 30% 20%, #3a2f5c, #1d1830 70%);
  --panel-bg:  rgba(20,18,42,.85);        /* every panel; 10px radius, 1px border rgba(201,196,255,.25) */
  --panel:     #14122a;                   /* the card plate, the minis, pickers */
  --band:      #1b1a3d;                   /* dark move band, stat cells; also "ink on lime" */
  --ink:       #fff;
  --mute:      #b8b4e0;                   /* secondary text */
  --edge:      #c9c4ff;                   /* lilac borders and links */

  /* sides */
  --me:        #9ed0ff;                   /* your text; blue-violet tint rgba(74,63,214,.16) */
  --foe:       #ffb3bd;                   /* their text, and the error caption; red tint rgba(184,40,63,.16) */
  --foe-band:  linear-gradient(90deg, #b8283f, #e2566a);
  --pill:      linear-gradient(90deg, #4a3fd6, #6a5cf0);   /* your band, every move pill */

  /* accents */
  --lime:      #c8ec3a;  --lime-pale:#f1ff9e;  --lime-deep:#a3d41b;   /* on / selected / do this next */
  --up:        #5fe08a;  --down:#ff7a6b;                              /* stage up / down, heal / damage */
  --hp-ok:     #3fd47a;  --hp-mid:#e0bc2d;  --hp-lo:#ff5d5d;           /* mini HP: >50%, ≤50%, ≤20% */
  --mega-a:    #ff6ad5;  --mega-b:#7af0ff;                            /* Mega pink → cyan */
  --protect:   rgba(90,220,255,.55);

  /* status chips */
  --brn:#e4613e; --par:#e0bc2d /* dark ink */; --psn:#9454cc; --slp:#8a8aa0; --frz:#49c8c9 /* dark ink */;

  font: 600 14px system-ui, sans-serif;   /* weight 600 everywhere; numbers are italic 800 */
}
```

Type rules:

- Names and HP numbers are *italic*.
- Big numbers (HP, PP, stat values) are italic, weight 800.
- Panel headings (`h2`) are 12px uppercase, letter-spaced `.08em`, in `--mute`.

### 4.2 The size unit `--U` / `--u`

Everything on the board is sized in one unit, so the whole board scales together:

- **`--U`** is set on `#board-step`.
- **`--u`** is what each component reads. `.pcard, .pmini { --u: var(--U) }`, and roster minis use `--u: calc(var(--U) * 1.3)`.
- A component used on its own defaults to `--u: 1vh`.

| Thing | Size in `u` |
|---|---|
| Big card | 72 wide. The top is 8.4 tall. A move pill is 6 tall, with 0.8 gaps. An empty slot is 37.2 tall. |
| Room above the cards for tabs | 2.7 (`padding-top` on `.cards`) |
| Mini | 26 wide (in the board roster). Its sprite is a 4.4 circle. Six minis stacked are about one card tall. |
| Folder tabs (item, ↔) | 2.7 tall, inset 2 from the card's corner |

**The board is fitted by measuring, not by a formula** (decision 025):

```js
// Lay the board out at 10px, measure, then scale so the two side panels fill the left 3/4
// or the height that's left, whichever runs out first. Refit on every resize.
function fitBoard() {
  const step = document.getElementById("board-step"), sides = step.querySelector(".sides");
  step.style.setProperty("--U", "10px");
  const panels = [...sides.children].map((p) => p.getBoundingClientRect());
  const w = Math.max(...panels.map((r) => r.width)), h = panels.at(-1).bottom - panels[0].top;
  const room = innerHeight - 16 - (panels[0].top + scrollY);
  step.style.setProperty("--U", `${(10 * Math.min(sides.clientWidth / w, room / h)).toFixed(2)}px`);
}
addEventListener("resize", fitBoard);
```

Step 1 doesn't use this. It sizes `--U` from a formula on the viewport: `min(calc((100vw - 404px) / 179.6), calc((100vh - 170px) / 77))`.

---

## 5. Page skeleton

One HTML page holds all three steps. The current step is a class on `<body>`, and the other sections are hidden.

```html
<body class="step-team">            <!-- step-team | step-board | step-plans -->
<header>
  <h1>Card solver</h1>
  <span class="seg"><button id="to-team">1 · Their team</button><button id="to-board">2 · Board</button><button id="to-plans">3 · Plans</button></span>
  <button class="plain" id="newgame">New game</button>
  <span class="grow"></span>
  <a href="/cards/test">card test page</a>
</header>
<div id="caption"></div>          <!-- errors and prompts, pink; takes no space when empty -->

<section id="team-step">
  <div class="rosters">
    <h3>Their team <small>from team preview · Tab or Enter for the next</small><button class="plain" id="clear-foes">Clear all</button></h3>
    <div class="list" id="foe-inputs"></div>        <!-- 6 minis whose name band is an <input> -->
    <h3>Your team <small>click the 4 you bring, in order: 1–2 lead, 3–4 back</small></h3>
    <div class="list" id="mine-list"></div>         <!-- .pick-row: .slotnum · .pmini · .role -->
    <div class="go"><button class="plain" id="start">Board →</button><span class="sum" id="bring-sum"></span></div>
  </div>
</section>

<section id="board-step">
  <div class="ctl"><span class="lbl">Conditions</span><span id="conditions" style="display:contents"></span></div>
  <div id="board">                                   <!-- grid: 3fr | 1fr -->
    <div class="sides">
      <div class="row-panel foe"><div class="side"><h3>Their team</h3><div class="list" id="roster-p2"></div></div><div class="cards" id="foes"></div></div>
      <div class="row-panel mine"><div class="side"><h3>Your team</h3><div class="list" id="roster-p1"></div></div><div class="cards" id="mine"></div></div>
    </div>
    <aside>
      <div class="panel" id="turn"></div>          <!-- the Log -->
      <div class="panel speed"><h2>Speed <small id="speed-sub"></small></h2><ol id="speed"></ol><div id="after"></div></div>
      <div class="panel"><h2>Watch out</h2><div id="threats"></div></div>
    </aside>
  </div>
</section>

<section id="plans-step">
  <div class="ctl"><span class="lbl">…one paragraph explaining rows, columns, the score and the caps…</span></div>
  <div class="ctl"><span class="lbl">Their switching</span><span id="switch-chip" style="display:contents"></span></div>
  <div class="ctl" id="plans-status"></div>
  <div id="plans"></div>
</section>
<!-- load order matters: card primitives, then foe moves, plans, turn, and the app last -->
<script src="/cards/pokemon-card.js"></script><script src="/cards/move-slots.js"></script>
<script src="/cards/plans.js"></script><script src="/cards/turn.js"></script><script src="/cards/solver.js"></script>
</body>
```

```css
body { margin:0; padding:16px; min-height:100vh; box-sizing:border-box; background:var(--bg); color:#fff; font:600 14px system-ui, sans-serif; }
body:not(.step-team) #team-step, body:not(.step-board) #board-step, body:not(.step-plans) #plans-step { display:none; }
header { display:flex; align-items:center; gap:12px; margin-bottom:12px; }
header h1 { margin:0; font-size:18px; font-style:italic; }
#caption { margin-bottom:10px; padding:8px 12px; border-radius:10px; background:rgba(20,18,42,.85); color:#ffb3bd; font-weight:500; }
#caption:empty { display:none; }

#board { display:grid; grid-template-columns:minmax(0,3fr) minmax(0,1fr); gap:16px; align-items:start; }
#board .sides { display:flex; flex-direction:column; align-items:flex-start; gap:calc(var(--U)*2); }
.row-panel { display:flex; align-items:flex-start; gap:calc(var(--U)*1.6); padding:calc(var(--U)*1.4); border-radius:calc(var(--U)*1.6); }
.row-panel.foe  { background:rgba(184,40,63,.16); border:2px solid rgba(255,179,189,.5); }
.row-panel.mine { background:rgba(74,63,214,.16); border:2px solid rgba(201,196,255,.5); }
.row-panel .side { background:rgba(255,255,255,.05); border-radius:calc(var(--U)*1); padding:calc(var(--U)*1); }   /* the "soft seam" */
.row-panel .pmini { --u:calc(var(--U)*1.3); width:calc(var(--u)*26); }
#board .cards { display:flex; gap:calc(var(--U)*1.2); padding-top:calc(var(--U)*2.7); }   /* room for the folder tabs */
aside { display:flex; flex-direction:column; gap:12px; min-width:0; }
.panel { background:rgba(20,18,42,.85); border:1px solid rgba(201,196,255,.25); border-radius:10px; padding:10px 12px; }
.panel h2 { margin:0 0 8px; font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:#b8b4e0; }
```

---

## 6. Components

The CSS below is trimmed to the rules that make the look: colours, shapes, sizes in `u`, states and keyframes. Hover outlines and cursors are mostly left out; see the real files for those. JS helpers are named where the behaviour isn't obvious.

### 6.1 Chips, the segmented switch, buttons, menus and autocomplete

```css
.chip { background:rgba(74,63,214,.25); color:#b8b4e0; border:1px solid rgba(201,196,255,.35); border-radius:999px; padding:4px 12px; cursor:pointer; font:inherit; }
.chip.on      { background:#c8ec3a; border-color:#f1ff9e; color:#1b1a3d; }   /* lit = on */
.chip.assumed { border-style:dashed; }                                        /* not set by you */
.chip small   { font-weight:500; opacity:.8; margin-left:6px; }               /* the one-line reason */

.seg { display:inline-flex; border:1px solid rgba(201,196,255,.35); border-radius:999px; overflow:hidden; }
.seg button { background:transparent; color:#b8b4e0; border:0; padding:5px 14px; font:inherit; }
.seg button.on { background:#c8ec3a; color:#1b1a3d; }
.seg button:disabled { opacity:.4; }

button.plain { background:#4a3fd6; color:#fff; border:1px solid #c9c4ff; border-radius:6px; padding:5px 12px; font:inherit; }
button.go    { background:#c8ec3a; color:#1b1a3d; border-color:#f1ff9e; }   /* the lime "do this next" button */
button.linkish { background:none; border:0; padding:0; color:#c9c4ff; font-size:12px; font-weight:500; text-decoration:underline; }

/* the sprite picker, item menu and Mega menu share one floating box */
.picker { position:absolute; z-index:10; display:flex; flex-direction:column; gap:4px; padding:8px; min-width:200px;
          background:#14122a; border:2px solid #c9c4ff; border-radius:10px; box-shadow:0 8px 24px rgba(0,0,0,.5); }
.picker button { text-align:left; background:#2a2850; color:#fff; border:1px solid transparent; border-radius:6px; padding:4px 8px; }
.picker button:disabled { opacity:.35; }                 /* "(in)", "(fainted)" … are greyed, not hidden */
.picker.menu button.on { background:#c8ec3a; color:#1b1a3d; }
.picker .ttl { font-weight:800; } .picker .desc { color:#b8b4e0; font-weight:500; }

/* autocomplete: from the 2nd letter, up to 8 matches */
.acwrap { position:relative; display:inline-block; }
.ac { position:absolute; z-index:20; left:0; top:calc(100% + 2px); min-width:max(100%,200px); padding:3px; border-radius:7px;
      background:#15162e; border:1px solid #44446b; box-shadow:0 6px 20px #000a; }
.ac .opt { display:flex; justify-content:space-between; gap:12px; padding:3px 8px; border-radius:5px; white-space:nowrap; font-size:13px; }
.ac .opt.on, .ac .opt:hover { background:#c6f03a; color:#1c1c1a; }
```

Autocomplete ranking:

1. labels that **start with** what's typed;
2. then labels with a **word that starts with** it;
3. then labels that **contain** it.

Keys: ↑ ↓ move the highlight, Enter or Tab picks, Esc closes. Any click outside, or Esc, closes any picker or menu.

### 6.2 The big card `.pcard`

```html
<div class="pcard [opp] [foe] [fainted] [protected] [mega] [t-acting|t-target|t-hit] [t-switch]">
  <div class="swtab [on|ask]">↔ Switch</div>                       <!-- left folder tab (6.4) -->
  <div class="itab [known|guess|used|none]"><span class="it guess">Charizardite Y?</span><small>96%</small></div>  <!-- right folder tab -->
  <div class="turntag">2nd · Iron Head</div>                         <!-- only while a turn is played -->
  <div class="top">                                                   <!-- 8.4u tall -->
    <div class="np">                                                  <!-- the HP plate, 56% wide -->
      <div class="sprite"><img src="/sprites/charizard.png"></div>
      <div class="body">
        <div class="banner"><span class="name">Charizard</span><span class="status brn">BRN</span>
          <span class="types"><img class="ti" src="/icons/fire.png"><img class="ti" src="/icons/flying.png"></span></div>
        <div class="hp"><div class="bar"><i style="width:65%"></i></div><span class="lbl"><b>120</b><small>/185</small></span></div>
      </div>
    </div>
    <div class="stages">                                              <!-- 5 cells: Atk Def SpA SpD Spe -->
      <div class="stat up"><span class="nm">Spe<span class="tag">+1</span></span><b class="val">228</b>
        <!-- theirs only: -->
        <svg class="curve" viewBox="0 0 100 24" preserveAspectRatio="none">
          <path class="ghost"/><path class="area"/><path class="line"/><line class="zero"/><line class="mode"/><line class="base"/></svg>
        <span class="rng">130–152</span></div>
    </div>
  </div>
  <div class="megabar [armed|done|blocked]"><span class="ring"></span><span>Mega Evolve</span><small>lock in with your moves</small></div>
  <div class="moves">                                                 <!-- yours: 4 rows; theirs (.opp): 2×4 grid -->
    <div class="move [sel] [empty] [ghost] [dim]" data-key="heatwave">
      <div class="pill"><div class="badge"><img class="ti" src="/icons/fire.png"></div><div class="band">Heat Wave</div>
        <div class="pp"><b>9</b><small>/10</small></div></div></div>       <!-- theirs unseen: <b>62</b><small>%</small> -->
    <div class="other"><input placeholder="+ other move…" list="learnset-…"><datalist id="learnset-…"></datalist></div>  <!-- theirs, 8th cell -->
  </div>
</div>
```

```css
.pcard { --u:1vh; position:relative; box-sizing:border-box; width:calc(var(--u)*72); padding:calc(var(--u)*.8) calc(var(--u)*1.2);
         border-radius:calc(var(--u)*1.4); background:rgba(20,18,42,.55); border:2px solid rgba(201,196,255,.25);
         font:600 calc(var(--u)*1.5)/1.2 system-ui, sans-serif; transition:filter .6s, opacity .6s, transform .6s; }
.pcard .top { position:relative; display:flex; gap:calc(var(--u)*.6); height:calc(var(--u)*8.4); }

/* HP plate: sprite | (slanted name band over a stepped lighter stripe holding the bar and the big number) */
.pcard .np { flex:0 0 56%; min-width:0; display:flex; overflow:hidden; background:#14122a; border:2px solid #c9c4ff; border-radius:calc(var(--u)*1.4); }
.pcard .sprite { width:calc(var(--u)*8.5); flex-shrink:0; display:flex; align-items:center; justify-content:center; overflow:hidden; }
.pcard .sprite img { width:120%; height:120%; object-fit:contain; }
.pcard .np .body { flex:1; min-width:0; display:flex; flex-direction:column; }
.pcard .banner { height:48%; display:flex; align-items:center; gap:calc(var(--u)*.6); padding:0 calc(var(--u)*1.2) 0 calc(var(--u)*2.6);
                 margin-left:calc(var(--u)*-.8); background:linear-gradient(90deg,#4a3fd6,#6a5cf0);
                 clip-path:polygon(calc(var(--u)*1.6) 0, 100% 0, 100% 100%, 0 100%); }
.pcard .banner .name { font-size:calc(var(--u)*1.8); font-style:italic; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.pcard .banner .types { display:flex; gap:calc(var(--u)*.3); margin-left:auto; }
.pcard .hp { flex:1; display:flex; align-items:center; gap:calc(var(--u)*1); padding:0 calc(var(--u)*1.2) 0 calc(var(--u)*3.4);
             background:linear-gradient(90deg, rgba(106,92,240,.35), rgba(106,92,240,.12));
             clip-path:polygon(calc(var(--u)*2.4) 0, 100% 0, 100% 100%, calc(var(--u)*1.2) 100%); }
.pcard .bar { position:relative; flex:1; height:calc(var(--u)*1.2); background:#2a2850; clip-path:polygon(calc(var(--u)*.8) 0, 100% 0, 100% 100%, 0 100%); }
.pcard .bar i { display:block; height:100%; background:linear-gradient(90deg,#e9e23a,#8ae03a); transition:width .6s ease; }
.pcard .hp .lbl { font-style:italic; font-weight:800; font-size:calc(var(--u)*2.4); line-height:1; white-space:nowrap; }
.pcard .hp .lbl small { font-size:calc(var(--u)*1.4); opacity:.85; }

/* stat cells */
.pcard .stages { flex:1; min-width:0; display:grid; grid-template-columns:repeat(5,1fr); gap:calc(var(--u)*.3); }
.pcard .stat { display:flex; flex-direction:column; justify-content:center; text-align:center; color:#b8b4e0; background:#1b1a3d;
               border-radius:calc(var(--u)*.5); padding:calc(var(--u)*.2); }
.pcard .stat .nm  { font-size:calc(var(--u)*.95); font-weight:800; letter-spacing:.03em; }
.pcard .stat .val { font-size:calc(var(--u)*1.5); font-style:italic; color:#fff; }
.pcard:not(.opp) .stat .val { font-size:calc(var(--u)*2); }              /* yours have no curve, so a bigger number */
.pcard .stat.up :is(.val,.tag) { color:#5fe08a; } .pcard .stat.down :is(.val,.tag) { color:#ff7a6b; }
.pcard .stat .rng { font-size:calc(var(--u)*.95); font-weight:700; color:#fff; opacity:.85; }
.pcard .curve { display:block; width:100%; height:calc(var(--u)*1.6); overflow:visible; }
.pcard .curve * { vector-effect:non-scaling-stroke; }
.pcard .curve .area  { fill:rgba(226,86,106,.45); }
.pcard .curve .line  { fill:none; stroke:#ffb3bd; stroke-width:1.5; }
.pcard .curve .ghost { fill:none; stroke:rgba(255,179,189,.4); stroke-dasharray:2 2; }   /* every build, ignoring clues */
.pcard .curve .mode  { stroke:#fff; stroke-width:1.5; }                                /* the likeliest value */
.pcard .curve .zero  { stroke:rgba(255,255,255,.45); stroke-dasharray:2 2; }           /* where it'd be with no stage */
.pcard .curve .base  { stroke:rgba(201,196,255,.35); }

/* moves: purple pill · round type badge · dark band slanted on the right · big italic PP */
.pcard .moves { margin-top:calc(var(--u)*.8); display:flex; flex-direction:column; gap:calc(var(--u)*.8); }
.pcard .move { position:relative; }
.pcard .pill { display:flex; align-items:center; height:calc(var(--u)*6); padding-left:calc(var(--u)*.5); border-radius:calc(var(--u)*3);
               background:linear-gradient(90deg,#4a3fd6,#6a5cf0); border:2px solid #c9c4ff; }
.pcard .badge { width:calc(var(--u)*4.4); height:calc(var(--u)*4.2); border-radius:calc(var(--u)*2.1); background:rgba(255,255,255,.18);
                display:flex; align-items:center; justify-content:center; }
.pcard .band { flex:1; height:calc(var(--u)*4.2); margin-left:calc(var(--u)*.6); display:flex; align-items:center; padding-left:calc(var(--u)*1.2);
               background:#1b1a3d; clip-path:polygon(0 0, 100% 0, calc(100% - var(--u)*1.5) 100%, 0 100%); font-size:calc(var(--u)*2.2); }
.pcard .pp { width:calc(var(--u)*6.5); text-align:right; padding-right:calc(var(--u)*1.4); font-style:italic; font-weight:800; line-height:1; }
.pcard .pp b { font-size:calc(var(--u)*2.6); } .pcard .pp small { display:block; font-size:calc(var(--u)*1.2); }
.pcard .move.sel .pill { background:linear-gradient(90deg,#c8ec3a,#a3d41b); border-color:#f1ff9e; box-shadow:0 0 calc(var(--u)*1) rgba(200,236,58,.5); }
.pcard .move.sel .pp { color:#1b1a3d; }
.pcard .move.sel::before { content:""; position:absolute; left:calc(var(--u)*-1.7); top:calc(var(--u)*2.1);   /* the yellow arrow */
                           border:calc(var(--u)*.9) solid transparent; border-left:calc(var(--u)*1.3) solid #f4e22a; border-right:0; }
.pcard .move.empty .pp b { color:#ff7a6b; }                                                 /* PP 0 */

/* theirs: a 2×4 grid; seen = solid, likely-but-unseen = dashed ghost with usage %, the 8th is a text box */
.pcard.opp .moves { display:grid; grid-template-columns:1fr 1fr; gap:calc(var(--u)*.8) calc(var(--u)*.9); }
.pcard .move.ghost .pill { background:rgba(74,63,214,.22); border-style:dashed; border-color:rgba(201,196,255,.55); }
.pcard .move.ghost .band { background:rgba(27,26,61,.55); color:#b8b4e0; }
.pcard .move.dim { opacity:.35; }                                                            /* 4 seen: moveset complete */
.pcard .other { display:flex; align-items:center; height:calc(var(--u)*6); padding:0 calc(var(--u)*1.8); border-radius:calc(var(--u)*3);
                border:2px dashed rgba(201,196,255,.55); font-size:calc(var(--u)*2); }

/* their side: red band and plate edge; the move pills stay purple */
.pcard.foe { border-color:rgba(255,140,155,.3); }
.pcard.foe .banner { background:linear-gradient(90deg,#b8283f,#e2566a); }
.pcard.foe .np { border-color:#ffb3bd; }
.pcard.foe .hp { background:linear-gradient(90deg, rgba(226,86,106,.35), rgba(226,86,106,.12)); }

/* status chip in the banner */
.pcard .banner .status { font-size:calc(var(--u)*1.1); font-weight:800; letter-spacing:.05em; padding:calc(var(--u)*.1) calc(var(--u)*.5); border-radius:calc(var(--u)*.4); }
.status.brn { background:#e4613e; } .status.par { background:#e0bc2d; color:#1b1a3d; } .status.psn { background:#9454cc; }
.status.slp { background:#8a8aa0; } .status.frz { background:#49c8c9; color:#1b1a3d; }

/* an empty slot: exactly a card's size */
.pcard.slot-empty { height:calc(var(--u)*37.2); display:flex; align-items:center; justify-content:center; border-style:dashed; color:#b8b4e0; font-size:calc(var(--u)*1.8); }
.pcard.loading { opacity:.6; }
.pcard.drop-ok { outline:3px dashed #c8ec3a; outline-offset:4px; }      /* a roster drag hovering a valid card */
```

**What the card shows:**

- **HP number:** yours read "120/185". Theirs read "100%", because that's all the game tells you.
- **Stat values:** each value has the stage applied. The page works this out per build itself: `floor(stat × m)`, with `m = (2+s)/2` for s ≥ 0, else `2/(2−s)`.
- **The likelihood curve** (theirs only):
  - one Gaussian bump per build, weighted by its share (σ = 3% of the axis), sampled at 48 points;
  - the axis runs from 0.6 × the lowest build to 1.6 × the highest, and is fixed when the card is made, so a stage visibly slides the curve;
  - it tweens over 600ms with `requestAnimationFrame` (SVG paths can't be CSS-transitioned everywhere);
  - the tooltip lists every build: "value · share% · label".
- **Their move grid:** the moves seen so far come first, in the order seen, solid with "PP". The likeliest unseen moves fill the rest up to 7, dashed with their usage %. The 8th cell is "+ other move…", which autocompletes from the learnset; a move it can't learn shakes the box. When the list changes, a FLIP pass slides each pill from its old place to its new one (260ms). Pills are matched by `data-key`.

### 6.3 The mini `.pmini`

```html
<div class="pmini [foe] [active] [out] [unknown] [fainted] [mega]" draggable="true">
  <div class="spr"><img src="/sprites/garchomp.png"><span class="key [armed|done]">M</span></div>
  <div class="panel">
    <div class="ban"><span class="nm">Garchomp</span><span class="status par">PAR</span>
      <span class="tys"><img class="ti" …></span><span class="itm it guess">Choice Scarf?</span><span class="hpv">142<small>/183</small></span></div>
    <div class="bar"><i class="[mid|lo]" style="width:78%"></i></div>
  </div>
</div>
```

```css
.pmini { --u:1vh; position:relative; display:flex; align-items:center; width:calc(var(--u)*32); font:600 calc(var(--u)*1.35)/1.2 system-ui, sans-serif;
         transition:filter .6s, opacity .6s; }
.pmini .spr { flex-shrink:0; width:calc(var(--u)*4.4); height:calc(var(--u)*4.4); margin-right:calc(var(--u)*-1.8); position:relative; z-index:1;
              border-radius:50%; overflow:hidden; background:#14122a; border:2px solid #c9c4ff; }          /* round sprite overlapping the band */
.pmini .panel { flex:1; min-width:0; overflow:hidden; background:#14122a; border:2px solid #c9c4ff; border-radius:0 calc(var(--u)*1.2) calc(var(--u)*1.2) 0; }
.pmini .ban { display:flex; align-items:center; gap:calc(var(--u)*.5); padding:calc(var(--u)*.35) calc(var(--u)*.9) calc(var(--u)*.35) calc(var(--u)*2.4);
              background:linear-gradient(90deg,#4a3fd6,#6a5cf0); }
.pmini .nm  { font-style:italic; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.pmini .hpv { margin-left:auto; font-size:calc(var(--u)*1.2); font-style:italic; font-weight:800; }
.pmini .bar { height:calc(var(--u)*.55); margin-left:calc(var(--u)*1.6); background:#2a2850; overflow:hidden; }
.pmini .bar i { display:block; height:100%; background:#3fd47a; transition:width .6s ease, background .4s; }
.pmini .bar i.mid { background:#e0bc2d; } .pmini .bar i.lo { background:#ff5d5d; }       /* ≤50%, ≤20% */
.pmini.foe :is(.spr,.panel) { border-color:#ffb3bd; } .pmini.foe .ban { background:linear-gradient(90deg,#b8283f,#e2566a); }
.pmini.active :is(.spr,.panel) { border-color:#c8ec3a; box-shadow:0 0 calc(var(--u)*.8) rgba(200,236,58,.45); }   /* on the field */
.pmini.fainted { filter:grayscale(1) brightness(.65); opacity:.6; }
.pmini.out { opacity:.3; }                                                                /* not brought (step 1) */
.pmini.unknown .ban { background:rgba(226,86,106,.25); }                                  /* a foe not yet seen in battle: "?" */
.pmini.unknown .bar i { background:repeating-linear-gradient(90deg,#5a4560 0 6px,transparent 6px 10px); }
.pmini .itm { max-width:40%; padding:0 calc(var(--u)*.5); border-radius:calc(var(--u)*.45); background:#24214a; border:1.5px solid rgba(201,196,255,.55);
              font-size:calc(var(--u)*.9); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.pmini.foe .itm { background:#3a1a2c; border-color:rgba(255,179,189,.6); }
.pmini .key { position:absolute; z-index:2; left:calc(var(--u)*-.3); bottom:calc(var(--u)*-.3); width:calc(var(--u)*1.7); height:calc(var(--u)*1.7);
              border-radius:50%; border:1.5px solid #ff6ad5; background:#14122a; color:#ff6ad5; font:900 calc(var(--u)*.85)/1 system-ui; display:flex; align-items:center; justify-content:center; }
.pmini .key.armed { background:linear-gradient(135deg,#ff6ad5,#7af0ff); color:#fff; animation:miniArmed 1.4s ease-in-out infinite; }
.pmini .key.done  { background:linear-gradient(135deg,#ff6ad5,#7af0ff); color:#1b1a3d; border-color:#fff; }
@keyframes miniArmed { 50% { box-shadow:0 0 calc(var(--u)*1) rgba(255,106,213,.95); } }
```

Foe HP on a mini is a %, and at least 1% while alive.

On step 1, the foe minis hide `.hpv` and `.bar`, and the name band becomes an `<input>` (italic, transparent). An empty mini is dashed, with a "?" sprite and the placeholder "Pokémon N". A name that doesn't match gets `text-decoration: underline wavy #ff5d5d`.

Your picks on step 1 are rows of `.slotnum · .pmini · .role`:

- `.slotnum.lead` is a lime circle with dark ink, `.slotnum.back` a sky-blue `#9ed0ff` one;
- an unpicked slot is a dashed empty circle;
- `.role` reads "Lead" (lime) or "Back" (sky).

### 6.4 Folder tabs: item (right) and ↔ switch (left)

Both sit on the card's top edge, `position:absolute; bottom:100%`, 2.7u tall, with no bottom border, inset 2u from their corner. They must never overlap.

```css
.pcard .itab  { position:absolute; right:calc(var(--u)*2); bottom:100%; max-width:50%; display:flex; align-items:center; gap:calc(var(--u)*.6);
                height:calc(var(--u)*2.7); padding:0 calc(var(--u)*1.1); border:2px solid rgba(201,196,255,.55); border-bottom:0;
                border-radius:calc(var(--u)*.9) calc(var(--u)*.9) 0 0; background:#24214a; font-size:calc(var(--u)*1.35); }
.pcard.foe .itab { border-color:rgba(255,179,189,.6); background:#3a1a2c; }
.pcard .itab.guess { border-style:dashed; }
.it.guess { opacity:.6; font-style:italic; } .it.used { text-decoration:line-through; opacity:.55; } .it.none { opacity:.45; }

.pcard .swtab { position:absolute; z-index:3; left:calc(var(--u)*2); bottom:100%; display:flex; align-items:center; gap:calc(var(--u)*.6);
                height:calc(var(--u)*2.7); padding:0 calc(var(--u)*1.1); border:2px solid rgba(158,208,255,.7); border-bottom:0;
                border-radius:calc(var(--u)*.9) calc(var(--u)*.9) 0 0; background:#1c2a4a; color:#9ed0ff; font:700 calc(var(--u)*1.35) system-ui; white-space:nowrap; }
.pcard.foe .swtab { background:#2a1f3e; }
.pcard .swtab.on  { background:#9ed0ff; color:#1b1a3d; border-color:#d6ecff; }    /* a switch is set */
.pcard .swtab.ask { background:#f1ff9e; color:#1b1a3d; border-color:#f1ff9e; }    /* "U-turn ↔ who came in?" */
.pcard.t-switch .moves { opacity:.3; }                                            /* the moves step back while a switch is the action */
```

| Item tab state | Text |
|---|---|
| known | "Leftovers" (solid) |
| guess (theirs, not seen) | "Charizardite Y?" with a small "96%" (dim, italic, dashed) |
| used | "Sitrus Berry" struck through, with "used" |
| none | dim "no item" |

### 6.5 The Mega bar

It sits above the moves, as on the in-game move screen.

```css
.pcard .megabar { margin-top:calc(var(--u)*.8); display:flex; align-items:center; gap:calc(var(--u)*1); height:calc(var(--u)*3.6); padding:0 calc(var(--u)*1.4);
                  border-radius:calc(var(--u)*1.8); border:2px solid #ff6ad5; background:rgba(255,106,213,.08); color:#ffd6f3; font-size:calc(var(--u)*1.6); font-style:italic; }
.pcard .megabar .ring { width:calc(var(--u)*2.2); height:calc(var(--u)*2.2); border-radius:50%; border:2px solid #ff6ad5; }
.pcard .megabar small { margin-left:auto; color:#b8b4e0; font-style:normal; font-weight:500; font-size:calc(var(--u)*1.2); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.pcard .megabar.armed { background:linear-gradient(90deg, rgba(255,106,213,.45), rgba(122,240,255,.35)); color:#fff; animation:megaArmed 1.4s ease-in-out infinite; }
.pcard .megabar.armed .ring { background:linear-gradient(135deg,#ff6ad5,#7af0ff); border-color:#fff; }
.pcard .megabar.done { background:linear-gradient(90deg,#ff6ad5,#7af0ff); color:#1b1a3d; border-color:#fff; }
.pcard .megabar.blocked { border-color:#6a6890; color:#6a6890; background:transparent; cursor:help; }
.pcard.foe .megabar:not(.done) { border-style:dashed; }
.pcard.mega .np { border-color:#ff6ad5; box-shadow:0 0 calc(var(--u)*1.2) rgba(255,106,213,.55); }
@keyframes megaArmed { 50% { box-shadow:0 0 calc(var(--u)*1.6) rgba(255,106,213,.85); } }
```

| State | Label · note |
|---|---|
| yours, can | "Mega Evolve" · "lock in with your moves" (outside ①: "it did this turn? click") |
| yours, armed | "Mega Evolve ✓" · "as the turn starts · calcs and Speed are the Mega's" |
| theirs, can (dashed) | "They Mega Evolved…" · "Y 96% · X 3%" |
| done | "Mega Charizard Y" · its ability |
| blocked | "Mega Evolve" · the reason: "Garchomp already Mega Evolved: one Mega per side per battle", "holding Leftovers, not its Mega Stone", "its Charizardite Y is gone" |

### 6.6 Animations

All of these are `transform`, `opacity`, `filter` or `box-shadow`, so the layout never moves (U1). Every one except the Mega has a button on `/cards/test`.

| Change | How | CSS / JS |
|---|---|---|
| HP | The bar glides 600ms. The number counts along with it (eased cubic, `requestAnimationFrame`). "−17" (red) or "+20" (green) floats up off the plate and fades. A hit shakes the sprite. | `.bar i { transition:width .6s }`; `.dmgpop` is appended to `.top`, *not* to the plate, whose clip-paths would cut it off |
| Stage | The value pulses. | `@keyframes pcardPulse { 0% { transform:scale(1.5) } 100% { transform:scale(1) } }`, .5s |
| Status | The chip pops in. | `@keyframes pcardPop { 0% { scale(0) } 70% { scale(1.2) } 100% { scale(1) } }`, .35s |
| Faint | The card greys and sinks 1u. | `.pcard.fainted { filter:grayscale(1) brightness(.6); opacity:.6; transform:translateY(calc(var(--u)*1)) }` |
| Protect | A cyan flash, then a steady pulsing shield until the end of the turn. | `::after` with `pcardShield` .9s, then `::before` with `pcardShieldHold` 2s infinite |
| Switch | The old card slides down 12% and fades (300ms ease-in), and the new one slides up in (300ms ease-out). | Web Animations API `swapCard(old, fresh)` |
| Mega | The card flashes white-pink, and its sprite, name, types and stats change in place. | `.megaflash::after` .9s; `morphCard()` |
| Seen move | Their grid slides the pills into their new places. | the FLIP pass, 260ms |

A shared `replay(node, cls)` helper removes the class, forces a reflow (`void node.offsetWidth`), then adds it back, so an animation can run again.

```css
@keyframes pcardHit { 0%,100% { transform:translateX(0) } 20% { transform:translateX(calc(var(--u)*-.6)) } 40% { transform:translateX(calc(var(--u)*.6)) }
                      60% { transform:translateX(calc(var(--u)*-.4)) } 80% { transform:translateX(calc(var(--u)*.4)) } }
.pcard .dmgpop { position:absolute; right:calc(44% + var(--u)*1.4); top:calc(var(--u)*-.5); color:#ff7a6b; font-style:italic; font-weight:800;
                 font-size:calc(var(--u)*2); pointer-events:none; animation:pcardDmgPop 1s ease forwards; }
@keyframes pcardDmgPop { 0% { opacity:1; transform:translateY(0) } 100% { opacity:0; transform:translateY(calc(var(--u)*-3)) } }
.pcard::before { content:""; position:absolute; inset:-2px; border-radius:inherit; pointer-events:none; opacity:0; border:2px solid rgba(120,230,255,.9);
                 box-shadow:0 0 calc(var(--u)*1.5) rgba(90,220,255,.55), inset 0 0 calc(var(--u)*1.5) rgba(90,220,255,.25); transition:opacity .4s; }
.pcard.protected::before { opacity:1; animation:pcardShieldHold 2s ease-in-out infinite; }
```

### 6.7 Speed and Watch out

```html
<div class="panel speed"><h2>Speed <small>fastest first</small></h2>
  <ol><li class="foe">Pelipper <span class="v">68–86</span></li><li class="me">Charizard <span class="v">152</span></li></ol>
  <div class="after">after Pelipper's Tailwind: Pelipper › Charizard › …</div></div>
<div class="panel"><h2>Watch out</h2>
  <div class="threat"><div class="who foe">Garchomp's Earthquake</div>
    <div class="tgt"><span class="me">→ Charizard</span><span>82–97% · <span class="ko big">OHKO likely</span></span></div>
    <div class="extra">note · goes first (+1)</div></div></div>
```

```css
.me { color:#9ed0ff; } .foe { color:#ffb3bd; }
.speed ol { margin:0; padding-left:22px; display:flex; flex-direction:column; gap:3px; }
.speed li span.v { float:right; font-style:italic; font-weight:800; color:#fff; }
.after { margin-top:8px; color:#b8b4e0; font-weight:500; font-size:13px; }
.threat { padding:6px 0; border-top:1px solid rgba(201,196,255,.15); } .threat:first-of-type { border-top:0; padding-top:0; }
.threat .tgt { display:flex; justify-content:space-between; gap:8px; margin-left:12px; font-weight:500; }
.threat .ko { font-weight:800; } .threat .ko.big { color:#c8ec3a; }      /* lime when the KO is sure or likely */
.threat .extra, .muted { color:#b8b4e0; font-weight:500; font-size:12px; }
```

- **The Speed heading** reads "fastest first", or "slowest first (Trick Room)".
- **Watch out shows only what the server sends** (10%+ OHKO or 40%+ 2HKO).
- **When nothing qualifies,** it reads "Nothing here is likely to OHKO or 2HKO your side."
- **While their side is empty,** it reads "Their leads aren't in yet."

### 6.8 The sprite circle and action line (shared by the Log and Plans)

```html
<span class="pl-act">
  <div class="pl-c [foe-c] [sm] [down] [maybe]"><img src="/sprites/rillaboom.png"><span class="badge"><img class="ti" src="/icons/grass.png"></span></div>
  <b class="mv">Fake Out</b><span class="to">›</span><span class="tgts"><div class="pl-c sm">…</div></span>
</span>
```

```css
.pl-c { --s:26px; width:var(--s); height:var(--s); flex-shrink:0; border-radius:50%; background:#14122a; border:2px solid #c9c4ff; position:relative;
        display:flex; align-items:center; justify-content:center; }
.pl-c.foe-c { border-color:#ffb3bd; } .pl-c.down { filter:grayscale(1) brightness(.5); } .pl-c.maybe { border-style:dashed; }
.pl-c img { width:100%; height:100%; object-fit:contain; border-radius:50%; }
.pl-c .badge { position:absolute; right:-9px; bottom:-5px; width:20px; height:20px; border-radius:50%; background:#14122a; border:1.5px solid #c9c4ff;
               display:flex; align-items:center; justify-content:center; }   /* the move's type, pinned to the attacker */
.pl-act { display:inline-flex; align-items:center; gap:4px; white-space:nowrap; font-size:11px; }
.pl-act > .pl-c:first-child { margin-right:6px; }
.pl-act .to { color:#c9c4ff; font-weight:800; font-size:13px; }
```

### 6.9 The Log panel (`#turn`)

From top to bottom:

1. a heading with "turn N now";
2. the stepper, **① Lock in · ② Playing · ③ End of turn**;
3. a big prompt line (`.ask.big`);
4. the live rows;
5. a footer with Lock in → or End turn →;
6. "Earlier turns", as `<details>`.

```css
#turn .stepper { display:flex; gap:4px; margin-bottom:10px; }
#turn .stepper .stp { flex:1; text-align:center; padding:3px 6px; border-radius:6px; font-size:12px; background:rgba(201,196,255,.1); color:#b8b4e0; }
#turn .stepper .stp.on { background:#c8ec3a; color:#1b1a3d; font-weight:800; } #turn .stepper .stp.past { color:#fff; }
#turn .ask, .pcard .ask { color:#f1ff9e; }
#turn .ask.big { font-size:14px; margin:2px 0 6px; color:#fff; min-height:1.3em; }     /* min-height: no jump when the prompt empties */

/* a live row reads like a Plans action: (attacker + type) Move › (targets), a muted result line under it */
.trow.live { display:flex; align-items:center; gap:8px; padding:7px 8px; border-radius:8px; border:1px solid rgba(201,196,255,.12); cursor:pointer; }
.trow.live.sel  { border-color:#c8ec3a; background:rgba(200,236,58,.1); }
.trow.live.fin  { background:rgba(63,212,122,.06); }
.trow.live.skip .mv { text-decoration:line-through; opacity:.6; }
.trow.live .pl-act { font-size:15px; } .trow.live .pl-c.sm { --s:28px; }
.trow.live .sub { color:#b8b4e0; font-size:13px; }            /* "calc 55–77%" waiting · live value · "−17% · calc 14–19%" done */
.trow .st.ok { color:#3fd47a; }                               /* ✓ when the row is done */
#turn .moved { padding:0 5px; border-radius:4px; border:1px dashed #f1ff9e; color:#f1ff9e; font-size:10px; font-weight:800; }   /* "exp. 2nd" */

/* earlier turns: order · why · attacker · move › each target's HP left */
.trow:not(.live) { display:grid; grid-template-columns:12px 34px 62px 1fr; gap:6px; align-items:center; padding:3px 0; }
.trow .grip { color:#6b6890; font-size:11px; letter-spacing:-2px; cursor:grab; }          /* ⋮⋮ */
.trow.dragging { opacity:.35; }
.trow.drop-before { box-shadow:inset 0 2px 0 #f1ff9e; } .trow.drop-after { box-shadow:inset 0 -2px 0 #f1ff9e; }
#turn .ord { min-width:30px; padding:1px 5px; border-radius:5px; background:#2a2850; font-weight:800; font-size:11px; text-align:center; }   /* 1st … 4th */
#turn .why { padding:1px 6px; border-radius:4px; background:#2a2850; color:#d8d4ff; font-weight:700; font-size:11px; }   /* "105 Spe" */
#turn .why.pri { background:#c8ec3a; color:#1b1a3d; }  /* "+3" */      #turn .why.sw { background:#9ed0ff; color:#1b1a3d; }  /* "switch" */
.trow .lnote { grid-column:4; color:#b8b4e0; font-weight:500; font-size:11px; } .trow .lnote b { color:#c8ec3a; }   /* the speed note */
#turn .turnhd::before { content:"▸"; } #turn details[open] > .turnhd::before { content:"▾"; }
#turn .turnhd .cond { font-size:10px; font-weight:800; padding:0 6px; border-radius:999px; background:rgba(201,196,255,.2); }  /* TR / Tailwind / Mega */
```

### 6.10 The cards during a turn: outlines, tag, damage box, actor strip, focus blur

```css
.pcard.t-acting { outline:3px solid #c8ec3a; outline-offset:3px; }                     /* the open row's Pokémon */
.pcard.t-target { outline:3px dashed #f1ff9e; outline-offset:3px; cursor:crosshair; }   /* click to set the target */
.pcard.t-hit    { outline:3px solid #f1ff9e; outline-offset:3px; }                     /* being hit: it gets a .pop */
.pcard.t-moves .move .pill { box-shadow:0 0 0 2px rgba(241,255,158,.55); }             /* their pills glow: "click the move it used" */
.pcard .turntag { position:absolute; z-index:3; top:calc(var(--u)*-1.3); right:calc(var(--u)*1.6); padding:calc(var(--u)*.15) calc(var(--u)*.8);
                  border-radius:999px; background:#14122a; border:1px solid #c8ec3a; font-size:calc(var(--u)*1.25); font-weight:700; pointer-events:none; }

/* the target's own HP bar grows a little and shows the calc's range (stripes) and the HP before (a tick) */
.pcard .bar { transition:height .2s; } .pcard.t-hit .bar { height:calc(var(--u)*2); }
.pcard .bar .cb .roll { position:absolute; top:0; bottom:0; background:repeating-linear-gradient(135deg, rgba(255,255,255,.8) 0 3px, rgba(255,255,255,.15) 3px 6px); }
.pcard .bar .cb .was  { position:absolute; top:0; bottom:0; width:2px; margin-left:-2px; background:#fff; box-shadow:0 0 0 1px #1b1a3d; }

/* the box over a target card */
.pcard .pop { position:absolute; z-index:4; top:calc(var(--u)*10); left:calc(var(--u)*4); right:calc(var(--u)*4); padding:10px 12px; border-radius:10px;
              background:#1d1830; border:2px solid #f1ff9e; box-shadow:0 10px 30px rgba(0,0,0,.6); font:600 13px system-ui; }
.pcard .pop .line { display:grid; grid-template-columns:1fr 84px; gap:10px; align-items:center; }   /* bar | readout */
.pcard .hbar { position:relative; height:16px; border-radius:8px; background:#2a2850; }
.pcard .hbar .was  { border:1px solid rgba(201,196,255,.45); background:rgba(201,196,255,.06); }   /* HP before the hit */
.pcard .hbar .sure { background:#3fd47a; }                                                         /* certainly left */
.pcard .hbar .roll { background:repeating-linear-gradient(135deg,#3fd47a 0 4px,rgba(63,212,122,.25) 4px 8px); }   /* the roll range */
.pcard .hbar input { position:absolute; inset:-6px 0; width:100%; margin:0; appearance:none; background:transparent; }
.pcard .hbar input::-webkit-slider-thumb { -webkit-appearance:none; width:6px; height:26px; border-radius:3px; background:#fff; box-shadow:0 0 0 2px #1b1a3d; }

/* the open row's own card: a strip over its stats for what isn't a move click */
.pcard .astrip { position:absolute; z-index:2; top:0; right:0; bottom:0; width:calc(44% - var(--u)*.6); padding:4px 8px; display:flex; flex-direction:column;
                 justify-content:center; gap:4px; border-radius:calc(var(--u)*.8); background:rgba(20,18,42,.95); border:1px solid #c8ec3a; font:600 12px system-ui; }
.pcard .astrip.sw { border-color:#9ed0ff; }

/* focus: while a row is open, everything but that row and its cards blurs and darkens */
body.focusing :is(#board-step > .ctl, .row-panel .side, #board aside > .panel:not(#turn), #turn > h2, #turn .stepper, #turn .foot,
                  #turn .earlier, #turn details.turn, .trow.live:not(.sel), #board .pcard:not(.t-acting, .t-target, .t-hit)) {
  filter:blur(3px) brightness(.45) saturate(.6);
}
body.focusing .pcard:is(.t-acting, .t-hit) { box-shadow:0 0 0 2px #c8ec3a, 0 0 46px rgba(200,236,58,.35); }
body.focusing .trow.live.sel { background:rgba(200,236,58,.16); box-shadow:0 0 0 2px #c8ec3a, 0 0 26px rgba(200,236,58,.3); }
```

The damage box's markup:

```html
<div class="pop">
  <div class="pt"><b>Heat Wave →</b><span class="foe">Pelipper</span><span class="seg"><button>HP</button><button class="on">%</button></span></div>
  <div class="line"><div class="hbar"><i class="was"></i><i class="sure"></i><i class="roll"></i><input type="range"></div><span class="hchip">62% ✓</span></div>
  <div class="btns"><button class="chip">KO</button><button class="chip">miss</button><span class="grow"></span><button class="plain go">✓ Done</button></div>
</div>
```

- **The HP / % switch** appears only when the target is yours.
- **The readout** compares the value with the calc: ▲ above it, ✓ inside it, ▼ below it. Hover shows the details.
- **A target that Protected** shows "protected itself · no damage" and only ✓ Done.

### 6.11 Plans

```css
.plans table { border-collapse:separate; border-spacing:0; }
.plans th, .plans td { padding:6px 8px; vertical-align:middle; border-bottom:1px solid rgba(201,196,255,.12); text-align:left; }
.plans td.cellx { border-left:1px solid rgba(201,196,255,.08); cursor:pointer; } .plans td.cellx:hover { background:rgba(201,196,255,.08); }
.plans td.overall { border-left:2px solid rgba(201,196,255,.3); }
.plans tr.best td.plan { box-shadow:inset 3px 0 0 #c8ec3a; }
.plans tr.dim td, .plans td.dimc { opacity:.45; }                  /* kept in only as the best switch, or a "show more" plan */
#plans.busy { opacity:.45; }                                       /* recomputing: the old matrix stays in place, dimmed */

/* an end state: theirs on top, yours under */
.pl-st { display:grid; grid-template-columns:auto auto; gap:2px 7px; align-items:center; padding:3px 7px; border-radius:8px; width:max-content;
         background:rgba(20,18,42,.75); border:1px solid rgba(201,196,255,.25); }
.pl-st .cell:nth-child(n+3) { padding-top:2px; border-top:1px solid rgba(201,196,255,.2); }
.pl-st .cell span { font-style:italic; font-weight:800; font-size:11px; min-width:46px; }     /* "KO", "KO 40%", "55–70%" */
.pl-pick { font-size:10px; font-weight:800; padding:1px 7px; border-radius:999px; background:#c8ec3a; color:#1b1a3d; }   /* Best vs likely */
.pl-pick.safe { background:#9ed0ff; }                                                                                   /* Safe pick */
.pl-sw  { font-size:10px; font-weight:800; padding:1px 7px; border-radius:999px; border:1px dashed #9ed0ff; color:#9ed0ff; }  /* ↔ switch */
.pl-sw.foe { border-color:#ffb3bd; color:#ffb3bd; }
.pl-tie { font-size:10px; font-weight:800; padding:1px 7px; border-radius:999px; background:rgba(201,196,255,.2); }       /* "N plans tie" */
.pl-alts .alt { display:inline-flex; align-items:center; gap:3px; padding:1px 7px 1px 2px; border-radius:999px;
                background:rgba(158,208,255,.12); border:1px solid rgba(158,208,255,.35); }   /* tied plans: "A or B" */

/* the full-screen turn */
.pl-modal { position:fixed; inset:0; z-index:50; background:rgba(10,8,24,.8); display:flex; align-items:center; justify-content:center; padding:24px; font:600 15px system-ui; }
.pl-modal .sheet { width:min(1500px,100%); max-height:100%; overflow:auto; padding:18px 22px; border-radius:14px; background:#1d1830; border:1px solid #c9c4ff; box-shadow:0 20px 60px rgba(0,0,0,.6); }
.pl-modal .tabs button.on { background:#c9c4ff; color:#1b1a3d; }                 /* one tab per Speed order */
.pl-modal .row { display:flex; align-items:flex-start; gap:14px; }               /* steps 1st → 4th side by side */
.pl-modal .step { flex:1 1 0; min-width:0; display:flex; flex-direction:column; gap:8px; padding:12px; border-radius:8px; border:1px solid rgba(201,196,255,.18); }
.pl-modal .step.gone { opacity:.55; }
.pl-modal .band { position:relative; height:6px; border-radius:3px; background:#2a2850; } .pl-modal .band i { position:absolute; top:0; bottom:0; background:#3fd47a; }
.pl-modal .chev { color:#c9c4ff; font-size:22px; font-weight:800; }               /* › or ↔ between source and targets */
```

---

## 7. Steps and flow

**The header** holds the title "Card solver", the switch **1 · Their team | 2 · Board | 3 · Plans**, **New game**, and a link to the card test page.

- Steps 2 and 3 stay disabled until their team has at least one Pokémon and your 4 are picked.
- The current step survives a reload, under the same rule.

### Step 1 · Their team

- **Their 6.** Each is a mini whose name band is a text box, with the autocomplete from §6.1. Enter or Tab picks and moves to the next box. After the 6th, focus goes to **Board →**.
  - Leaving a box keeps an exact label or id. Anything else is underlined in wavy red.
  - A duplicate is refused, and the caption reads "Garchomp is already in their 6".
  - × removes one. **Clear all** empties all six and focuses box 1.
- **Your 4.** Your team is read from the team file. Each one is a mini with its item chip, and its tooltip shows the item, the ability and the moves.
  - Click the 4 you bring, in order: 1–2 lime ("Lead", 1 on the left), 3–4 sky ("Back").
  - The line under the list says "N more to pick", or "Lead A + B · back C + D" when all 4 are in.
  - Clicking a numbered one drops it, and the rest renumber. Once 4 are picked, the other 2 dim to 30%.
  - A 5th click is refused: "You're bringing 4 already: click one of them to drop it first."
  - A team of fewer than 4 brings all of them.
  - **The 2 you don't bring are gone from the game:** from your board roster, the picker, the switch and replacement chips, and the Plans bench.

### Step 2 · Board

```
┌ Conditions: [Trick Room] [Tailwind · yours] [Tailwind · theirs] [Weather: rain · Drizzle · auto] [Swift Swim · Pelipper] ┐
├──────────────────────────── left 3/4 ─────────────────────────────┬──────── right 1/4 ────────┤
│ ┌ Their team (red panel) ─────────────────────────────────────┐ │ Log       turn 3 now   │
│ │ roster  │  [ their card A ]   [ their card B ]                │ │ ① Lock in ② Playing ③ … │
│ │ 6 minis │                                                    │ │ rows…                 │
│ └──────────────────────────────────────────────────────────────┘ │ Speed   fastest first  │
│ ┌ Your team (blue panel) ─────────────────────────────────────┐ │ Watch out               │
│ │ roster  │  [ your card A ]    [ your card B ]                 │ │                         │
│ └──────────────────────────────────────────────────────────────┘ │                         │
└──────────────────────────────────────────────────────────────────┴─────────────────────────┘
```

**The conditions bar:**

| Chip | Behaviour |
|---|---|
| Trick Room | On or off. |
| Tailwind · yours | On or off. |
| Tailwind · theirs | On or off. |
| Weather | Shows the weather in force. A click cycles auto → sun → rain → sand → snow → none. Its small text reads "Drizzle · auto" or "set by hand", and it's dashed while only assumed. |
| A speed ability, e.g. "Swift Swim · Pelipper" | One per foe whose speed ability works in the current weather. It's lit and dashed while assumed on; a click turns it off. |

**Opening the board:**

- Your 1 and 2 go into your side if it's empty.
- Their side stays empty, reading "+ who did they lead?", until you pick their leads from the slots. After turn 1 is logged, an empty slot reads "+ pick a Pokémon".
- A slot whose Pokémon is still loading reads "Garchomp…" and is faded.

**While their side is empty:**

- Speed shows only your two.
- Watch out reads "Their leads aren't in yet."
- The caption reads "Pick their leads: click a slot on their side."
- The Log reads "Who did they lead? Click a slot on their side, then pick your moves.", with no Lock in.
- Plans reads "Pick their leads on the Board first."

**The right quarter**, top to bottom: the Log (§8 ①–③), Speed and Watch out (§6.7).

### Step 3 · Plans

- **Columns are their replies.** The header is "You ↓ They →". Each column shows their actions (sprite + type badge, "Move › targets"), "N% likely", and a "↔ they switch" tag, or "their likeliest switch", dimmed when it's there only because it's kept.
- **Rows are your plans.** Tied plans show the shared action, then the other Pokémon's options joined by "or".
- **Each cell is the end state:** their sprites over yours, each with "KO", "KO 40%" or "55–70%". A ring is solid when the Pokémon is certainly down and dashed when it might be. Under that is a verdict: "Garchomp down 60%" or "nobody goes down".
- **The last column:**
  - "you KO 1.2 · they KO 0.3";
  - "HP bars +0.40 · score +1.40";
  - "worst: vs …";
  - tags: **Best vs likely**, **Safe pick**, "↔ switch" / "↔ both switch", "N plans tie", and "beaten by row 2 · −0.30 vs top" or "below the cut".
- **The footer** gives the sample counts, the switch rate, and how many less likely replies are left out but still count.
- **The full-screen turn:**
  - The top line has your actions, "vs", "Them · N% likely", the verdict, and ×.
  - Below it are the steps, 1st to 4th. Each has its reason chip (priority, "switch" or a Speed range), then the source › each target with its HP band. A switch shows "out ↔ in".
  - Notes give the skips ("Kingambit flinches, so no move", "fails 33%") and blocks ("blocked by Arcanine's Protect").
  - It ends with "Next state".
- **While it computes:** the old matrix stays, dimmed to 45% and not moving, with "Playing every plan against their likely replies…".

---

## 8. The action table

"Waits" means the gesture is blocked while a turn is being played (② Playing), and the caption says why.

### Anywhere

| Where | Gesture | What changes |
|---|---|---|
| Header | 1 · 2 · 3 | Changes step. |
| Header | New game | Resets HP, status, stages, seen moves, PP, items, Megas, conditions and the turn log. Keeps their 6, your 4, the step and the switch rate. Your 1 and 2 go back on the field, and their side empties. |
| A picker or menu is open | click outside, or Esc | Closes it. |
| Window | resize | Refits the board. |

### Step 1

| Where | Gesture | What changes |
|---|---|---|
| A foe box | type 2+ letters | Up to 8 suggestions. |
| Suggestions | ↑ ↓, then Enter or Tab | Picks one and focuses the next box (after the 6th, Board →). |
| A foe box | Esc | Closes the suggestions. An emptied box clears that Pokémon; otherwise the old name comes back. |
| A foe box | pick one already in their 6 | Refused, and the caption names it. |
| A filled mini | × | Removes it from their 6 and from the board. |
| Their team | Clear all | Empties all six, their board slots, everything known about them and the speed-ability switches. |
| Your mini | click | Adds it as the next number, or drops it if it's numbered. Before turn 1 is logged, this resets your leads; after that, only a Pokémon you no longer bring leaves the field. |
| | Board → | Goes to step 2. |

### Step 2, any time

| Where | Gesture | What changes | Waits? |
|---|---|---|---|
| A roster mini | drag onto a card on its own side | It comes in with fresh stages. Dropped on the partner's slot, the two swap and keep their stages. A fainted one can't be dropped. | yes |
| A sprite or an empty slot | click | Opens the picker with that side's team. "(in)", "(on the field)" and "(fainted)" are greyed. "Empty slot" appears when both slots are filled. | yes |
| A name band | click | Cycles none → BRN → PAR → PSN → SLP → FRZ → none. | no |
| A stat cell | click / right-click | Stage +1 / −1, between −6 and +6. | no |
| An HP area | press and drag | HP follows the pointer and is saved on release. 0 means fainted. | yes |
| Their move pill | click | Marks it seen, or unseen again, up to 4 seen. | — |
| "+ other move…" | type, then Enter or pick | Marks it seen. A move it can't learn shakes the box. | — |
| Item tab or chip, yours | click | Opens "Charizard @ Charizardite Y": the item's text and "Used up / knocked off" (or "Not used up after all"). | no |
| Item tab or chip, theirs | click | Opens "which did you see?": their likeliest items with %, an "other item…" box over every item, and once one is set, "Used up / knocked off" and "Not seen yet". | no |
| Your Mega bar, during ① | click | Arms or disarms it. While armed, the scout plays it as the Mega. | — |
| A Mega bar, otherwise | click | A menu: pick the form ("Mega Charizard Y · Drought"; theirs show "% hold Charizardite Y"), "Undo: it didn't Mega Evolve", or the reason it can't. Marking theirs sets their item to that stone. | no |
| Conditions | click a chip | Toggles or cycles it. | no |

**Every change** saves the state, then re-scouts after a 120ms debounce. Each request gets a rising id, and a reply that isn't the newest is dropped. While the scout runs, the old numbers stay up.

### ① Lock in

| Where | Gesture | What changes |
|---|---|---|
| Your card | click a move | Picks it. If it needs a target and has more than one, the Log asks "Heat Wave: click the target card", and the cards it can hit go `.t-target`. |
| A dashed card | click | Sets the target. |
| Your ↔ Switch tab | click | Opens a strip over the stats: "Charizard switches to", with your back as chips (minus one your partner already switches to) and "cancel". |
| That strip | a bench chip | The switch becomes this Pokémon's action. The tab reads "↔ … in · undo" and the moves dim. **The card now draws the one coming in** (SCOUTUI-18). A move click on the card replaces the switch, and undo clears it. |
| Anywhere | Esc | Closes the switch strip, or else cancels the pick in progress. |
| Log | Lock in → | Enabled once both of yours are picked and a scout reply exists. An armed Mega happens. The board and conditions are frozen as the turn's start, and the rows are laid out in expected order. |

Before Lock in, the Log shows a read-only preview of the turn in expected order, with the calc on your picks.

### ② Playing

| Where | Gesture | What changes |
|---|---|---|
| A Log row, or a card's plain area | click | Opens that Pokémon's row; a second click closes it. A fainted Pokémon's row doesn't open. |
| An open row | — | `body.focusing`: everything else blurs (§6.10). The actor gets `.t-acting`. |
| Their open row's card | click the move it used | Sets the row's move; their pills glow while one is needed. A move in another priority bracket moves its row into that bracket. |
| The actor's strip | other move… | A move from the learnset that isn't among the 7. |
| A dashed card | click | Sets the target. "change" on the strip lets you pick again. |
| Your open row's card | click another move | Changes the row's move. |
| A ↔ Switched tab | click | Before the Pokémon acts, the row becomes a switch, moves to the switch bracket and opens "switched to" chips with "cancel". After its move, it was forced out: "then forced out (Eject Button, Red Card…) to", with "didn't switch". Undo or change puts back what the row had. |
| A pivot move (Volt Switch, U-turn, Flip Turn, Parting Shot, Chilly Reception, Baton Pass), either side | — | After ✓ Done (at once for a status pivot), the row stays open and the tab turns `.ask`: "U-turn ↔ who came in?". The strip asks "then switched to", with the bench and "didn't switch". |
| The strip | didn't move | The row is done, with nothing happening. |
| The strip, on a flinched row | it didn't flinch (Inner Focus, Covert Cloak…) | Overrides the flinch. |
| The box over each target | slide | Sets the HP left, starting at the calc's middle. The card's HP bar grows and follows, with the stripes and the before-tick. |
| The box | KO · miss · ✓ Done | KO sets HP to 0. Miss means no damage. Done closes the row. |
| A status move | — | Done as soon as its target is known. |
| A row's grip ⋮⋮ | drag | Reorders the turn, and every HP after it is worked out again. |
| Log | back to the expected order | Re-sorts the rows. |
| Anywhere | Esc, or a click on empty board | Closes the open row. |
| Log | End turn → | Lime when every row is done. Rows not done count as "didn't move". |

**While a turn is played:**

- Each card has a turn tag: "2nd · Iron Head", "flinched" or "fainted".
- Each card's HP is as entered so far.
- Status and stages can still be edited.
- **A card whose slot has been switched draws whoever is in the slot as of the open row** (or as of the last row so far). That card can only be targeted, and its tag reads "↔ X out" (SCOUTUI-18).

### ③ End of turn

End turn writes to the board:

- each Pokémon's HP;
- switches (whoever comes in starts with fresh stages);
- their moves used, as seen (up to 4);
- your PP, minus 1 per move used;
- Trick Room, toggled if someone used it;
- Tailwind, on for the side that used it.

Then the turn goes into the log. The Log asks "Who comes in?" for each fainted slot, with that side's bench as chips, and the next turn begins.

### Earlier turns

| Gesture | What changes |
|---|---|
| Click "Turn N" | Folds the turn open or shut. The summary line has a chip for TR, Tailwind or a Mega, and the end state as small sprites with HP. |
| Drag a row | Fixes the order. The HP stays as entered. |

Each earlier row shows:

- its place (1st…4th) and a why chip ("+3", "switch" or "105 Spe");
- the attacker + type badge, the move, › each target with the HP left, ▲ ✓ ▼, and "−17% · calc 14–19%";
- an "exp. 2nd" tag when the Speed order expected it somewhere else;
- a speed note: "went before Archaludon (105) → **Speed 105–112** this turn", or "… though its Speed is 80–95: Scarf? a speed tie?".

---

## 9. The turn log's rules (the page's only logic)

The page applies these by walking the rows top to bottom.

1. **Damage is stored as damage taken,** not as HP left, so moving a row re-derives every HP after it.
2. **Expected order:** priority first (a switch counts as +7 here), then the scout's Speed order, which already includes Tailwind and Trick Room. Rows move only when dragged, except a move changed into another priority bracket, which moves its own row.
3. **Fake Out** flinches its target if the target's row comes later and the Fake Out wasn't a miss or a KO. The flinch can be overridden.
4. **Protect,** once used in an earlier row, blocks every hit aimed at that Pokémon later in the turn.
5. **A single-target move at a fainted foe** goes to its partner.
6. **A Pokémon KO'd before its row** is skipped.
7. **A switch you locked in** starts the turn done.
8. **Who came in,** by a switch, a pivot or a forced switch, takes the later hits aimed at that slot. Each row records who was in each slot as it played (`occ`). Baton Pass doesn't pass stat changes.
9. **Their picked moves** are sent to the scout as seen at once, so the calc covers them mid-turn.
10. **Their Mega, marked mid-turn,** takes the new Speed order. If nothing has been entered yet, the rows are re-sorted.

---

## 10. Saved state

Everything is in `localStorage["champions-cards-v1"]`, saved on every change. The server keeps nothing. HP is a fraction of max. Per-Pokémon facts are keyed by base name.

```json
{
  "step": "board",
  "foeTeam": ["pelipper", "archaludon", "garchomp", "kingambit", "incineroar", ""],
  "bring": ["charizard", "archaludon", "garchomp", "zoroark"],
  "switchRate": 0.1,
  "slots": {"p2a": {"name": "pelipper", "stages": {}}, "p2b": {"name": "archaludon", "stages": {"spa": 1}},
            "p1a": {"name": "charizard", "stages": {}}, "p1b": {"name": "archaludon", "stages": {}}},
  "mons": {
    "p1": {"charizard": {"hp": 0.62, "status": null, "seen": [], "pp": {"heatwave": 9}, "mega": "charizard-mega-y"}},
    "p2": {"pelipper": {"hp": 1, "status": "PAR", "seen": ["Hurricane", "Tailwind"], "item": "Damp Rock", "itemUsed": false}}
  },
  "weather": "auto", "tailwind": ["foe"], "trickRoom": false, "abilityOff": [],
  "game": {"turn": 3, "log": ["… one entry per finished turn: cond, rows, megas, end"],
           "live": {"phase": "mine | play | replace", "acts": {}, "start": null, "cond": null, "R": null, "mega": null, "megas": []}}
}
```

| What | Kept across a switch? | Kept by New game? |
|---|---|---|
| HP, status, seen moves, PP, item, Mega | yes (per Pokémon) | no |
| Stat stages | no (per slot) | no |
| Their 6, your 4, the step, the switch rate | — | yes |
| Conditions, the turn log | — | no |

**On load,** anything that no longer exists is dropped: a species gone from the dex, or a Pokémon gone from the team file or from their 6. A name gone from the team file also leaves `bring`, and a slot of yours holding anyone not in `bring` is cleared.

---

## 11. Server contract

`champions scout --team FILE [--port 8001] [--no-open]` runs a standard-library `ThreadingHTTPServer` on 127.0.0.1.

| Route | Gives |
|---|---|
| `GET /`, `/cards` | `solver.html` |
| `GET /cards/test` | `test.html` |
| `GET /cards/*.js\|css`, `/icons/<type>.png`, `/sprites/<form>.png` | Only names that match fixed patterns, so no path can climb out of `static/`. |
| `GET /api/dex` | Every species: label, types, learnset, Pikalytics move usage, item odds, and Mega forms (label, types, ability, stone, pct). Every move: name, type, category, PP, priority and target. Every item's text. |
| `GET /api/team` | Your team, re-read from the file on every request: name, label, item, ability, moves, max HP, and the Megas its stone allows. |
| `POST /api/scout` | Scouts the board (below). |
| `POST /api/plans` | The board plus `bench: {mine, foes}` and `switch_rate`, played as Plans. |

**Board entries.**

- `mine` holds 1–2 entries. `foes` holds 0–2 for `/api/scout` and 1–2 for `/api/plans`. Both are in slot order, a then b.
- The errors read "put 1 or 2 Pokémon on your side and at most 2 on theirs" and "put 1 or 2 Pokémon on each side".
- The Plans `bench.mine` holds only your back 2.

| Field | Meaning |
|---|---|
| `name` | Required. |
| `hp` | 0–1 (default 1). |
| `moves` | Replaces the move list. |
| `seen` | (theirs) Moves seen, pinned; the guess fills the rest. |
| `boosts` | −6..6, with engine keys. |
| `status` | `par brn psn tox slp frz`, or null. |
| `mega` | A Mega form id. |
| `item` | (theirs) A seen item. |
| `item_used` | A boolean. |

**Key names differ by layer.**

| Thing | Page state | Request / engine | Builds in the reply |
|---|---|---|---|
| Stat stages | `atk def spa spd spe` | `attack defense special-attack special-defense speed` | `atk def spa spd spe` |
| Status | `BRN PAR PSN SLP FRZ` | lowercase (`tox` is allowed too) | — |
| Tailwind side | `me`, `foe` | `me`, `foe` | — |

**Who computes what.**

- **The server works out:** the Speed order and ranges (stages, paralysis, Tailwind, Trick Room and speed abilities applied); the weather and its source; Watch out, already filtered, with `ko` and `chance`; each hit's calc range; and each Pokémon's builds, with stats before stages.
- **The page only** applies stages to the builds, draws the curves, and applies §9.

```jsonc
// POST /api/scout
{"mine": [{"name": "charizard", "hp": 0.62, "status": null, "boosts": {}, "mega": "charizard-mega-y"}],
 "foes": [{"name": "pelipper", "hp": 1, "status": "par", "seen": ["Hurricane"], "boosts": {"speed": -1}, "item": "Damp Rock"}],
 "weather": "auto", "tailwind": ["foe"], "trick_room": false, "ability_off": [],
 "also": {"mine": [{"name": "garchomp"}], "foes": [{"name": "kingambit"}]}}          // the backs, not fainted (SCOUTUI-18)

// reply
{"weather": "sun", "weather_source": "Drought", "trick_room": false,
 "order": [{"side": "me", "name": "charizard", "label": "Mega Charizard Y", "lo": 152, "hi": 152},
           {"side": "foe", "name": "pelipper", "label": "Pelipper", "lo": 68, "hi": 86}],
 "after": [{"setter": {"side": "foe", "name": "pelipper"}, "what": "Tailwind", "order": ["…"]}],
 "threats": [{"foe": {"…": "…"}, "move": "Hurricane", "priority": 0, "note": "",
              "targets": [{"side": "me", "name": "charizard", "pct": "88–104%", "ko": "OHKO", "chance": "likely"}]}],
 "calc": [{"mon": {"side": "me", "name": "charizard"}, "move": "heatwave", "target": {"side": "foe", "name": "pelipper"},
           "lo": 0.21, "hi": 0.25, "immune": false}],
 "speed_abilities": [{"foe": {"…": "…"}, "ability": "Swift Swim", "weather": "rain", "on": true}],
 "board": [{"side": "me", "name": "charizard", "label": "Mega Charizard Y", "form": "charizard-mega-y", "hp": 0.62, "max_hp": 185,
            "builds": [{"label": "Modest · 32 HP / 32 SpA / 2 SpD", "w": 1, "hp": 185, "stats": {"atk": 104, "spa": 211, "spe": 152}}],
            "moves": [{"id": "heatwave", "name": "Heat Wave", "usage": null, "seen": false}]}],
 "also": [{"side": "me", "name": "garchomp", "builds": ["…"]}, {"side": "foe", "name": "kingambit", "builds": ["…"]}]
 // also: "tailwind", "full_hp", "notes", "triggers", "hits"
}

// POST /api/plans reply (trimmed)
{"board": [{"key": "me:charizard", "side": "me", "label": "Charizard", "hp": 0.62}, {"key": "foe:garchomp", "bench": true}],
 "replies": [{"acts": [{"key": "foe:pelipper", "name": "Hurricane", "type": "Flying", "targets": ["me:charizard"]}],
              "w": 0.31, "w0": 0.22, "fit": 0.4, "switch": false, "extra": false}],
 "plans": [{"acts": ["…"], "takes": 1.2, "loses": 0.3, "hp_bars": 0.4, "score": 1.1, "worst_score": -0.5, "worst": ["…"],
            "switches": 0, "hidden": false, "dim": false, "beaten_by": null}],
 "cells": [[{"dead": {"foe:pelipper": 0.6}, "hp": {"foe:pelipper": [0.0, 0.3]},
             "lines": [{"share": 0.62, "steps": ["…"], "end": {"dead": {}, "hp": {}}}]}]],
 "best": 0, "safe": 0, "samples": 200, "screen": 24, "switch_rate": 0.1, "more": {"replies": 4, "w": 0.12}}
```

The exact payloads are pinned by `tests/test_scout_server.py`. Read it before writing the server.

---

## 12. Files

`test_scout_server` fetches most of these by name, so a server-first build creates them as stubs.

| File | Owns |
|---|---|
| `static/cards/solver.html` | The page: header, steps, layout, and the page-level CSS (§5, §6.1, §6.7). |
| `static/cards/solver.js` | The state, the steps, the board, editing, items and Megas, `fitBoard`, `recompute` (debounced, latest reply wins). |
| `static/cards/pokemon-card.js` + `.css` | `pokemonCard`, `cardTop`, `statCell`/`updateStat` (the curves), `updateCard`, `swapCard`, `morphCard`, `itemTab`, `itemChip`, `megaBar`, `miniCard`/`updateMini`, `replay`, `tween`. |
| `static/cards/move-slots.js` | `loadData()` (`/api/dex`), `MoveSlots` (seen-first, then usage, 7 slots), `opponentCard`, the FLIP `flip()`, `moveInput`. |
| `static/cards/turn.js` + `.css` | `window.Turn`: the Log, ① ② ③, `walk()` (§9), `popover`, `actorStrip`, the switch tabs, `shown(slot)`, card hooks and decoration. |
| `static/cards/plans.js` + `.css` | The matrix and the full-screen turn. |
| `static/cards/test.html` | The test page: four hand-written cards, benches, full rosters, and one button per state change (Hit, Stat ▲/▼, Heal, Status, Faint, Switch, Protect, Reveal, Clue, End turn, Reset). |
| `static/icons/<type>.png`, `static/sprites/<form>.png` | Kept assets. They are never regenerated. |

---

## 13. Invariants and acceptance

**Invariants.** Check these during every manual check:

- Nothing on the board moves or resizes as results arrive, a menu opens, or a turn is played.
- The board fits the window with no scrolling, and nothing is cut off at 1920×1080 or smaller.
- The board re-scouts within about 120ms of an edit, and a late reply never overwrites a newer one.
- Errors always show in the caption.

**Manual checks.** Run `champions scout --team teams/my-team.txt` first.

- **M5** Type their 6 (autocomplete from the 2nd letter: ↑↓, then Enter or Tab moves to the next box); typing one already in their 6 is refused. Click 4 of yours: they number 1–4 (1–2 Lead, 3–4 Back), the other 2 dim, and a 5th click is refused; click #1 and the rest renumber. Board → stays off until you have 4, then opens with your 1 and 2 on the field, their slots reading "+ who did they lead?", only your 4 in your roster, Speed listing your two and Lock in waiting. Pick one of theirs: Watch out fills in. A switch or a replacement offers only your back 2, and so does Plans. New game keeps your 4 and empties their side.
- **M6** Drag a Pokémon from each roster onto a card on its own side; drag one onto its partner's slot and the two swap. Click a sprite and pick from the list. A fainted Pokémon can't be dropped or picked.
- **M7** Drag an HP bar, click a stat (+1) and right-click it (−1), click the name to cycle status, click a dashed foe move to mark it seen. Switch a Pokémon out and back: HP, status and seen moves are kept, stages are not.
- **M8** The board fits the window with no scrolling at 1920×1080 and in a smaller window. Each card's plate shows "HP/max" for yours and "%" for theirs, and a damage number isn't cut off. +1 Speed or paralysis on a slower Pokémon moves it up or down in Speed; lowering your HP turns a 2HKO into an OHKO in Watch out.
- **M9** Change each condition chip; Speed and Watch out update at once, with no reload.
- **M10** Reload mid-game and everything is still there. New game keeps their 6 and the 4 you bring, and clears HP, status, stages, seen moves and conditions.
- **M11** While doing M6–M9, no panel jumps or changes size. On `/cards/test`, each button plays its animation.
- **M12** On 3 · Plans, the matrix appears within a few seconds and dims (without moving) while a board change recomputes. One row has Best vs likely and one Safe pick. Click a cell: the turn opens full screen with each step's priority or Speed, and with a tab per order when Speed can go either way; ×, Esc or a click outside closes it.
- **M13** On 3 · Plans with Pokémon in both backs: at most 4 rows and 6 columns; your best switch is a row and their likeliest switch a column (dimmed when it only made it in for being kept); "Show N more" unfolds the rest; "They switch" cycles 0 / 10 / 20 / 30% and recomputes; a switch cell's turn shows out ↔ in first.
- **M14** On 2 · Board, click a move on each of your cards (and a target card when asked), then Lock in. Click one of their rows: everything blurs except that row and their card, whose move pills glow. Click Fake Out on it, then your card: the row jumps to 1st and your Pokémon's row reads "flinched". A box appears over your card; slide it and your card's HP bar follows (with the calc's stripes), then ✓ Done. Open your Heat Wave row: a box over each of their cards. Esc or a click on empty board space ends the blur; a click on a card's plain area opens its row. Drag a row to another place: the HP after it changes. End turn: HP, their seen moves and your PP stay on the cards, the turn folds into the log, and a reload keeps it all.
- **M15** With Charizard @ Charizardite Y in your team and their Charizard and Garchomp on the board: each card has an item tab (theirs "Charizardite Y? 96%", dashed), and each mini an item chip. Click your Charizard's Mega Evolve bar: it glows, its mini's key stone glows, the weather chip turns to sun, and its stats become the Mega's; click your moves and Lock in: the card flashes into Mega Charizard Y. Click their Garchomp's "They Mega Evolved…", pick Mega Garchomp Z: its card flashes, its item tab reads Garchompite Z, and their Charizard's bar greys out ("one Mega per side"). Mark their Incineroar's Sitrus Berry on its mini, then "Used up": struck through. Nothing on the board shifts. End turn: the log's turn names both Megas; a reload keeps it all; New game clears it.
- **M16** With their Incineroar and Rillaboom on the board, on 2 · Board at ① Lock in: each of your cards has "↔ Switch" on the left of its top edge, clear of the item tab. Click it on one card: a strip over its stats lists your back 2; pick one: the tab reads "↔ (sprite) X in · undo" and its moves dim, the Log preview puts the switch first, and the other card's strip doesn't offer the same one. Click a move on that card instead: the switch is gone. Switch one, pick a move on the other, Lock in: the switch row is already ✓. Their cards now read "↔ Switched". Click Rillaboom's U-turn, then a target, slide the HP, ✓ Done: the box goes, and Rillaboom's tab turns yellow, "U-turn ↔ who came in?", with their bench and "didn't switch" in its strip; pick one: "U-turn ↔ (sprite) Y in · change". Click Incineroar's Parting Shot: it asks at once. On a card whose move is done, "↔ Switched" asks who it was forced out to. A later hit on Rillaboom's slot goes to who came in. End turn: the newcomers are on the board and the log reads "↔ Y in"; undo on a tab puts back what the row had.
- **M17** *(proposed, SCOUTUI-18)* At ① Lock in, set a switch on one of your cards. The card at once draws the one coming in (sprite, name, HP, item, stats, with no Mega bar), and the tab's tooltip names both. Clicking its moves, stats or HP does nothing. During ②, after a pivot's "who came in?" is answered, that card draws the newcomer, with the tag "↔ X out" on its row, and can still be targeted. Undo on the tab puts the original back.

---

## 14. Tried and rejected; not done yet

Don't bring these back without a reason. The number is the decision.

- **Watch out as step 3, then a turn tree** (023). Both fixed the order by Speed alone, so they couldn't show priority, Speed ranges or randomness.
- **A JS simulator for Plans** (023). It would be a second copy of the rules.
- **Plans with too many scenarios** (024): a switch row per Pokémon, grouped or "every switch" tables, a separate switch strip, and fewer samples everywhere.
- **Roster and panels** (025): a roster rail shared by both sides, a bigger roster in the same rail, a 2-column roster grid, a stripped roster, and banner or spine panel headers.
- **Stats placement** (025): a strip under the plate (it loses the curves), hover only (they're needed at a glance), and a hand-tuned size formula.
- **The turn log's first design** (026): a cursor that walks the turn in order, click-to-reorder, in-row move chips, a keyboard dock, and one end-of-turn sheet per Pokémon.
- **Damage entered in the Log row** (026, reversed by 027). The card is where the eye already is.
- **Other damage entry** (027): A, a strip under the plate; C, dragging on the card with ✓ in the row. "Fade" and "Off" focus modes lost to the blur.
- **Item and Mega layouts** (028): A, the item in the name band; B, the item as a fifth pill row (the cards got taller); C, a short mini tab; D, A's minis unchanged.
- **Guessing their leads** (029), and other bring-4 pickers: B, three lanes; C, Lead/Back chips.
- **Switching from the Log** (030), the sprite menu (B), roster then card (C), and the ↔ tab on the right edge, where it collided with the item tab.
- **Free drag-and-drop onto the field mid-game.** It flooded the log with "X in" lines.
- **Focus fire drawn as 2→1 merged arrows.** Speed order changes what happens between the two hits.

**Not done yet:**

- feeding the order's Speed notes back into the scout as a known Speed;
- chance flinches (Rock Slide), which are entered as "didn't move" by hand;
- foe items you haven't marked, and other foe abilities;
- Plans playing pivot moves;
- Plans' turns beyond this one, and turns out (everyone is treated as on their first turn).

---

## 15. Build order

Give one stage per session. A stage is done when its checks pass and nothing on the board moves while doing them.

| Stage | Build | Done when |
|---|---|---|
| U2 | The server (§11), with stub files (§12). | `tests/test_scout_server.py` passes. |
| U3a | Step 1 and the board: the tokens (§4), the skeleton (§5), the card, mini, chips and panels (§6.1–6.7), and the step 2 any-time gestures (§8), saved state (§10) and every animation, plus `/cards/test`. | M5–M11 |
| U3b | Plans (§6.11, §7 step 3). | M12–M13 |
| U3c | The turn log and switching (§6.9–6.10, §8 ①–③, §9), including SCOUTUI-18's shown-incoming. | M14, M16, M17 |
| U3d | Items and Mega Evolution (§6.4–6.5). | M15 |

Wherever a rebuild has to guess, the spec has a gap. Write the answer here, not just in the code.
