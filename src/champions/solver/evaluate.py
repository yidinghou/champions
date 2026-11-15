"""Score a battle from side 0's view, -1..1."""


def evaluate(b):
    """Win or loss is exact (+1/-1, draw 0). Otherwise the difference in average team HP fraction.
    Ignores status, stat stages and field effects (a known limit)."""
    if b.winner is not None:
        return 0.0 if b.winner == -1 else (1.0 if b.winner == 0 else -1.0)
    frac = [sum(m.hp / m.max_hp for m in s.team) / len(s.team) for s in b.sides]
    return frac[0] - frac[1]
