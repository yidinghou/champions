"""champions sim replay <file>   play a saved replay and print the event log."""
import sys

from .replay import ReplayError, replay


def main():
    argv = sys.argv[1:]
    if len(argv) != 2 or argv[0] != "replay":
        sys.exit("usage: champions sim replay <replay.json>")
    try:
        b = replay(argv[1])
    except (ReplayError, OSError) as e:
        sys.exit(f"error: {e}")
    for e in b.log:
        print(e)
    if b.winner is not None:
        print("winner:", "draw" if b.winner == -1 else f"side {b.winner}")
