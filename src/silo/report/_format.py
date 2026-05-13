"""Tiny shared formatters used by both report renderers."""
from __future__ import annotations


def fmt_hours(v: float | None) -> str:
    return "—" if v is None else f"{v:.1f}h"


def fmt_lines(v: float | None) -> str:
    return "—" if v is None else f"{v:.0f}"


def fmt_pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.0f}%"


def fmt_int(v: int | None) -> str:
    return "—" if v is None else f"{v}"


def fmt_float(v: float | None, places: int = 2) -> str:
    return "—" if v is None else f"{v:.{places}f}"


def fmt_delta(before: float | None, after: float | None, places: int = 1, suffix: str = "") -> str:
    """Signed delta, or '—' if either side is missing."""
    if before is None or after is None:
        return "—"
    d = after - before
    sign = "+" if d > 0 else ("−" if d < 0 else "±")
    return f"{sign}{abs(d):.{places}f}{suffix}"


def fmt_delta_pct(before: float | None, after: float | None) -> str:
    """Relative delta as percentage points (works on 0..1 values)."""
    if before is None or after is None:
        return "—"
    d = (after - before) * 100
    sign = "+" if d > 0 else ("−" if d < 0 else "±")
    return f"{sign}{abs(d):.0f}pp"
