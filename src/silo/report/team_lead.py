"""Team-lead report: per-person detail + team metrics + period delta + narrative."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment

from ..types import PeriodReport
from ._format import fmt_delta, fmt_float, fmt_hours, fmt_int, fmt_lines, fmt_pct
from .narrative import generate_team_lead_narrative

log = logging.getLogger(__name__)

TEMPLATE = """\
# {{ team }} — Team Lead Report

_Generated {{ generated_at }} · periods: {{ period_labels|join(', ') }}_

{% for r in reports %}
## {{ r.period_label }}

### Team summary

| Metric | Value |
|---|---|
| PR cycle time (p50 / p90) | {{ h(r.team_metrics.pr_cycle_time_p50_hours) }} / {{ h(r.team_metrics.pr_cycle_time_p90_hours) }} |
| Time to first review (p50) | {{ h(r.team_metrics.time_to_first_review_p50_hours) }} |
| Median PR size | {{ lines(r.team_metrics.pr_size_p50_lines) }} lines |
| Review latency (p50) | {{ h(r.team_metrics.review_latency_p50_hours) }} |
| Reviewer concentration | {{ pct(r.team_metrics.reviewer_concentration) }} |
| % PRs with substantive review | {{ pct(r.team_metrics.pct_prs_with_substantive_review) }} |
| Contribution Gini | {{ flt(r.team_metrics.contribution_gini) }} |
| Meeting hours/wk (team avg) | {{ h(r.team_metrics.meeting_hours_per_week_avg) }} |
| Focus hours/wk (team avg) | {{ h(r.team_metrics.focus_block_hours_per_week_avg) }} |

### Per person

| Person | PRs | Reviewed | Comments | Cycle p50 | TTFR p50 | Meetings/wk | Focus/wk |
|---|---:|---:|---:|---:|---:|---:|---:|
{% for pm in r.person_metrics -%}
| {{ pm.github }} | {{ pm.prs_authored }} | {{ pm.prs_reviewed }} | {{ pm.comments_left }} | {{ h(pm.pr_cycle_time_p50_hours) }} | {{ h(pm.time_to_first_review_p50_hours) }} | {{ h(pm.meeting_hours_per_week) }} | {{ h(pm.focus_block_hours_per_week) }} |
{% endfor %}
{% endfor %}
{% if pop %}
## Period-over-period

Comparing **{{ pop.from_label }}** → **{{ pop.to_label }}**:

| Metric | {{ pop.from_label }} | {{ pop.to_label }} | Δ |
|---|---:|---:|---:|
{% for row in pop.rows -%}
| {{ row.label }} | {{ row.before }} | {{ row.after }} | {{ row.delta }} |
{% endfor %}
{% endif %}

## Patterns worth discussing

{{ narrative }}

---
_Reviews and comments are sourced from team members only. Reviews by people outside the team on this team's PRs are not currently counted (v1 limitation)._
"""


def render(
    team_name: str, reports: list[PeriodReport], out_dir: Path, api_key: str | None
) -> Path:
    """One markdown file per team. `reports` must all be for the same team,
    ordered chronologically by period. If `api_key` is None, narrative is skipped."""
    if not reports:
        raise ValueError(f"render({team_name}): no reports provided")
    for r in reports:
        if r.team != team_name:
            raise ValueError(f"render({team_name}): got report for team {r.team!r}")

    if api_key is None:
        narrative = (
            "_Narrative skipped (--skip-narrative). Re-run without the flag and "
            "with ANTHROPIC_API_KEY set to generate discussion patterns._"
        )
    else:
        log.info("[narrative] team_lead %s (%d periods)", team_name, len(reports))
        narrative = generate_team_lead_narrative(reports, api_key)

    pop = _period_over_period(reports) if len(reports) >= 2 else None

    env = Environment(trim_blocks=True, lstrip_blocks=True)
    template = env.from_string(TEMPLATE)
    body = template.render(
        team=team_name,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        period_labels=[r.period_label for r in reports],
        reports=reports,
        pop=pop,
        narrative=narrative,
        h=fmt_hours,
        lines=fmt_lines,
        pct=fmt_pct,
        flt=fmt_float,
        i=fmt_int,
    )

    out_path = out_dir / f"team_lead_{_slug(team_name)}.md"
    out_path.write_text(body)
    log.info("[report] wrote %s", out_path)
    return out_path


def _period_over_period(reports: list[PeriodReport]) -> dict:
    """Compare the first and last report in `reports`. Assumes chronological order."""
    first, last = reports[0], reports[-1]
    a, b = first.team_metrics, last.team_metrics
    rows = [
        {
            "label": "PR cycle time p50",
            "before": fmt_hours(a.pr_cycle_time_p50_hours),
            "after": fmt_hours(b.pr_cycle_time_p50_hours),
            "delta": fmt_delta(a.pr_cycle_time_p50_hours, b.pr_cycle_time_p50_hours, suffix="h"),
        },
        {
            "label": "Time to first review p50",
            "before": fmt_hours(a.time_to_first_review_p50_hours),
            "after": fmt_hours(b.time_to_first_review_p50_hours),
            "delta": fmt_delta(a.time_to_first_review_p50_hours, b.time_to_first_review_p50_hours, suffix="h"),
        },
        {
            "label": "Review latency p50",
            "before": fmt_hours(a.review_latency_p50_hours),
            "after": fmt_hours(b.review_latency_p50_hours),
            "delta": fmt_delta(a.review_latency_p50_hours, b.review_latency_p50_hours, suffix="h"),
        },
        {
            "label": "Reviewer concentration",
            "before": fmt_pct(a.reviewer_concentration),
            "after": fmt_pct(b.reviewer_concentration),
            "delta": fmt_delta(a.reviewer_concentration, b.reviewer_concentration, places=2, suffix=""),
        },
        {
            "label": "% PRs w/ substantive review",
            "before": fmt_pct(a.pct_prs_with_substantive_review),
            "after": fmt_pct(b.pct_prs_with_substantive_review),
            "delta": fmt_delta(a.pct_prs_with_substantive_review, b.pct_prs_with_substantive_review, places=2),
        },
        {
            "label": "Meeting hrs/wk avg",
            "before": fmt_hours(a.meeting_hours_per_week_avg),
            "after": fmt_hours(b.meeting_hours_per_week_avg),
            "delta": fmt_delta(a.meeting_hours_per_week_avg, b.meeting_hours_per_week_avg, suffix="h"),
        },
        {
            "label": "Focus hrs/wk avg",
            "before": fmt_hours(a.focus_block_hours_per_week_avg),
            "after": fmt_hours(b.focus_block_hours_per_week_avg),
            "delta": fmt_delta(a.focus_block_hours_per_week_avg, b.focus_block_hours_per_week_avg, suffix="h"),
        },
    ]
    return {"from_label": first.period_label, "to_label": last.period_label, "rows": rows}


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s.lower())
