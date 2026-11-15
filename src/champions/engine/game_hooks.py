"""Small shared rules for abilities that copy or swap."""
UNCOPYABLE = frozenset({"trace", "noability", "forecast", "multitype", "imposter"})


def copyable(ability):
    return ability not in UNCOPYABLE
