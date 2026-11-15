"""Stage 3: Protect-style block. Moves with the protect flag are stopped for a protected target, and Wide Guard and
Quick Guard stop spread and priority moves aimed at their side."""
from ...calc.abilities import breaks  # noqa: F401  (Mold Breaker does not get past Protect)
from ..stages import change_stat
from ..status import try_set_status
from ..teams import moves_data

SPREAD_KINDS = ("allAdjacentFoes", "allAdjacent")


def _contact_effect(ctx, shield, target):
    """What a Spiky Shield, Baneful Bunker or King's Shield does to a contact attacker."""
    user, b = ctx.user, ctx.battle
    if "contact" not in ctx.move["flags"] or user.fainted:
        return
    if shield == "spikyshield":
        user.take(max(1, user.max_hp // 8))
    elif shield == "banefulbunker":
        try_set_status(b, user, "psn", target, ctx.move_id, announce=False)
    elif shield == "kingsshield":
        change_stat(b, user, "atk", -1, source=target, cause="foe")


def check(ctx):
    move, b = ctx.move, ctx.battle
    kept = []
    natural = moves_data()[ctx.move_id]["priority"]
    for t in ctx.targets:
        if t is ctx.user:
            kept.append(t)
            continue
        guards = b.sides[t.side].conditions
        if guards.get("wideguard") and move["target"] in SPREAD_KINDS:
            b.log_event("protected", mon=t.ref, move=ctx.move_id, by="wideguard")
        elif guards.get("quickguard") and natural > 0:
            b.log_event("protected", mon=t.ref, move=ctx.move_id, by="quickguard")
        else:
            kept.append(t)
    ctx.targets = kept
    if "protect" not in move["flags"]:
        return
    if ctx.user.ability in ("unseenfist", "piercingdrill") and "contact" in move["flags"]:
        return                                    # contact moves go through Protect
    kept = []
    for t in ctx.targets:
        shield = t.volatiles.get("protect")
        if t is ctx.user or not shield:
            kept.append(t)
        elif shield == "kingsshield" and move["category"] == "Status":
            kept.append(t)                        # King's Shield lets status moves through
        else:
            b.log_event("protected", mon=t.ref, move=ctx.move_id, by=shield if isinstance(shield, str) else "protect")
            _contact_effect(ctx, shield, t)
    ctx.targets = kept
