"""Compare the live solver with the rollout and MCTS move pickers.

Audit (default): on random doubles positions, solve with the live 2-turn setting, then with each game-playing method
twice (seeds 1 and 2), and report how often the top pick agrees and how much guaranteed value the other pick gives up.

    python scripts/compare_solvers.py [n_positions] [seed] [--budget S] [--workers W]

Match: bots play whole games against each other.

    python scripts/compare_solvers.py --match N --bots mcts,live [--budget S] [--workers W] [--shard I/N] [--json FILE]

Bots: live (solve_budget), fallback (the 1-turn solve), rollout, mcts, mcts-greedy, random, and rollout-old / mcts-old
(the same with the old root options, no Protect and one switch). --protect gives every mon Protect in place of its last move.
"""
import argparse, json, random, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from champions.engine import game
from champions.solver import mcts, rollout, search
from position_audit import POOL, B, position, sp, with_protect

MAX_TURNS = 40
OLD_ROOT = dict(moves=2, status=0, switches=1)          # the root options before Protect and every switch were added
METHODS = {"rollout": lambda b, a: rollout.solve_rollout(b, budget=a.budget, workers=a.workers, seed=a.seed, policy="random"),
           "mcts": lambda b, a: mcts.solve_mcts(b, budget=a.budget, workers=a.workers, seed=a.seed, policy="random"),
           "mcts-greedy": lambda b, a: mcts.solve_mcts(b, budget=a.budget, workers=a.workers, seed=a.seed, policy="greedy")}
OLD = {"rollout-old": lambda b, a: rollout.solve_rollout(b, budget=a.budget, workers=a.workers, seed=a.seed, policy="random", root=OLD_ROOT),
       "mcts-old": lambda b, a: mcts.solve_mcts(b, budget=a.budget, workers=a.workers, seed=a.seed, policy="random", root=OLD_ROOT)}
BOTS = {**METHODS, **OLD}


# ---------------------------------------------------------------- audit

def live(b, workers):
    """The live 2-turn solve with the game-playing methods' root options, so every method's rows still line up.
    It still can't Protect on turn 2."""
    return search.solve(b, depth=2, buckets=B, min_prob=0.05, deep_min_prob=0.05, time_limit=300, workers=workers,
                        **{**search.LIVE, "root_filter": rollout.ROOT})


def top(r):
    return max(zip(r.row_mix, r.rows))[1]


def guarantee(mix, judge):
    """What `mix` (over the judge's rows) is sure to get in the judge's table: its worst column."""
    m = len(judge.cols)
    return min(sum(mix[i] * (judge.matrix[i][j] if judge.matrix[i][j] is not None else judge.value)
                   for i in range(len(mix))) for j in range(m))


def gap(other, judge):
    """How much guaranteed value the judge loses by following `other`'s mix instead of its own."""
    return judge.value - guarantee(other.row_mix, judge)


def audit(n, seed, args):
    rnd = random.Random(seed)
    tot = {k: [0, 0, 0.0, 0.0, 0.0, 0] for k in METHODS}      # same top vs live, same top vs rerun, gaps, positions
    for k in range(n):
        b = position(rnd, args.protect)
        ref = live(b, args.workers)
        print(f"pos {k}: live {ref.value:+.3f} top {top(ref)}", flush=True)
        for name, run in METHODS.items():
            runs = []
            for s in (1, 2):
                args.seed = s
                runs.append(run(b, args))
            if any(r.rows != ref.rows or r.cols != ref.cols for r in runs):
                print(f"  {name}: skipped (its rows or columns differ from the live solve's)")
                continue
            a, c = runs
            t = tot[name]
            t[0] += top(a) == top(ref); t[1] += top(a) == top(c)
            t[2] += gap(a, ref); t[3] += gap(a, c); t[5] += 1
            print(f"  {name:12} top {top(a)} | same as live {top(a) == top(ref)} gap {gap(a, ref):.3f} | "
                  f"rerun same {top(a) == top(c)} gap {gap(a, c):.3f} | {a.label}", flush=True)
    for name, t in tot.items():
        if t[5]:
            print(f"{name:12} same top as live {t[0]}/{t[5]}  same top on rerun {t[1]}/{t[5]}  "
                  f"mean gap vs live {t[2] / t[5]:.3f}  vs rerun {t[3] / t[5]:.3f}")


# ---------------------------------------------------------------- matches

def sample(mix, rnd):
    x, acc = rnd.random() * sum(mix), 0.0
    for k, w in enumerate(mix):
        acc += w
        if x < acc:
            return k
    return len(mix) - 1


def decide(bot, b, side, args, rnd):
    """Our choices for `side` this turn. Both sides' bots solve the same one-turn game from side 0's point of view,
    so side 1 plays the column mix of its own solve."""
    if bot == "random":
        return rollout.random_choices(b, side, rnd)
    args.seed = rnd.getrandbits(20)
    if bot == "live":
        r = search.solve_budget(b, args.budget, workers=args.workers)
    elif bot == "fallback":
        r = search.solve(b, depth=1, buckets=B, min_prob=0.05, **search.FALLBACK)
    elif bot in BOTS:
        r = BOTS[bot](b, args)
    else:
        raise SystemExit(f"unknown bot {bot}")
    mix, actions = (r.row_mix, r.row_actions) if side == 0 else (r.col_mix, r.col_actions)
    if not actions:
        return []
    return list(actions[sample(mix, rnd)])


def teams(rnd, protect=False):
    mons = rnd.sample(POOL, 8)
    return [[sp(s, with_protect(m) if protect else m, a) for s, m, a in half] for half in (mons[:4], mons[4:])]


def play(bots, g, args):
    """Game g between bots[0] and bots[1]: team pair g // 2, sides swap every other game."""
    rnd = random.Random(args.seed0 * 100_003 + g)
    pair = teams(random.Random(args.seed0 * 1000 + g // 2), args.protect)
    swap = g % 2
    order = [bots[1], bots[0]] if swap else list(bots)           # order[side] = the bot playing that side
    b = game.start(pair, seed=g + 1, format="doubles")
    while b.winner is None and b.turn < MAX_TURNS:
        choices = []
        for side in (0, 1):
            mine = decide(order[side], b, side, args, rnd)
            choices += mine
        if not choices:
            break
        game.play_turn(b, choices)
    win = None if b.winner in (None, -1) else order[b.winner]
    return {"game": g, "winner": win, "turns": b.turn, "order": order}


def match(args):
    bots = args.bots.split(",")
    if len(bots) != 2:
        raise SystemExit("--bots takes two names, like mcts,live")
    i, n = (int(x) for x in args.shard.split("/"))
    games = []
    for g in range(args.match):
        if g % n != i:
            continue
        t0 = time.perf_counter()
        r = play(bots, g, args)
        games.append(r)
        print(f"game {g}: {r['winner'] or 'draw'} in {r['turns']} turns ({time.perf_counter() - t0:.0f}s)", flush=True)
    wins = {b: sum(r["winner"] == b for r in games) for b in bots}
    draws = sum(r["winner"] is None for r in games)
    print(f"{bots[0]} {wins[bots[0]]} - {wins[bots[1]]} {bots[1]}  ({draws} draws, {len(games)} games)")
    if args.json:
        Path(args.json).write_text(json.dumps({"bots": bots, "wins": wins, "draws": draws, "games": games}))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("n", nargs="?", type=int, default=8)
    p.add_argument("seed", nargs="?", type=int, default=1)
    p.add_argument("--match", type=int, default=0)
    p.add_argument("--bots", default="mcts,live")
    p.add_argument("--budget", type=float, default=5.0)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--shard", default="0/1")
    p.add_argument("--json")
    p.add_argument("--protect", action="store_true", help="every mon gets Protect in place of its last move")
    args = p.parse_args()
    args.seed0 = args.seed
    if args.workers > 1:
        search.get_pool(args.workers)
    match(args) if args.match else audit(args.n, args.seed, args)


if __name__ == "__main__":
    main()
