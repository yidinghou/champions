"""Damage calculator: level 50, Gen 9 formula, offline.

    champions calc garchomp earthquake baxcalibur
    champions calc garchomp earthquake baxcalibur --atk-nature jolly --atk-sp attack=32 \\
        --def-nature impish --def-sp hp=32,defense=32 --spread --item lifeorb
    champions calc garchomp-mega-z dragonclaw salamence-mega --crit --boost 1

Prints the min-max damage over the 16 random rolls, as % of the defender's max HP, and hits to KO.
Modeled: STAB, type effectiveness, crit, spread, burn, stat stages, sun/rain, terrain, screens, Helping Hand,
multi-hit moves (--hits), resist berries, and the item/ability tables below (flag-based power abilities like Tough
Claws, -ate abilities, type immunities, Multiscale/Filter/Fluffy/Fur Coat...), plus Knock Off, Facade, Acrobatics,
Electro Ball, Gyro Ball, Foul Play. NOT modeled: weight-based and HP-based variable-power moves, Sheer Force, most
other abilities/items, Tera/Z-move effects. Check the notes line in the output for what was applied.
Cases in data/damage_cases.json were checked against Pikalytics' Champions calculator (all 16 rolls each) or worked
by hand (source field); not yet checked against in-game damage.
"""
import argparse
import re
import sys

from .lookup import find_forms, load, norm
from .stats import level50

LEVEL = 50
# Moves whose attacking/defending stat differs from their category.
USES_DEFENSE_AS_ATTACK = {"bodypress"}
HITS_PHYSICAL_DEF = {"psyshock", "psystrike", "secretsword"}  # special moves that target Defense
# Modifiers are in 4096ths, like the game. Type-boost items (Charcoal etc., 4915) are parsed from item text.
# Life Orb and Expert Belt multiply final damage; Muscle Band / Wise Glasses multiply base power.
FINAL_ITEMS = {"lifeorb": 5324}
BP_ITEMS = {"muscleband": ("Physical", 4505), "wiseglasses": ("Special", 4505)}
TYPE_BOOST = 4915
# Attacker abilities that double the Attack stat.
DOUBLE_ATTACK = {"huge-power", "pure-power"}
# Attacker abilities that boost base power for moves carrying a Showdown flag: ability -> (flag, 4096ths).
FLAG_ABILITIES = {"tough-claws": ("contact", 5325), "iron-fist": ("punch", 4915), "strong-jaw": ("bite", 6144),
                  "sharpness": ("slicing", 6144), "mega-launcher": ("pulse", 6144), "punk-rock": ("sound", 5325)}
# Normal moves become this type and get x1.2 base power.
TYPE_CHANGERS = {"pixilate": "Fairy", "aerilate": "Flying", "refrigerate": "Ice"}
# Defender abilities that grant immunity to a move type.
IMMUNITY_ABILITIES = {"water-absorb": "Water", "dry-skin": "Water", "volt-absorb": "Electric", "motor-drive": "Electric",
                      "lightning-rod": "Electric", "flash-fire": "Fire", "sap-sipper": "Grass", "earth-eater": "Ground"}
# Defender abilities that scale final damage on super-effective hits / at full HP.
SUPER_EFFECTIVE_REDUCERS = {"filter", "solid-rock"}
FULL_HP_REDUCERS = {"multiscale"}
# Resist berries: item id -> type. Chilan (Normal) works without super effectiveness.
RESIST_BERRIES = {"occaberry": "Fire", "passhoberry": "Water", "wacanberry": "Electric", "rindoberry": "Grass",
                  "yacheberry": "Ice", "chopleberry": "Fighting", "kebiaberry": "Poison", "shucaberry": "Ground",
                  "cobaberry": "Flying", "payapaberry": "Psychic", "tangaberry": "Bug", "chartiberry": "Rock",
                  "kasibberry": "Ghost", "habanberry": "Dragon", "colburberry": "Dark", "babiriberry": "Steel",
                  "roseliberry": "Fairy", "chilanberry": "Normal"}
TERRAIN_TYPE = {"electric": "Electric", "grassy": "Grass", "psychic": "Psychic"}
TERRAIN_HALVED = {"grassy": {"earthquake", "bulldoze", "magnitude"}}


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


def poke_round(value, num):
    """value * num / 4096 rounded half down, as the game does for modifiers."""
    q, r = divmod(value * num, 4096)
    return q + 1 if r > 2048 else q


def chain(mods, start=4096):
    """Combine 4096ths modifiers the way Showdown's chainModify does (one rounding, applied once)."""
    m = start
    for x in mods:
        m = (m * x + 2048) >> 12
    return m


def rolls(base_damage, modifiers):
    """Apply modifiers in game order; returns the 16 random rolls.
    modifiers: (name, value) pairs. random splits the 16 rolls; crit floors x1.5; effectiveness and
    burn floor; everything else (spread, weather, stab, item) is a 4096ths modifier with poke_round."""
    out = []
    for r in range(85, 101):
        d = base_damage
        for name, val in modifiers:
            if name == "random":
                d = d * r // 100
            elif name == "crit":
                d = d * 3 // 2
            elif name == "effectiveness":
                d = int(d * val)
            elif name == "burn":
                d //= 2
            else:
                d = poke_round(d, val)
        out.append(max(d, 1))
    return out


def grounded(mon, ability, item):
    return "flying" not in mon["types"] and ability != "levitate" and item != "airballoon"


def multihit_count(move, args):
    """Number of hits: --hits if given, else the fixed count, 5 with Skill Link, 3 for 2-5 hit moves."""
    mh = move.get("multihit")
    if not mh:
        return 1
    if isinstance(mh, int):
        return args.hits or mh
    return args.hits or (mh[1] if args.ability == "skill-link" else 3)


def calculate(att, move, dfn, chart, items, args):
    notes = []
    mid = norm(move["name"])
    cat = move["category"]
    flags = set(move.get("flags") or [])
    power = move["base_power"]
    mtype = move["type"]
    a_stats = level50(att["stats"], args.atk_nature, parse_sp(args.atk_sp))
    d_stats = level50(dfn["stats"], args.def_nature, parse_sp(args.def_sp))

    if mid == "electroball":
        ratio = a_stats["speed"] / d_stats["speed"]
        power = 150 if ratio >= 4 else 120 if ratio >= 3 else 80 if ratio >= 2 else 60 if ratio >= 1 else 40
        notes.append(f"Electro Ball: {power} BP from speed {a_stats['speed']} vs {d_stats['speed']}")
    elif mid == "gyroball":
        power = min(150, 25 * d_stats["speed"] // a_stats["speed"] + 1)
        notes.append(f"Gyro Ball: {power} BP from speed {a_stats['speed']} vs {d_stats['speed']}")
    if cat == "Status" or not power:
        sys.exit(f"{move['name']} has no fixed base power (status or variable-power move); not supported")

    if args.ability in TYPE_CHANGERS and mtype == "Normal":
        mtype = TYPE_CHANGERS[args.ability]
        notes.append(f"{args.ability.capitalize()}: Normal move becomes {mtype}, power x1.2")

    atk_key = "attack" if cat == "Physical" else "special-attack"
    if mid in USES_DEFENSE_AS_ATTACK:
        atk_key = "defense"
        notes.append("uses Defense as its attack stat")
    def_key = "defense" if cat == "Physical" or mid in HITS_PHYSICAL_DEF else "special-defense"

    if mid == "foulplay":
        A = d_stats["attack"]
        notes.append("Foul Play: uses the defender's Attack")
    else:
        A = int(a_stats[atk_key] * stage(args.boost))
    D = int(d_stats[def_key] * stage(args.def_boost))
    if args.def_ability == "fur-coat" and def_key == "defense":
        D *= 2
        notes.append("Fur Coat: Defense x2")

    a_mods = []  # attack-stat modifiers, chained
    if args.ability in DOUBLE_ATTACK and cat == "Physical":
        a_mods.append(8192)
        notes.append(f"{args.ability} doubles Attack")
    if args.def_ability == "thick-fat" and mtype in ("Fire", "Ice"):
        a_mods.append(2048); notes.append("Thick Fat: attack x0.5")
    if args.def_ability == "heatproof" and mtype == "Fire":
        a_mods.append(2048); notes.append("Heatproof: attack x0.5")
    if args.def_ability == "purifying-salt" and mtype == "Ghost":
        a_mods.append(2048); notes.append("Purifying Salt: attack x0.5")
    if a_mods:
        A = poke_round(A, chain(a_mods))

    eff = type_multiplier(mtype, dfn["types"], chart)
    immune = {"levitate": "Ground", **IMMUNITY_ABILITIES}.get(args.def_ability)
    if immune == mtype:
        eff = 0; notes.append(f"{args.def_ability}: immune to {mtype}")

    bp_mods = []
    if args.ability == "technician" and power <= 60:
        bp_mods.append(6144); notes.append("Technician: power x1.5")
    if args.ability in FLAG_ABILITIES and FLAG_ABILITIES[args.ability][0] in flags:
        bp_mods.append(FLAG_ABILITIES[args.ability][1]); notes.append(f"{args.ability}: power x{FLAG_ABILITIES[args.ability][1] / 4096:.2g}")
    if args.ability in TYPE_CHANGERS and move["type"] == "Normal":
        bp_mods.append(TYPE_BOOST)
    if mid == "knockoff" and args.def_item:
        bp_mods.append(6144); notes.append("Knock Off: power x1.5 (target holds an item)")
    if mid == "facade" and args.burn:
        bp_mods.append(8192); notes.append("Facade: power x2 (burned)")
    if mid == "acrobatics" and not args.item:
        bp_mods.append(8192); notes.append("Acrobatics: power x2 (no item)")
    if args.helping_hand:
        bp_mods.append(6144); notes.append("Helping Hand: power x1.5")
    if args.terrain:
        if TERRAIN_TYPE.get(args.terrain) == mtype and grounded(att, args.ability, args.item):
            bp_mods.append(5325); notes.append(f"{args.terrain} terrain: power x1.3")
        g_def = grounded(dfn, args.def_ability, args.def_item)
        if g_def and (args.terrain == "misty" and mtype == "Dragon" or mid in TERRAIN_HALVED.get(args.terrain, ())):
            bp_mods.append(2048); notes.append(f"{args.terrain} terrain: power x0.5")

    final_mods = []  # chained into one modifier applied after burn
    if args.item:
        iid = norm(args.item)
        if iid not in items:
            sys.exit(f"unknown or illegal item {args.item!r}")
        iname = items[iid]["name"]
        boost = re.search(r"(\w+)-type attacks have 1\.2×", items[iid]["short_desc"] or "")
        if iid == "expertbelt":
            if eff > 1:
                final_mods.append(4915); notes.append("Expert Belt x1.2")
        elif boost and boost.group(1) == mtype:
            bp_mods.append(TYPE_BOOST); notes.append(f"{iname}: power x1.2")
        elif iid in BP_ITEMS and BP_ITEMS[iid][0] == cat:
            bp_mods.append(BP_ITEMS[iid][1]); notes.append(f"{iname}: power x1.1")
        elif iid in FINAL_ITEMS:
            final_mods.append(FINAL_ITEMS[iid]); notes.append(f"{iname} x{FINAL_ITEMS[iid] / 4096:.1f}")
        else:
            notes.append(f"{iname} has no effect here (or isn't modeled)")
    if args.def_item:
        did = norm(args.def_item)
        if did not in items:
            sys.exit(f"unknown or illegal item {args.def_item!r}")
        if RESIST_BERRIES.get(did) == mtype and (eff > 1 or did == "chilanberry"):
            final_mods.append(2048); notes.append(f"{items[did]['name']}: x0.5")
    if args.def_ability in SUPER_EFFECTIVE_REDUCERS and eff > 1:
        final_mods.append(3072); notes.append(f"{args.def_ability}: x0.75")
    if args.def_ability in FULL_HP_REDUCERS:
        final_mods.append(2048); notes.append(f"{args.def_ability}: x0.5 (assumes full HP)")
    if args.def_ability == "fluffy":
        if "contact" in flags:
            final_mods.append(2048); notes.append("Fluffy: contact x0.5")
        if mtype == "Fire":
            final_mods.append(8192); notes.append("Fluffy: Fire x2")
    if args.screen and not args.crit:
        final_mods.append(2732 if args.doubles or args.spread else 2048)
        notes.append(f"screen x{final_mods[-1] / 4096:.2f}")

    hits = multihit_count(move, args)
    total = [0] * 16
    for i in range(hits):
        hit_power = 20 * (i + 1) if mid == "tripleaxel" else power
        hit_power = max(1, poke_round(hit_power, chain(bp_mods)))
        base = (22 * hit_power * A // D) // 50 + 2  # floor(2*50/5+2) = 22 at level 50

        mods = []
        if args.spread:
            mods.append(("spread", 3072))
        if args.weather:
            if args.weather == "sun" and mtype == "Fire" or args.weather == "rain" and mtype == "Water":
                mods.append(("weather", 6144))
            elif args.weather == "sun" and mtype == "Water" or args.weather == "rain" and mtype == "Fire":
                mods.append(("weather", 2048))
        if args.crit:
            mods.append(("crit", None))
        mods.append(("random", None))
        if mtype.lower() in att["types"]:
            mods.append(("stab", 8192 if args.ability == "adaptability" else 6144))
        mods.append(("effectiveness", eff))
        if args.burn and cat == "Physical" and mid != "facade":
            mods.append(("burn", None))
        if final_mods:
            mods.append(("final", chain(final_mods)))
        hit = rolls(base, mods) if eff else [0] * 16
        total = [t + h for t, h in zip(total, hit)]
        if i == 0:  # notes that don't depend on the hit index
            if args.spread: notes.append("spread x0.75")
            if args.weather and any(m[0] == "weather" for m in mods): notes.append(f"{args.weather} x{dict(mods)['weather'] / 4096:g}")
            if args.crit: notes.append("crit x1.5")
            if mtype.lower() in att["types"]: notes.append(f"STAB x{dict(mods)['stab'] / 4096:g}")
            if args.burn and cat == "Physical" and mid != "facade": notes.append("burn x0.5")
    if hits > 1:
        notes.append(f"{hits} hits (each hit uses the same random roll)")
    return total, d_stats["hp"], notes, eff


def damage(attacker, move, defender, **opts):
    """Programmatic entry point (used by tests). opts mirror the CLI flags with underscores:
    atk_nature, atk_sp, def_nature, def_sp, boost, def_boost, crit, spread, burn, weather, item,
    ability, def_ability, def_item, helping_hand, terrain, screen, doubles, hits. Returns (rolls, defender_hp, notes, type_effectiveness)."""
    args = argparse.Namespace(atk_nature="hardy", atk_sp=None, def_nature="hardy", def_sp=None, boost=0,
                              def_boost=0, crit=False, spread=False, burn=False, weather=None, item=None,
                              ability="", def_ability="", def_item=None, helping_hand=False, terrain=None,
                              screen=False, doubles=False, hits=0)
    unknown = set(opts) - set(vars(args))
    if unknown:
        raise TypeError(f"unknown option(s): {', '.join(sorted(unknown))}")
    vars(args).update(opts)
    forms = load("champions.json")["pokemon"]
    return calculate(pick_form(attacker, forms), load("moves.json")["moves"][norm(move)],
                     pick_form(defender, forms), load("types.json")["chart"], load("items.json")["items"], args)


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
    ap.add_argument("--def-ability", default="", help="defender's ability slug, e.g. levitate, thick-fat, multiscale")
    ap.add_argument("--def-item", help="defender's held item (resist berries; Knock Off checks for any item)")
    ap.add_argument("--helping-hand", action="store_true", help="an ally used Helping Hand (power x1.5)")
    ap.add_argument("--terrain", choices=["electric", "grassy", "psychic", "misty"])
    ap.add_argument("--screen", action="store_true", help="the defender's side has the matching screen (Reflect/Light Screen/Aurora Veil)")
    ap.add_argument("--doubles", action="store_true", help="doubles battle (screens x2/3 instead of x1/2; --spread implies it)")
    ap.add_argument("--hits", type=int, default=0, help="hit count for multi-hit moves (default: fixed count, else 3; 5 with Skill Link)")
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
