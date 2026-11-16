"""Joint actions: one choice per active slot, for a whole side."""
import itertools

from ..engine import game
from ..engine.actions import Move, Switch
from ..engine.teams import moves_data

CHOOSES_TARGET = {"normal", "any"}     # the other target kinds (self, spread, field) ignore the chosen target


def slot_choices(battle, side):
    """{slot: [choices]}: legal_choices without the duplicates. The engine lists a move once per foe even when
    the move hits no chosen target (self, spread, field), so those collapse to one choice."""
    per_slot, seen = {}, set()
    for c in game.legal_choices(battle, side):
        if isinstance(c, Move) and moves_data()[c.move]["target"] not in CHOOSES_TARGET:
            key = (c.slot, c.move, c.mega)
            if key in seen:
                continue
            seen.add(key)
        per_slot.setdefault(c.slot, []).append(c)
    return per_slot


def _two_megas(combo):
    """A side may Mega Evolve only one Pokemon per turn."""
    return sum(1 for c in combo if isinstance(c, Move) and c.mega) > 1


def joint_actions(battle, side):
    """Every legal combination of per-slot choices for `side` (two slots may not switch to the same mon)."""
    per_slot = slot_choices(battle, side)
    out = []
    for combo in itertools.product(*per_slot.values()):
        targets = [c.to for c in combo if isinstance(c, Switch)]
        if len(targets) != len(set(targets)) or _two_megas(combo):
            continue
        out.append(list(combo))
    return out


def _name(species, base_names):
    """Display name; with base_names a Mega form shows as its base species (labels that must match across games)."""
    if base_names:
        from ..belief.reference import species_table
        species = species_table().get(species, {}).get("species", species)
    return species.title()


def describe(battle, combo, base_names=False):
    """Readable label for a joint action. One slot: 'earthquake'. Two slots: 'Garchomp earthquake + Incineroar fakeout->Gengar'
    (names are added only when needed to tell the slots apart, targets only when there is a choice of foe)."""
    parts = []
    for c in combo:
        mon = battle.sides[c.side].mon_at(c.slot)
        name = _name(mon.species, base_names) + " " if len(combo) > 1 else ""
        if isinstance(c, Switch):
            parts.append(f"{name}switch to {battle.sides[c.side].team[c.to].species.title()}")
            continue
        text = c.move
        if moves_data()[c.move]["target"] in CHOOSES_TARGET and len(battle.sides[1 - c.side].alive_active()) > 1:
            foe = battle.mon(*c.target)
            text += "->" + (_name(foe.species, base_names) if foe else "?")
        parts.append(name + text)
    return " + ".join(parts)
