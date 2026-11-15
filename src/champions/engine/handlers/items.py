"""Item handlers. See engine/items.py for the hook each one uses."""
from .. import items
from ..actions import Switch
from ..hooks import on
from ..stages import change_stat


def _berry(name):
    def deco(fn):
        def wrapped(battle, mon):
            if mon.item == name and not mon.fainted and items.can_eat(battle, mon):
                fn(battle, mon)
        return on("on_update", f"item:{name}")(wrapped)
    return deco


def _herb_or_seed(name):
    def deco(fn):
        def wrapped(battle, mon):
            if mon.item == name and not mon.fainted:
                fn(battle, mon)
        return on("on_update", f"item:{name}")(wrapped)
    return deco


# --- berries that restore or cure ---
def _hp_berry(name, amount):
    @_berry(name)
    def eat(battle, mon):
        if mon.hp * 2 <= mon.max_hp:
            items.consume(battle, mon, cause="eat")
            mon.heal(amount(mon))


_hp_berry("sitrusberry", lambda m: max(1, m.max_hp // 4))
_hp_berry("oranberry", lambda m: 10)


def _status_berry(name, statuses):
    @_berry(name)
    def eat(battle, mon):
        if mon.status in statuses:
            items.consume(battle, mon, cause="eat")
            mon.cure_status()


for _n, _s in items.STATUS_BERRIES.items():
    _status_berry(_n, _s)


@_berry("lumberry")
def lum(battle, mon):
    if mon.status or "confusion" in mon.volatiles:
        items.consume(battle, mon, cause="eat")
        mon.cure_status()
        mon.remove_volatile("confusion")


@_berry("persimberry")
def persim(battle, mon):
    if "confusion" in mon.volatiles:
        items.consume(battle, mon, cause="eat")
        mon.remove_volatile("confusion")


@_berry("leppaberry")
def leppa(battle, mon):
    from ..teams import moves_data
    for mv in mon.moves:
        if mon.pp.get(mv, 1) == 0:
            items.consume(battle, mon, cause="eat", move=mv)
            mon.pp[mv] = min(moves_data()[mv]["pp"], 10)
            return


# --- herbs and seeds ---
@_herb_or_seed("whiteherb")
def white_herb(battle, mon):
    low = [k for k, v in mon.stages.items() if v < 0]
    if low:
        items.consume(battle, mon, cause="herb")
        for k in low:
            mon.stages[k] = 0


@_herb_or_seed("mentalherb")
def mental_herb(battle, mon):
    if any(v in mon.volatiles for v in items.MENTAL_HERB_CURES):
        items.consume(battle, mon, cause="herb")
        for v in items.MENTAL_HERB_CURES:
            mon.remove_volatile(v)


def _seed(name, terrain, stat):
    @_herb_or_seed(name)
    def pop(battle, mon):
        if battle.arena.get("terrain") == terrain:
            items.consume(battle, mon, cause="seed")
            change_stat(battle, mon, stat, 1, source=mon, cause="self")


for _n, (_t, _st) in items.SEEDS.items():
    _seed(_n, _t, _st)


# --- end of turn ---
@on("on_residual", "item:leftovers")
def leftovers(battle, mon):
    mon.heal(max(1, mon.max_hp // 16))


# --- when the holder is hit ---
@on("on_damaging_hit", "item:rockyhelmet")
def rocky_helmet(battle, ctx):
    if "contact" in ctx.move["flags"] and not ctx.user.fainted and not ctx.user.ability == "magicguard":
        ctx.user.take(max(1, ctx.user.max_hp // 6))


@on("on_damaging_hit", "item:airballoon")
def air_balloon(battle, ctx):
    items.consume(battle, ctx.current, cause="popped")


# --- when the holder hits ---
@on("on_user_hit", "item:kingsrock")
def kings_rock(battle, ctx):
    t = ctx.current
    if ctx.move["category"] == "Status" or t.fainted or t is ctx.user:
        return
    if any(s.get("volatile") == "flinch" for s in ctx.effects.get("secondary", ())):
        return                                    # it already has its own flinch chance
    if t.ref in battle.arena.get("moved", ()) or t.ability == "innerfocus":
        return
    if battle.rng.chance(10, "kingsrock"):
        t.add_volatile("flinch")


@on("on_after_all_hits", "item:shellbell")
def shell_bell(battle, ctx):
    total = ctx.dealt_total()
    if total > 0 and not ctx.user.fainted:
        ctx.user.heal(max(1, total // 8))


@on("on_after_all_hits", "item:lifeorb")
def life_orb(battle, ctx):
    if ctx.dealt_total() > 0 and not ctx.user.fainted and ctx.user.ability != "magicguard":
        ctx.user.take(max(1, ctx.user.max_hp // 10))


# --- after a hit the holder survived ---
def _slot(battle, mon):
    return battle.sides[mon.side].active.index(mon.idx)


@on("on_after_hit_target", "item:ejectbutton")
def eject_button(battle, ctx):
    from ..game import run_switch
    holder = ctx.current
    bench = items.switch_candidates(battle, holder)
    if holder.item == "ejectbutton" and bench and not holder.fainted:
        items.consume(battle, holder, cause="eject")
        run_switch(battle, Switch(holder.side, _slot(battle, holder), bench[0]))     # TODO(policy): the player picks


@on("on_after_hit_target", "item:redcard")
def red_card(battle, ctx):
    from ..game import run_switch
    holder, attacker = ctx.current, ctx.user
    if holder.item != "redcard" or attacker.fainted or attacker.side == holder.side:
        return
    if battle.sides[attacker.side].active.count(attacker.idx) == 0:
        return                                    # the attacker already left
    bench = items.switch_candidates(battle, attacker)
    if bench:
        items.consume(battle, holder, cause="red_card")
        run_switch(battle, Switch(attacker.side, _slot(battle, attacker), battle.rng.choice(bench, "redcard")))
