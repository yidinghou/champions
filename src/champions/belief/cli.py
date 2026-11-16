"""champions belief <species> [--seen-move M]... [--seen-item I] [--seen-ability A] [--top N] [--view V]

Show the belief about one opposing Pokemon's hidden set: the likeliest sets, per-field marginals, and how much of it
the engine can simulate. Reveal moves/items/abilities with the --seen-* flags to see the belief narrow.
"""
import argparse
import sys
from typing import List, Optional

from .belief import AbilitySeen, Belief, ItemSeen, MoveSeen
from .prior import PriorBook, load_priors


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%" if x < 0.1 else f"{x * 100:.0f}%"


def _top(d: dict, n: int = 6) -> str:
    items = sorted(d.items(), key=lambda t: -t[1])[:n]
    return ", ".join(f"{k if k is not None else '(none)'} {_pct(v)}" for k, v in items)


def render(book: PriorBook, species: str, moves: List[str], items: List[str], abilities: List[str],
           top: int = 8, view: str = "project") -> str:
    slug = book.names.resolve(species)
    if slug is None:
        near = ", ".join(book.names.suggest(species)) or "nothing close"
        raise SystemExit(f"error: unknown species {species!r}. Did you mean: {near}?")
    prior = book.get(slug)
    if prior is None:
        raise SystemExit(f"error: no usage data for {slug}")
    b = Belief.from_prior(prior)
    for m in moves:
        b = b.condition(MoveSeen(m))
    for i in items:
        b = b.condition(ItemSeen(i))
    for a in abilities:
        b = b.condition(AbilitySeen(a))
    out = [f"{slug}  (source: {prior.source}, data as of {prior.as_of or 'unknown'})"]
    seen = [f"move {m}" for m in moves] + [f"item {i}" for i in items] + [f"ability {a}" for a in abilities]
    if seen:
        out.append("seen: " + ", ".join(seen) + f"   (prior probability of these: {_pct(b.evidence)})")
    if b.impossible:
        out.append("IMPOSSIBLE: " + b.notes[-1])
    for n in b.notes[:-1] if b.impossible else b.notes:
        out.append(f"note: {n}")
    arch = b.archetypes(k=top, view=view)
    out.append("")
    out.append(f"top {len(arch.items)} sets ({view} view; chances sum to {_pct(1 - arch.residual)}, the rest is spread over many rarer sets):")
    for n, (h, w) in enumerate(arch.items, 1):
        mega = f" -> {h.mega_form}" if h.mega_form else ""
        out.append(f"  {n:>2}. {_pct(w):>6}  {', '.join(h.moves) or '(no supported moves)'} | {h.item or '(none)'}{mega} | "
                   f"{h.ability} | {h.nature} {h.spread}")
    m = b.marginals()
    out += ["", "marginals:"]
    for field in ("moves", "items", "abilities", "natures", "spreads"):
        out.append(f"  {field:<10}{_top(m[field], 8 if field == 'moves' else 5)}")
    c = arch.coverage
    out += ["", "engine coverage of this belief:",
            f"  moves the engine models: {_pct(c.move_share)} of a set's moves (about {c.moves_dropped:.1f} per set are dropped in the project view)",
            f"  abilities modeled: {_pct(c.ability_share)}   items modeled: {_pct(c.item_share)} (none yet)",
            f"  sets fully simulable (strict view): {_pct(c.strict_mass)}",
            f"  sets left with NO simulable move (project view; such an opponent would do nothing): {_pct(c.empty_mass)}",
            f"  not listed by the source: moves {_pct(c.tail_moves) if c.tail_moves is not None else 'unknown'}, spreads {_pct(c.tail_spreads)}"]
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> None:
    p = argparse.ArgumentParser(prog="champions belief", description=__doc__.strip().splitlines()[0])
    p.add_argument("species")
    p.add_argument("--source", default="munchstats-doubles", help="usage snapshot '<site>-<format>' (default: munchstats-doubles)")
    p.add_argument("--top", type=int, default=8, help="how many sets to list")
    p.add_argument("--view", choices=["raw", "project", "strict"], default="project",
                   help="raw: as listed; project: unsupported moves removed; strict: only fully simulable sets")
    p.add_argument("--seen-move", action="append", default=[], metavar="MOVE")
    p.add_argument("--seen-item", action="append", default=[], metavar="ITEM")
    p.add_argument("--seen-ability", action="append", default=[], metavar="ABILITY")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)
    book = load_priors(source=args.source)
    for w in book.warnings:
        print(f"warning: {w}", file=sys.stderr)
    print(render(book, args.species, args.seen_move, args.seen_item, args.seen_ability, args.top, args.view))
