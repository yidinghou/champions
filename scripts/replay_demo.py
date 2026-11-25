"""Build scripts/replay_demo.html: one game, MCTS (side 0) vs a simple opponent (side 1), stepped turn by turn.

    python scripts/replay_demo.py [--opponent greedy|random] [--seed 1] [--budget 2] [--workers 4]
    open scripts/replay_demo.html

Each turn the page shows the board before and after, what MCTS chose (and its mix over the other options),
what the opponent did, and the battle log. MCTS plays side 0 by taking its top option (--pick sample draws from its mix instead); the opponent plays its policy.
"""
import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

import base64                                                   # noqa: E402

from champions.engine import game                               # noqa: E402
from champions.engine.actions import Move, Switch               # noqa: E402
from champions.solver.actions import CHOOSES_TARGET, describe, moves_data       # noqa: E402
from champions.solver.mcts import solve_mcts                    # noqa: E402
from champions.solver.rollout import POLICIES, result           # noqa: E402


def sp(species, moves, ability):
    return dict(species=species, moves=moves, ability=ability)


TEAMS = [[sp("incineroar", ["fakeout", "flamethrower", "closecombat", "nightslash"], "intimidate"),
          sp("garchomp", ["earthquake", "dragonclaw", "rockslide", "stoneedge"], "sandveil"),
          sp("venusaur", ["gigadrain", "sludgebomb", "sleeppowder", "earthquake"], "overgrow"),
          sp("rotom", ["thunderwave", "surf", "shadowball", "willowisp"], "levitate")],
         [sp("gengar", ["shadowball", "sludgebomb", "thunderwave", "icebeam"], "cursedbody"),
          sp("dragonite", ["dragonclaw", "extremespeed", "icebeam", "earthquake"], "innerfocus"),
          sp("gyarados", ["surf", "icebeam", "stoneedge", "earthquake"], "intimidate"),
          sp("salamence", ["dragonclaw", "flamethrower", "earthquake", "rockslide"], "enter")]]
TEAMS[1][3]["ability"] = "intimidate"


ICONS = HERE.parent / "sources" / "icons"
SPRITES = {}


def sprite(species):
    """data: URI of the species icon ('' if there is none), cached so each is embedded once."""
    if species not in SPRITES:
        f = ICONS / f"{species}.png"
        SPRITES[species] = "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode() if f.exists() else ""
    return species


def board(b):
    from champions.solver.actions import moves_data  # noqa: F401
    return [[{"name": m.species.title(), "species": sprite(m.species), "types": list(m.types), "hp": m.hp,
              "max": m.max_hp, "status": m.status, "active": i in s.active} for i, m in enumerate(s.team)]
            for s in b.sides]


def events(b, turn):
    return [str(e) for e in b.log if e.turn == turn and e.kind != "rng"][:80]


def _mv(name):
    d = moves_data()[name]
    return {"move": d["name"], "type": d["type"].lower(), "cat": d["category"].lower(), "bp": d["base_power"]}


def choice_view(b, c):
    mon = b.sides[c.side].mon_at(c.slot)
    base = {"mon": mon.species.title(), "species": sprite(mon.species)}
    if isinstance(c, Switch):
        to = b.sides[c.side].team[c.to]
        return {**base, "switch": to.species.title(), "to": sprite(to.species)}
    out = {**base, **_mv(c.move), "mega": bool(c.mega)}
    kind = moves_data()[c.move]["target"]
    tgt = getattr(c, "target", None)
    foe = b.mon(*tgt) if tgt else None
    if kind in CHOOSES_TARGET:
        if foe is not None and len(b.sides[tgt[0]].alive_active()) > 1:
            out["target"] = foe.species.title()
    elif kind == "allAdjacentFoes":
        out["target"] = "both foes"
    elif kind == "allAdjacent":
        out["target"] = "everyone else"
    return out


def joint_view(b, combo):
    return [choice_view(b, c) for c in combo]


def _ref(ref):
    """'p1:rotom' -> (side 0, 'Rotom')."""
    side, species = ref.split(":", 1)
    return int(side[1:]) - 1, species


def actions(b, turn):
    """The turn's events grouped into steps: one per switch / move (with who it hit and for how much) / other."""
    steps, cur = [], None
    for e in b.log:
        if e.turn != turn or e.kind in ("rng", "turn", "start"):
            continue
        d = e.data
        if e.kind == "move":
            side, sp = _ref(d["mon"])
            cur = {"kind": "move", "side": side, "mon": sp.title(), "species": sprite(sp), **_mv(d["move"]),
                   "targets": [], "notes": []}
            steps.append(cur)
        elif e.kind == "switch":
            side, sp = _ref(d["mon"])
            cur = None
            steps.append({"kind": "switch", "side": side, "mon": sp.title(), "species": sprite(sp)})
        elif e.kind == "damage" and cur is not None:
            side, sp = _ref(d["mon"])
            hp, mx = (int(x) for x in d["hp"].split("/"))
            cur["targets"].append({"side": side, "mon": sp.title(), "species": sprite(sp), "dmg": d["amount"],
                                   "pct": d["amount"] / mx if mx else 0, "hp": hp, "max": mx, "out": "hit"})
        elif e.kind in ("immune", "protected", "missed", "blocked") and cur is not None:
            side, sp = _ref(d["mon"])
            cur["targets"].append({"side": side, "mon": sp.title(), "species": sprite(sp), "out": e.kind})
        elif e.kind == "crit" and cur is not None:
            cur["notes"].append("critical hit")
        elif e.kind == "fail":
            side, sp = _ref(d["mon"])
            if cur is not None:
                cur["notes"].append(f"failed ({d.get('reason', '?')})")
            else:
                steps.append({"kind": "note", "text": f"{sp.title()}'s {d['move']} failed", "side": side})
        elif e.kind == "faint":
            side, sp = _ref(d["mon"])
            steps.append({"kind": "faint", "side": side, "mon": sp.title(), "species": sprite(sp)})
            if cur is not None:
                for t in cur["targets"]:
                    if t["mon"] == sp.title() and t["side"] == side:
                        t["ko"] = True
        elif e.kind in ("boost", "status", "volatile", "heal", "recoil", "field", "item", "ability", "damage"):
            who = _ref(d["mon"])[1].title() if d.get("mon") else ""
            if e.kind == "boost":
                text = f"{who} {d['stat'].upper()} {d['change']:+d}" + (f" ({d['cause']})" if d.get("cause") else "")
            else:
                body = " ".join(f"{k}={v}" for k, v in d.items() if k != "mon")
                text = f"{who} {e.kind} {body}".strip()
            steps.append({"kind": "note", "text": text, "side": _ref(d["mon"])[0] if d.get("mon") else None})
    return steps


def top_options(b, res, n=6):
    order = sorted(range(len(res.rows)), key=lambda i: -res.row_mix[i])[:n]
    return [{"combo": joint_view(b, res.row_actions[i]), "p": res.row_mix[i],
             "vs_their_mix": sum(res.matrix[i][j] * res.col_mix[j] for j in range(len(res.cols)))} for i in order]


def play(args):
    b = game.start([[dict(s) for s in t] for t in TEAMS], seed=args.seed, format="doubles")
    rnd = random.Random(args.seed)
    opp = POLICIES[args.opponent]
    turns = []
    while b.winner is None and b.turn < args.max_turns:
        before = board(b)
        res = solve_mcts(b, budget=args.budget, workers=args.workers, seed=args.seed * 1000 + b.turn)
        if not res.row_actions:
            break
        if args.pick == "best":
            i = max(range(len(res.rows)), key=lambda k: res.row_mix[k])
        else:
            i = rnd.choices(range(len(res.rows)), weights=res.row_mix)[0]
        mine = res.row_actions[i]
        theirs = opp(b, 1, rnd)
        their_label = describe(b, theirs)
        chosen_view, their_view = joint_view(b, mine), joint_view(b, theirs)
        j = max(range(len(res.cols)), key=lambda j: res.col_mix[j])
        expected_reply = joint_view(b, res.col_actions[j])
        options = top_options(b, res)
        game.play_turn(b, list(mine) + list(theirs))
        turns.append({"turn": b.turn, "before": before, "after": board(b), "chosen": chosen_view,
                      "chosen_p": res.row_mix[i], "value": res.value, "options": options,
                      "their_best_reply": expected_reply, "theirs": their_view, "steps": actions(b, b.turn),
                      "log": events(b, b.turn), "iterations": getattr(res.stats, "iterations", 0)})
        print(f"turn {b.turn}: {res.rows[i]}  |  {their_label}  (value {res.value:+.2f})", file=sys.stderr)
    return {"sprites": SPRITES, "opponent": args.opponent, "seed": args.seed, "budget": args.budget, "turns": turns,
            "start": turns[0]["before"] if turns else board(b), "winner": b.winner, "result": result(b),
            "ended_early": b.winner is None}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--opponent", choices=sorted(POLICIES), default="greedy")
    p.add_argument("--pick", choices=["best", "sample"], default="best",
                   help="best: play MCTS's top option (default); sample: draw from its mix")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--budget", type=float, default=2.0, help="seconds of MCTS per turn")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--max-turns", type=int, default=30)
    args = p.parse_args()
    data = play(args)
    html = (HERE / "replay_demo_template.html").read_text().replace("__DATA__", json.dumps(data))
    out = HERE / "replay_demo.html"
    out.write_text(html)
    w = {0: "MCTS won", 1: "opponent won", None: "no winner"}[data["winner"]]
    print(f"{w} in {len(data['turns'])} turns -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
