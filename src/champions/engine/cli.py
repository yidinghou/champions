"""champions sim replay <file> [--turn N] [--rng] [--raw]   play a saved replay and print it.
champions sim view <file> [-o out.html]                    step through a replay in the browser."""
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
    v = sub.add_parser("view", help="write a replay as a self-contained HTML page and open it in a browser")
    v.add_argument("file")
    v.add_argument("-o", "--out", help="output path (default: next to the replay, .html)")
    v.add_argument("--no-open", action="store_true", help="write the page but don't open it")
    args = p.parse_args()
    if args.cmd == "view":
        from .viewer import write_html
        try:
            out = write_html(args.file, args.out)
        except (ReplayError, OSError, ValueError) as e:
            sys.exit(f"error: {e}")
        print(out)
        if not args.no_open:
            import webbrowser
            webbrowser.open(out.resolve().as_uri())
        return
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
