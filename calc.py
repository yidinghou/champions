#!/usr/bin/env python3
"""Damage calculator: level 50, Gen 9 formula, offline.

    python3 calc.py garchomp earthquake baxcalibur
    python3 calc.py garchomp earthquake baxcalibur --atk-nature jolly --atk-sp attack=32 \\
        --def-nature impish --def-sp hp=32,defense=32 --spread --item lifeorb
    python3 calc.py garchomp-mega-z dragonclaw salamence-mega --crit --boost 1

Prints the min-max damage over the 16 random rolls, as % of the defender's max HP, and hits to KO.
Modeled: STAB, type effectiveness, crit, spread (doubles), burn, stat stages, sun/rain, and the small
item/ability tables below. NOT modeled: terrain, screens, most abilities/items, multi-hit and
variable-power moves (base power is used as listed), Tera/Z-move effects. Check the notes line in
the output for what was applied. Not yet verified against in-game numbers.
"""
import argparse
import re
import sys

from lookup import find_forms, load, norm
from stats import level50

LEVEL = 50
# Moves whose attacking/defending stat differs from their category.
USES_DEFENSE_AS_ATTACK = {"bodypress"}
HITS_PHYSICAL_DEF = {"psyshock", "psystrike", "secretsword"}  # special moves that target Defense
# Attacker items: (multiplier, condition). Type-boost items (1.2x, e.g. Charcoal) are parsed from item text.
FLAT_ITEMS = {"lifeorb": 1.3, "musclebadge": 1.1, "muscleband": 1.1, "wiseglasses": 1.1}
CATEGORY_ITEMS = {"muscleband": "Physical", "wiseglasses": "Special", "choiceband": "Physical", "choicespecs": "Special"}
# Attacker abilities that double the Attack stat.
DOUBLE_ATTACK = {"huge-power", "pure-power"}


def pick_form(name, forms):
    hits = find_forms(name, forms)
    exact = [f for f in hits if f["name"] == name.lower()]
    if exact:
        return exact[0]
    if len(hits) == 1:
        return hits[0]
    sys.exit(f"{name!r} is ambiguous: {', '.join(f['name'] for f in hits[:8])}" if hits else f"no Pokémon matching {name!r}")


def parse_sp(text):
    if not text:
        return None
    try:
        return {k: int(v) for k, v in (p.split("=") for p in text.split(","))}
    except ValueError:
        sys.exit(f"bad SP {text!r}; expected e.g. attack=32,speed=32")


def stage(n):
    """Stat stage multiplier for stages -6..+6."""
    return (2 + n) / 2 if n >= 0 else 2 / (2 - n)


def type_multiplier(move_type, def_types, chart):
    m = 1
    for t in def_types:
        m *= chart[move_type][t.capitalize()]
    return m


def rolls(base_damage, modifiers):
    """Apply modifiers in game order with a floor after each step; returns the 16 random rolls."""
    out = []
    for r in range(85, 101):
        d = base_damage
        for name, mult in modifiers:
            if name == "random":
                d = d * r // 100
            else:
                d = int(d * mult)
        out.append(max(d, 1))
    return out


def calculate(att, move, dfn, chart, items, args):
    notes = []
    mid = norm(move["name"])
    cat = move["category"]
    if cat == "Status" or not move["base_power"]:
        sys.exit(f"{move['name']} has no fixed base power (status or variable-power move); not supported")
    power = move["base_power"]
    a_stats = level50(att["stats"], args.atk_nature, parse_sp(args.atk_sp))
    d_stats = level50(dfn["stats"], args.def_nature, parse_sp(args.def_sp))

    atk_key = "attack" if cat == "Physical" else "special-attack"
    if mid in USES_DEFENSE_AS_ATTACK:
        atk_key = "defense"
        notes.append("uses Defense as its attack stat")
    def_key = "defense" if cat == "Physical" or mid in HITS_PHYSICAL_DEF else "special-defense"

    A = int(a_stats[atk_key] * stage(args.boost))
    D = int(d_stats[def_key] * stage(args.def_boost))
    if args.ability in DOUBLE_ATTACK and cat == "Physical":
        A *= 2
        notes.append(f"{args.ability} doubles Attack")
    if args.ability == "technician" and power <= 60:
        power = int(power * 1.5)
        notes.append("Technician: power x1.5")

    base = (22 * power * A // D) // 50 + 2  # floor(2*50/5+2) = 22 at level 50

    mods = []
    if args.spread:
        mods.append(("spread", 0.75)); notes.append("spread x0.75")
    if args.weather:
        if args.weather == "sun" and move["type"] == "Fire" or args.weather == "rain" and move["type"] == "Water":
            mods.append(("weather", 1.5)); notes.append(f"{args.weather} x1.5")
        elif args.weather == "sun" and move["type"] == "Water" or args.weather == "rain" and move["type"] == "Fire":
            mods.append(("weather", 0.5)); notes.append(f"{args.weather} x0.5")
    if args.crit:
        mods.append(("crit", 1.5)); notes.append("crit x1.5")
    mods.append(("random", None))

    stab = 1
    if move["type"].lower() in att["types"]:
        stab = 2 if args.ability == "adaptability" else 1.5
        mods.append(("stab", stab)); notes.append(f"STAB x{stab}")
    eff = type_multiplier(move["type"], dfn["types"], chart)
    if args.def_ability == "levitate" and move["type"] == "Ground":
        eff = 0; notes.append("Levitate: immune to Ground")
    if args.def_ability == "thick-fat" and move["type"] in ("Fire", "Ice"):
        mods.append(("thickfat", 0.5)); notes.append("Thick Fat x0.5")
    mods.append(("effectiveness", eff))
    if args.burn and cat == "Physical":
        mods.append(("burn", 0.5)); notes.append("burn x0.5")

    if args.item:
        iid = norm(args.item)
        if iid not in items:
            sys.exit(f"unknown or illegal item {args.item!r}")
        need = CATEGORY_ITEMS.get(iid)
        desc = items[iid]["short_desc"] or ""
        boost = re.search(r"(\w+)-type attacks have 1\.2×", desc)
        if iid == "expertbelt":
            if eff > 1:
                mods.append(("item", 1.2)); notes.append("Expert Belt x1.2")
        elif boost and boost.group(1) == move["type"]:
            mods.append(("item", 1.2)); notes.append(f"{items[iid]['name']} x1.2")
        elif iid in FLAT_ITEMS and (need is None or need == cat):
            mods.append(("item", FLAT_ITEMS[iid])); notes.append(f"{items[iid]['name']} x{FLAT_ITEMS[iid]}")
        else:
            notes.append(f"{items[iid]['name']} has no effect here (or isn't modeled)")

    dmg = rolls(base, mods) if eff else [0] * 16
    return dmg, d_stats["hp"], notes, eff


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("attacker")
    ap.add_argument("move", help="move name, e.g. earthquake or 'dragon claw'")
    ap.add_argument("defender")
    ap.add_argument("--atk-nature", default="hardy")
    ap.add_argument("--atk-sp", help="attacker Stat Points, e.g. attack=32,speed=32")
    ap.add_argument("--def-nature", default="hardy")
    ap.add_argument("--def-sp", help="defender Stat Points, e.g. hp=32,defense=32")
    ap.add_argument("--boost", type=int, default=0, help="attacker offensive stat stage, -6..6")
    ap.add_argument("--def-boost", type=int, default=0, help="defender defensive stat stage, -6..6")
    ap.add_argument("--crit", action="store_true")
    ap.add_argument("--spread", action="store_true", help="move hits multiple targets in doubles (x0.75)")
    ap.add_argument("--burn", action="store_true", help="attacker is burned")
    ap.add_argument("--weather", choices=["sun", "rain"])
    ap.add_argument("--item", help="attacker's held item (see notes for which are modeled)")
    ap.add_argument("--ability", default="", help="attacker's ability slug, e.g. adaptability, huge-power, technician")
    ap.add_argument("--def-ability", default="", help="defender's ability slug, e.g. levitate, thick-fat")
    args = ap.parse_args()

    forms = load("champions.json")["pokemon"]
    moves = load("moves.json")["moves"]
    learnsets = load("learnsets.json")["learnsets"]
    chart = load("types.json")["chart"]
    items = load("items.json")["items"]

    att, dfn = pick_form(args.attacker, forms), pick_form(args.defender, forms)
    mid = norm(args.move)
    if mid not in moves:
        sys.exit(f"unknown move {args.move!r}")
    move = moves[mid]
    if mid not in learnsets.get(att["name"], []):
        print(f"warning: {att['name']} doesn't learn {move['name']} in Champions", file=sys.stderr)

    dmg, hp, notes, eff = calculate(att, move, dfn, chart, items, args)
    lo, hi = min(dmg), max(dmg)
    print(f"{att['name']} {move['name']} vs {dfn['name']}  ({move['type']}, {move['category']}, {move['base_power']} BP, x{eff:g} effective)")
    print(f"  {lo}-{hi} damage  ({lo / hp:.1%}-{hi / hp:.1%} of {hp} HP)")
    if hi:
        kos = [-(-hp // d) for d in dmg if d]  # hits to KO for each roll
        best, worst = min(kos), max(kos)
        line = f"hits to KO: {best}" if best == worst else f"hits to KO: {best}-{worst}"
        if best == 1:
            line += f"  ({sum(d >= hp for d in dmg)}/16 rolls OHKO)"
        print(f"  {line}")
    print(f"  rolls: {' '.join(map(str, dmg))}")
    if notes:
        print("  applied: " + "; ".join(notes))


if __name__ == "__main__":
    main()
