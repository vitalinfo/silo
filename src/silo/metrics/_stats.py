"""Tiny shared stats helpers used by metric modules."""
from __future__ import annotations


def percentile(values: list[float], p: float) -> float | None:
    """Linear-interpolation percentile (p in 0..100). Returns None for empty input."""
    if not values:
        return None
    if not 0 <= p <= 100:
        raise ValueError(f"percentile must be in [0, 100], got {p}")
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    rank = (p / 100) * (len(s) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(s) - 1)
    frac = rank - lo
    return float(s[lo] + (s[hi] - s[lo]) * frac)
