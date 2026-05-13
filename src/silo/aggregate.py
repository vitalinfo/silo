"""Pipeline: collectors -> raw records -> per-person & per-team metrics."""
from __future__ import annotations

from .collectors.calendar import CalendarCollector
from .collectors.github import GitHubCollector
from .config import Period, RunConfig, Team
from .types import PeriodReport


def build_period_report(
    team: Team,
    period: Period,
    run_cfg: RunConfig,
    gh: GitHubCollector,
    cal: CalendarCollector,
) -> PeriodReport:
    """Collect raw records for one (team, period), compute metrics, return PeriodReport."""
    raise NotImplementedError
