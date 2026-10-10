"""Which moves the engine models. Anything else is rejected up front (and hidden from the UI), so an
unmodeled move can never silently do the wrong thing. Each new mechanic adds to these constants."""
from functools import lru_cache

from ..calc import damage
from ..lookup import load

STATUS_MOVES = {"protect", "trickroom", "tailwind"}
SINGLE_TARGET = {"normal", "any", "adjacentFoe"}  # self-hit and random-target moves are not modeled yet
SPREAD = {"allAdjacentFoes", "allAdjacent"}  # no target choice; allAdjacent also hits the user's ally
FIRST_TURN_ONLY = {"fakeout", "firstimpression"}  # fail unless it is the user's first turn out
FLINCHES = {"fakeout"}


@lru_cache(maxsize=None)
def all_moves():
    return load("moves.json")["moves"]


@lru_cache(maxsize=None)
def is_supported(move_id):
    """Plain damaging single-target and spread moves (secondary effects ignored), plus the status moves in STATUS_MOVES.
    Charge and recharge moves are excluded until weather/charging exists; variable-power moves only if calc handles them."""
    mv = all_moves().get(move_id)
    if mv is None:
        return False
    if mv["category"] == "Status":
        return move_id in STATUS_MOVES
    if mv["target"] not in SINGLE_TARGET | SPREAD or {"charge", "recharge"} & set(mv["flags"]):
        return False
    if not mv["base_power"]:
        try:
            damage("garchomp", move_id, "incineroar")
        except (SystemExit, Exception):
            return False
    return True
