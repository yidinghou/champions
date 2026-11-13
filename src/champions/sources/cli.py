"""`champions sources <name> [args]` dispatcher."""
import sys
from importlib import import_module

NAMES = ["munchstats", "pikalytics", "championslab", "opgg", "compare"]


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] not in NAMES:
        sys.exit(f"usage: champions sources {{{'|'.join(NAMES)}}} [--limit N] [--refresh] [--format F] [name ...]")
    sys.argv = [f"champions sources {argv[0]}", *argv[1:]]
    import_module(f"champions.sources.{argv[0]}").main()


if __name__ == "__main__":
    main()
