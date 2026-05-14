"""Collectors -> raw records -> PersonMetrics + TeamMetrics -> PeriodReport.

v1 scope note: team review-health metrics (latency, concentration, % substantive)
are computed from reviews authored by team members only. Reviews by people
outside the team on the team's PRs are not collected and therefore not counted.
This is documented in the exec-report disclaimer.
"""
from __future__ import annotations

from statistics import mean

from .collectors.calendar import CalendarCollector
from .collectors.github import GitHubCollector
from .config import Period, RunConfig, Team
from .metrics._stats import percentile
from .metrics.contribution import gini
from .metrics.flow import pr_cycle_time_hours, pr_sizes_lines, time_to_first_review_hours
from .metrics.load import (
    after_hours_busy_per_week,
    focus_block_hours_per_week,
    fragmentation_score,
    meeting_hours_per_week,
    partition_all_day,
)
from .metrics.review_health import (
    pct_prs_with_substantive_review,
    review_latency_hours,
    reviewer_concentration,
)
from .types import PeriodReport, PersonMetrics, RawPeriodData, TeamMetrics


def build_period_report(
    team: Team,
    period: Period,
    run_cfg: RunConfig,
    gh: GitHubCollector,
    cal: CalendarCollector,
) -> PeriodReport:
    wh = run_cfg.work_hours
    frm, to = period.from_, period.to

    # Per-person collection. Calendar blocks are partitioned into regular meetings
    # vs all-day events (PTO / OOO / holidays / offsites) so load metrics ignore PTO.
    per_person: list[tuple] = []  # (member, prs, reviews, comments, regular_blocks, all_day_blocks)
    for m in team.members:
        prs = gh.prs_authored(m.github, frm, to)
        reviews = gh.reviews_given(m.github, frm, to)
        comments = gh.comments_left(m.github, frm, to)
        if m.google:
            regular_blocks, all_day_blocks = partition_all_day(
                cal.busy_blocks(m.google, frm, to), m.zoneinfo
            )
        else:
            # Bots / service accounts have no calendar.
            regular_blocks, all_day_blocks = [], []
        per_person.append((m, prs, reviews, comments, regular_blocks, all_day_blocks))

    # Per-person metrics
    person_metrics: list[PersonMetrics] = []
    for m, prs, reviews, comments, blocks, _all_day in per_person:
        cycle = pr_cycle_time_hours(prs)
        ttfr = time_to_first_review_hours(prs, reviews)  # reviews given to author's PRs
        sizes = pr_sizes_lines(prs)
        # Calendar-derived metrics are None (not 0) for members without a calendar,
        # so they don't drag down team averages by pretending they have 0 meetings.
        has_calendar = m.google is not None
        person_metrics.append(
            PersonMetrics(
                github=m.github,
                google=m.google,
                prs_authored=len(prs),
                prs_reviewed=len(reviews),
                comments_left=len(comments),
                pr_cycle_time_p50_hours=percentile(cycle, 50),
                pr_cycle_time_p90_hours=percentile(cycle, 90),
                time_to_first_review_p50_hours=percentile(ttfr, 50),
                pr_size_p50_lines=percentile(sizes, 50),
                pr_size_p90_lines=percentile(sizes, 90),
                meeting_hours_per_week=meeting_hours_per_week(blocks, wh, m.zoneinfo, frm, to) if has_calendar else None,
                focus_block_hours_per_week=focus_block_hours_per_week(blocks, wh, m.zoneinfo, frm, to) if has_calendar else None,
                fragmentation_score=fragmentation_score(blocks, wh, m.zoneinfo, frm, to) if has_calendar else None,
                after_hours_busy_per_week=after_hours_busy_per_week(blocks, wh, m.zoneinfo, frm, to) if has_calendar else None,
            )
        )

    # Team-level pools
    all_team_prs = [pr for _, prs, _, _, _, _ in per_person for pr in prs]
    all_team_reviews = [r for _, _, revs, _, _, _ in per_person for r in revs]

    team_cycle = pr_cycle_time_hours(all_team_prs)
    team_ttfr = time_to_first_review_hours(all_team_prs, all_team_reviews)
    team_sizes = pr_sizes_lines(all_team_prs)
    team_latency = review_latency_hours(all_team_prs, all_team_reviews)

    contribution_values = [
        float(pm.prs_authored + pm.prs_reviewed + pm.comments_left) for pm in person_metrics
    ]

    team_metrics = TeamMetrics(
        team=team.name,
        pr_cycle_time_p50_hours=percentile(team_cycle, 50),
        pr_cycle_time_p90_hours=percentile(team_cycle, 90),
        time_to_first_review_p50_hours=percentile(team_ttfr, 50),
        pr_size_p50_lines=percentile(team_sizes, 50),
        review_latency_p50_hours=percentile(team_latency, 50),
        reviewer_concentration=reviewer_concentration(all_team_reviews),
        pct_prs_with_substantive_review=pct_prs_with_substantive_review(all_team_prs, all_team_reviews),
        contribution_gini=gini(contribution_values),
        meeting_hours_per_week_avg=_avg_skip_none([pm.meeting_hours_per_week for pm in person_metrics]),
        focus_block_hours_per_week_avg=_avg_skip_none([pm.focus_block_hours_per_week for pm in person_metrics]),
    )

    raw = RawPeriodData(
        prs=all_team_prs,
        reviews_given=all_team_reviews,
        comments_left=[c for _, _, _, cmts, _, _ in per_person for c in cmts],
        busy_blocks_by_member={
            m.google: blocks for m, _, _, _, blocks, _ in per_person if m.google
        },
        all_day_blocks_by_member={
            m.google: all_day for m, _, _, _, _, all_day in per_person if m.google and all_day
        },
    )

    return PeriodReport(
        period_label=period.label,
        period_from=frm,
        period_to=to,
        team=team.name,
        team_metrics=team_metrics,
        person_metrics=person_metrics,
        raw=raw,
    )


def _avg_skip_none(values: list[float | None]) -> float | None:
    real = [v for v in values if v is not None]
    if not real:
        return None
    return mean(real)
