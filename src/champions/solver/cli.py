"""champions recommend --mine team.json --opp a,b,c,d,e,f --leads a,b [--seen species:move:Name] ...

Recommend a mix of actions for your leads against an opponent whose sets are only partly known: opposing teams are
sampled from the usage-data belief (narrowed by anything --seen), each is played out, and one strategy is chosen
that does well on average across them.
"""
import argparse
import json
import sys
from typing import List, Optional

from ..belief import AbilitySeen, ItemSeen, MoveSeen, TeamBelief, load_priors
from ..belief.reference import species_table
from .recommend import Recommendation, recommend

SEEN = {"move": MoveSeen, "item": ItemSeen, "ability": AbilitySeen}


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%" if x < 0.1 else f"{x * 100:.0f}%"


def _sgn(x: float) -> str:
    return ("+" if x >= 0 else "-") + f"{abs(x):.2f}"


def _team_line(team: List[dict], n_leads: int) -> str:
    return " + ".join(f"{species_table()[s['species']]['species']} [{', '.join(s['moves']) or 'no simulable move'}]"
                      for s in team[:n_leads])


def render(rec: Recommendation, n_leads: int, top: int = 8) -> str:
    out = [f"Recommended play: expected score {_sgn(rec.value)} for you (range -1..+1, 0 = even), "
           f"averaged over {len(rec.teams)} sampled opposing teams.", ""]
    order = sorted(range(len(rec.rows)), key=lambda i: -rec.strategy[i])
    out.append("mix over your joint actions:")
    for i in order[:top]:
        if rec.strategy[i] < 0.005:
            break
        out.append(f"  {_pct(rec.strategy[i]):>6}  {rec.rows[i]}")
    hidden = sum(1 for p in rec.strategy if p >= 0.005) - top
    if hidden > 0:
        out.append(f"  ... and {hidden} more with smaller shares")
    out += ["", "against each sampled opponent (their lead sets; chance of that team):"]
    for k in sorted(range(len(rec.teams)), key=lambda k: -rec.weights[k]):
        out.append(f"  {_pct(rec.weights[k]):>6}  {_team_line(rec.teams[k], n_leads)}")
        out.append(f"          this mix scores {_sgn(rec.sample_values[k])}; knowing exactly this set you could get {_sgn(rec.sample_best[k])}")
    out += ["", f"value of knowing the opponent's set: {_sgn(rec.value_of_information)} on average",
            f"(averaging each game's own best answer instead would score {_sgn(rec.fused_value)}, "
            f"vs {_sgn(rec.value)} for the mix above)"]
    for n in rec.notes:
        out.append(f"note: {n}")
    out.append(f"[{len(rec.rows)} candidate actions, {rec.cells:,} cells resolved, {rec.seconds:.1f}s. "
               f"Sampling means this is an estimate; --samples N steadies it.]")
    return "\n".join(out)


def _parse_seen(text: str):
    try:
        species, kind, value = text.split(":", 2)
        return species, SEEN[kind](value)
    except (ValueError, KeyError):
        raise SystemExit(f"error: --seen wants species:move|item|ability:Name, got {text!r}")


def main(argv: Optional[List[str]] = None) -> None:
    p = argparse.ArgumentParser(prog="champions recommend", description=__doc__.strip().splitlines()[0])
    p.add_argument("--mine", required=True, help="JSON file: your team as a list of engine specs (leads first)")
    p.add_argument("--opp", required=True, help="comma-separated opposing team preview (6 species)")
    p.add_argument("--leads", required=True, help="comma-separated opposing leads (2 for doubles, 1 for singles)")
    p.add_argument("--seen", action="append", default=[], metavar="SPECIES:KIND:NAME",
                   help="something revealed, e.g. garchomp:move:Earthquake (repeatable; kind = move|item|ability)")
    p.add_argument("--format", choices=["doubles", "singles"], default="doubles")
    p.add_argument("--samples", type=int, default=8, help="opposing teams to sample (default 8)")
    p.add_argument("--depth", type=int, default=1, help="turns to look ahead (default 1; 2 is much slower)")
    p.add_argument("--moves", type=int, default=2, help="damaging moves considered per Pokemon (default 2)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--source", default="munchstats-doubles", help="usage snapshot '<site>-<format>'")
    p.add_argument("--require-moves", action="store_true",
                   help="resample opposing Pokemon that would otherwise have no simulable move (biases toward modeled species)")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)

    slots, bring = (2, 4) if args.format == "doubles" else (1, 3)
    try:
        spec = json.load(open(args.mine))
        mine = spec["team"] if isinstance(spec, dict) else spec
    except (OSError, ValueError, KeyError) as e:
        raise SystemExit(f"error: cannot read your team from {args.mine}: {e}")
    leads = [s.strip() for s in args.leads.split(",") if s.strip()]
    if len(leads) != slots:
        raise SystemExit(f"error: {args.format} needs {slots} opposing lead(s), got {len(leads)}")
    book = load_priors(source=args.source)
    for w in book.warnings:
        print(f"warning: {w}", file=sys.stderr)
    try:
        tb = TeamBelief.from_preview([s.strip() for s in args.opp.split(",")], book, leads=leads, bring=bring)
        for text in args.seen:
            species, obs = _parse_seen(text)
            slug = book.names.resolve(species)
            if slug is None:
                raise SystemExit(f"error: unknown species {species!r} in --seen")
            tb = tb.condition(slug, obs)
            if tb.beliefs[slug].impossible:
                print(f"warning: {text}: {tb.beliefs[slug].notes[-1]}", file=sys.stderr)
        rec = recommend(mine, tb, n_samples=args.samples, depth=args.depth, seed=args.seed, moves=args.moves,
                        format=args.format, require_moves=args.require_moves)
    except ValueError as e:
        raise SystemExit(f"error: {e}")
    print(render(rec, slots))
