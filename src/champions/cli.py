"""Umbrella CLI: `champions <command> [args...]`."""
import sys
from importlib import import_module

COMMANDS = {
    "sources": ("champions.sources.cli", "usage-stat sources: sources {munchstats|pikalytics|championslab|opgg|icons}"),
    "check-roster": ("champions.fetch.roster_check", "verify new_in_mc tags against Showdown (network)"),
}
FETCHERS = {
    "champions": "champions.fetch.champions",
    "moves": "champions.fetch.moves",
    "reference": "champions.fetch.reference",
}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in (*COMMANDS, "fetch"):
        print("usage: champions <command> [args]\n\ncommands:")
        for name, (_, desc) in COMMANDS.items():
            print(f"  {name:<14}{desc}")
        print(f"  {'fetch':<14}refresh game data from the network: fetch {{{'|'.join(FETCHERS)}}}")
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "fetch":
        if not rest or rest[0] not in FETCHERS:
            sys.exit(f"usage: champions fetch {{{'|'.join(FETCHERS)}}}")
        module, prog, rest = FETCHERS[rest[0]], f"champions fetch {rest[0]}", rest[1:]
    else:
        module, prog = COMMANDS[cmd][0], f"champions {cmd}"
    sys.argv = [prog, *rest]
    import_module(module).main()
