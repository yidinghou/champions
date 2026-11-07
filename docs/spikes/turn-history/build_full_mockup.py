"""Builds full-mockup.html: the real play UI (src/champions/play/static/index.html) with a recorded battle baked in
and the turn scrubber replaced by A3-style numbered turn tabs plus a whole-battle log in the right gutter.
Run: PYTHONPATH=src python3 docs/spikes/turn-history/build_full_mockup.py"""
import json
import pathlib

from champions.battle.dex import dex
from champions.play.session import Session

HERE = pathlib.Path(__file__).parent
SRC = (HERE / "../../../src/champions/play/static/index.html").resolve().read_text()

# -- a real recorded battle: views[k] is what the API returned after turn k ------------------------------------
M = lambda s, *mv: {"species": s, "moves": list(mv)}
s = Session()
views = [s.new({"teams": {"p1": [M("incineroar", "fakeout", "tailwind", "mudslap")], "p2": [M("garchomp", "aquatail", "mudslap")]},
                "seed": 3, "chance": [95]})]
for turn in ({"p1a": {"move": "fakeout", "target": "p2a"}, "p2a": {"move": "mudslap", "target": "p1a"}},
             {"p1a": {"move": "tailwind"}, "p2a": {"move": "aquatail", "target": "p1a"}},
             {"p1a": {"move": "mudslap", "target": "p2a"}, "p2a": {"move": "aquatail", "target": "p1a"}},
             {"p1a": {"move": "mudslap", "target": "p2a"}, "p2a": {"move": "mudslap", "target": "p1a"}}):
    views.append(s.turn(turn))

NEW_SHOW = r'''
let openSlot = null, cursor = 3, selTurn = 2, selFrame = null;  // cursor: turns played so far; selTurn: tab being viewed (null = live)
const VIEWS = __VIEWS__, DEX = __DEX__;
function turnTab(k, on) { return el("button", {class: "t" + (on ? " on" : ""), onclick: () => { selTurn = k === cursor ? null : k; selFrame = null; show(); }}, String(k)); }
function show() {
  $("setup").classList.add("hidden"); $("game").classList.remove("hidden");
  view = VIEWS[cursor];
  const g = $("game"); g.replaceChildren();
  const k = selTurn == null ? cursor : selTurn;                      // turn on the board
  const frames = k === 0 ? [] : VIEWS[k].frames;
  const frame = selFrame != null ? frames[selFrame] : null;
  const state = frame ? frame.state : k === 0 ? VIEWS[0].snapshot : frames[frames.length - 1].state;
  const live = k === cursor && selFrame == null && !playing;
  const canAct = live && !view.winner && !view.pending.length;
  const slots = canAct ? orderSlots() : [];
  if (!slots.includes(openSlot)) openSlot = slots.find((x) => !ready(x)) || slots[0] || null;
  const targeted = new Set(slots.filter(ready).map((x) => picks[x].target).filter(Boolean));
  const ctx = {frame, targeted, open: openSlot, diff: hpDiff(frames, selFrame)};

  // turn tabs: the selected number is attached to its board, like a folder tab
  const tabs = el("div", {class: "tabs"});
  for (let i = 1; i <= cursor; i++) tabs.append(turnTab(i, i === k));
  tabs.append(el("button", {class: "t next" + (k === cursor && selTurn == null ? " on" : ""), onclick: () => { selTurn = null; selFrame = null; show(); }}, String(cursor + 1)));
  tabs.append(el("span", {style: "flex:1"}),
    el("button", {onclick: () => { cursor = Math.max(0, cursor - 1); selTurn = null; selFrame = null; show(); }, disabled: !cursor}, "Undo"),
    el("button", {onclick: () => { cursor = 0; selTurn = null; selFrame = null; show(); }}, "Restart"));
  const sides = el("div", {class: "field"});
  for (const side of ["p2", "p1"]) {
    const col = el("div", {class: side}, el("h2", {}, side === "p1" ? "Player 1" : "Player 2"),
      el("div", {class: "cards"}, Object.keys(state.slots).filter((x) => x.startsWith(side)).map((slot) => slotCard(slot, state.slots[slot], ctx))),
      el("div", {class: "mute"}, "Bench: ", state.bench[side].map((b) => `${pretty(b.species)} ${b.hp}/${b.max_hp}`).join(", ") || "none"));
    sides.append(col);
  }
  const board = el("div", {class: "panel"},
    el("div", {class: "row"}, el("strong", {}, k === cursor && selTurn == null ? `Turn ${state.turn} · live` : `Turn ${k}`), fieldTags(state.field)), sides);
  g.append(el("div", {class: "split"}, el("div", {}, tabs, board), el("div", {class: "gutter-col"}, rail(live, canAct, slots), battleLog(k))));
  const box = $("battle-log"), head = box && box.querySelector(".turnblk.on");
  if (box && head) box.scrollTo({top: head.offsetTop - box.offsetTop - 6, behavior: "smooth"});
}
function battleLog(k) {  // the whole battle, one block per turn; the viewed turn is highlighted and scrolled into view
  const box = el("div", {class: "card log", id: "battle-log"}, el("h3", {}, "Battle log"));
  for (let t = 1; t <= cursor; t++) {
    const fr = VIEWS[t].frames, blk = el("div", {class: "turnblk" + (t === k ? " on" : ""), onclick: () => { selTurn = t === cursor ? null : t; selFrame = null; show(); }},
      el("div", {class: "th"}, `Turn ${t}`, fieldTags(fr[0].state.field)));
    fr.forEach((f, i) => { if (i === 0) return;
      blk.append(el("div", {class: "ln" + (t === k && selFrame === i ? " on" : ""), onclick: (e) => { e.stopPropagation(); selTurn = t === cursor ? null : t; selFrame = i; show(); }}, fmtLog(f.text))); });
    box.append(blk);
  }
  if (!view.winner) box.append(el("div", {class: "turnblk wait" + (selTurn == null && selFrame == null ? " on" : "")}, el("div", {class: "th"}, `Turn ${cursor + 1}`), el("div", {class: "mute"}, "waiting for orders…")));
  return box;
}
'''
NEW_TAIL = r'''
let timer = null, playing = false;
async function act(fn) {  // mockup: "Resolve turn" reveals the next recorded turn and plays its lines down the log
  $("err").textContent = "";
  if (cursor >= VIEWS.length - 1) { fail(new Error("mockup ends here: that was the last recorded turn")); return; }
  cursor++; selTurn = null; picks = {}; openSlot = null; playing = true; selFrame = 0; show();
  const n = VIEWS[cursor].frames.length;
  timer = setInterval(() => { if (selFrame >= n - 1) { clearInterval(timer); playing = false; selFrame = null; } else selFrame++; show(); }, 650);
}
(async () => { dex = DEX; view = VIEWS[cursor]; show(); })();
</script>
</body>
</html>
'''
EXTRA_CSS = '''
  /* --- spike: A3 turn tabs + whole-battle log in the right gutter --- */
  .tabs { display:flex; gap:6px; align-items:flex-end; padding-left:4px; }
  .tabs .t { border:1px solid var(--line); border-bottom:none; background:var(--bg); color:var(--mute); border-radius:10px 10px 0 0; padding:6px 16px 8px; font-weight:700; min-width:52px; }
  .tabs .t.on { background:var(--card); color:var(--ink); border-color:var(--acc); margin-bottom:-1px; padding-top:9px; position:relative; z-index:1; }
  .tabs .t.next { border-style:dashed; border-bottom:none; }
  .tabs button:not(.t) { margin-bottom:6px; }
  .panel { background:var(--card); border:1px solid var(--acc); border-radius:0 10px 10px 10px; padding:12px; }
  .gutter-col { position:sticky; top:12px; display:flex; flex-direction:column; gap:8px; max-height:calc(100vh - 24px); }
  .gutter-col .rail { position:static; flex:none; }
  #battle-log { flex:1; min-height:160px; max-height:none; overflow:auto; margin:0; position:relative; }
  #battle-log .turnblk.on { font-weight:400; color:var(--ink); }
  #battle-log h3 { position:sticky; top:-12px; background:var(--card); padding:12px 0 6px; margin:-12px 0 0; z-index:2; }
  .turnblk { border-left:3px solid var(--line); padding:3px 0 4px 10px; margin:0 0 8px; cursor:pointer; border-radius:0 6px 6px 0; opacity:.62; }
  .turnblk.on { border-color:var(--acc); background:color-mix(in srgb, var(--acc) 9%, transparent); opacity:1; }
  .turnblk .th { font-size:11px; font-weight:700; letter-spacing:.05em; text-transform:uppercase; color:var(--mute); }
  .turnblk .th .tag { text-transform:none; letter-spacing:0; margin-left:6px; }
  .turnblk .ln { padding:1px 4px; margin-left:-4px; border-radius:4px; font-size:13px; }
  .turnblk .ln.on { background:var(--acc); color:#fff; font-weight:600; } .turnblk .ln.on span { color:#fff; }
'''
a = SRC.index("let openSlot = null;\nfunction show() {")
b = SRC.index("function fieldTags(")
out = SRC[:a] + NEW_SHOW.replace("__VIEWS__", json.dumps(views)).replace("__DEX__", json.dumps(dex())) + SRC[b:]
c = out.index("async function act(fn) {")
out = out[:c] + NEW_TAIL
out = out.replace("</style>", EXTRA_CSS + "</style>", 1).replace("<title>Champions Play</title>", "<title>Champions Play — turn tabs + log gutter (mockup)</title>")
out = out.replace("`/icons/", "`../../../src/champions/play/static/icons/")
(HERE / "full-mockup.html").write_text(out)
print("wrote", HERE / "full-mockup.html", len(out) // 1024, "KB")
