"""Umbrella CLI: `champions <command> [args...]`. Each command's own --help lists its options."""
import sys
from importlib import import_module

from . import __version__

COMMANDS = {
    "lookup": ("champions.lookup", "look up Pokémon, moves, items, abilities (offline)"),
    "calc": ("champions.calc", "damage calculator"),
    "stats": ("champions.stats", "level-50 battle stats: stats NAME [NATURE] [stat=sp,...]"),
    "check-roster": ("champions.fetch.roster_check", "verify new_in_mc tags against Showdown (network)"),
}
FETCHERS = {
    "champions": "champions.fetch.champions",
    "moves": "champions.fetch.moves",
    "reference": "champions.fetch.reference",
    "opgg": "champions.fetch.opgg",
}


def usage():
    lines = [f"usage: champions <command> [args]   (champions {__version__})", "", "commands:"]
    lines += [f"  {name:<13}{desc}" for name, (_, desc) in COMMANDS.items()]
    lines.append(f"  {'fetch':<13}refresh data from the network: fetch {{{'|'.join(FETCHERS)}}}")
    return "\n".join(lines)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(usage())
        return
    if argv[0] == "--version":
        print(__version__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "fetch":
        if not rest or rest[0] not in FETCHERS:
            sys.exit(f"usage: champions fetch {{{'|'.join(FETCHERS)}}}")
        module, prog, rest = FETCHERS[rest[0]], f"champions fetch {rest[0]}", rest[1:]
    elif cmd in COMMANDS:
        module, prog = COMMANDS[cmd][0], f"champions {cmd}"
    else:
        sys.exit(f"unknown command {cmd!r}\n\n{usage()}")
    sys.argv = [prog, *rest]
    import_module(module).main()


if __name__ == "__main__":
    main()
