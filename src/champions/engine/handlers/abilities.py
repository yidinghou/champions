"""Abilities that react to a hit, an entry or the end of the turn: Trace, Thermal Exchange, Spicy Spray."""
from ..game_hooks import copyable
from ..hooks import on
from ..stages import change_stat
from ..status import try_set_status


@on("on_damaging_hit", "ability:thermalexchange")
def thermal_exchange(battle, ctx):
    if ctx.move["type"] == "Fire":
        change_stat(battle, ctx.current, "atk", 1, source=ctx.current, cause="self")


@on("on_damaging_hit", "ability:spicyspray")
def spicy_spray(battle, ctx):
    if not ctx.user.fainted:
        try_set_status(battle, ctx.user, "brn", ctx.current, ctx.move_id, announce=False)


@on("on_switch_in", "ability:trace")
def trace(battle, mon):
    """Copy a random foe's ability (not Trace itself), and start it as if it had just entered."""
    from ..game import send_in_ability
    foes = [f for _, f in battle.sides[1 - mon.side].alive_active() if copyable(f.ability)]
    if not foes:
        return
    foe = battle.rng.choice(foes, "trace")
    mon.ability = foe.ability
    battle.log_event("ability", mon=mon.ref, ability=mon.ability, copied_from=foe.ref)
    send_in_ability(battle, mon)
