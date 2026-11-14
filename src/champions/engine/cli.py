"""champions sim replay <file> [--turn N] [--rng] [--raw]   play a saved replay and print it."""
import argparse
import os
import sys

from .pretty import render, set_color
from .replay import ReplayError, load_replay, play_replay


def main():
    p = argparse.ArgumentParser(prog="champions sim")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("replay", help="play a replay and print it")
    r.add_argument("file")
    r.add_argument("--turn", type=int, help="show only this turn (1-based), with HP before and after")
    r.add_argument("--rng", action="store_true", help="also show the random rolls")
    r.add_argument("--raw", action="store_true", help="print the raw event log, one line per event")
    r.add_argument("--color", choices=["auto", "always", "never"], default="auto",
                   help="colorize output (auto: only on a terminal, and not if NO_COLOR is set)")
    args = p.parse_args()
    set_color(args.color == "always" or (args.color == "auto" and sys.stdout.isatty()
                                         and "NO_COLOR" not in os.environ))
    try:
        data = load_replay(args.file)
        if args.raw:
            b = play_replay(data)
            for e in b.log:
                print(e)
            if b.winner is not None:
                print("winner:", "draw" if b.winner == -1 else f"side {b.winner}")
        elif args.turn:
            print(render(data, args.turn, play_replay, args.rng))
        else:
            for t in range(1, len(data["turns"]) + 1):
                print(render(data, t, play_replay, args.rng))
                print()
    except (ReplayError, OSError, ValueError) as e:
        sys.exit(f"error: {e}")
