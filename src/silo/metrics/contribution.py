"""Contribution distribution: Gini coefficient."""
from __future__ import annotations


def gini(values: list[float]) -> float | None:
    """Gini coefficient.

    0 = perfectly even, 1 = fully concentrated in one person.
    Returns None if input is empty or all-zero (concentration undefined).

    Uses the standard sorted formula:
        G = (2 * sum_i(i * x_i)) / (n * sum(x_i)) - (n + 1) / n
    where x_i is the i-th smallest value (1-indexed).
    """
    if not values:
        return None
    if any(v < 0 for v in values):
        raise ValueError("gini: values must be non-negative")
    s = sorted(values)
    total = sum(s)
    if total == 0:
        return None
    n = len(s)
    weighted = sum((i + 1) * x for i, x in enumerate(s))
    return (2 * weighted) / (n * total) - (n + 1) / n
