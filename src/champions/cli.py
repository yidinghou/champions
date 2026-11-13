"""Umbrella CLI: `champions <command> [args...]`."""
import sys
from importlib import import_module

COMMANDS = {
    "sources": ("champions.sources.cli", "usage-stat sources: sources {munchstats|pikalytics|championslab|opgg|compare}"),
}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in COMMANDS:
        print("usage: champions <command> [args]\n\ncommands:")
        for name, (_, desc) in COMMANDS.items():
            print(f"  {name:<10}{desc}")
        return
    sys.argv = [f"champions {argv[0]}", *argv[1:]]
    import_module(COMMANDS[argv[0]][0]).main()
