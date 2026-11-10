"""Usage-statistics sources for Pokémon Champions (moves, items, abilities, spreads, teammates).

Each module fetches one site, parses it into a common snapshot (see common.py) and saves it under
sources/snapshots/. Run `champions sources <name> [--limit N] [--refresh]`; compare with
`champions sources compare`. Analysis of each source's fidelity: sources/README.md.
"""
