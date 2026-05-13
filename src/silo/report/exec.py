"""Exec report: team-level only, no per-person data, narrative-led."""
from __future__ import annotations

from pathlib import Path

from ..types import PeriodReport


def render(reports: list[PeriodReport], out_dir: Path) -> Path:
    """Single markdown file. Team-level metrics across all teams + period-over-period
    + cross-team comparisons (only on normalized metrics) + Claude narrative.
    Includes an explicit 'what this measures / does not measure' section."""
    raise NotImplementedError
