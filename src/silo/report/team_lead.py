"""Team-lead report: per-person detail + team metrics + Claude narrative."""
from __future__ import annotations

from pathlib import Path

from ..types import PeriodReport


def render(reports: list[PeriodReport], out_dir: Path) -> Path:
    """One markdown file per team. Includes per-person table + team metrics +
    period-over-period delta + narrative paragraphs from Claude."""
    raise NotImplementedError
