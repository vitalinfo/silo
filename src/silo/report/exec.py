"""Exec report: team-level only, no per-person data, narrative-led.

Cross-team comparisons are restricted to normalized metrics (rates, ratios,
percentiles) so teams with different work shapes aren't ranked unfairly.
Raw counts are deliberately omitted.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment

from ..types import PeriodReport
from ._format import fmt_delta, fmt_float, fmt_hours, fmt_lines, fmt_pct
from .narrative import generate_exec_narrative

log = logging.getLogger(__name__)

TEMPLATE = """\
# Exec Report

_Generated {{ generated_at }} · teams: {{ team_names|join(', ') }} · periods: {{ period_labels|join(', ') }}_

## Cross-team — latest period ({{ latest_period }})

Normalized metrics only. Raw activity counts are excluded by design.

| Team | Cycle p50 | TTFR p50 | Latency p50 | Sub. review % | Reviewer conc. | Contrib. Gini | Meetings/wk | Focus/wk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{% for row in latest_rows -%}
| {{ row.team }} | {{ h(row.tm.pr_cycle_time_p50_hours) }} | {{ h(row.tm.time_to_first_review_p50_hours) }} | {{ h(row.tm.review_latency_p50_hours) }} | {{ pct(row.tm.pct_prs_with_substantive_review) }} | {{ pct(row.tm.reviewer_concentration) }} | {{ flt(row.tm.contribution_gini) }} | {{ h(row.tm.meeting_hours_per_week_avg) }} | {{ h(row.tm.focus_block_hours_per_week_avg) }} |
{% endfor %}
{% if pop_per_team %}
## Period-over-period (per team)

Comparing **{{ pop_from }}** → **{{ pop_to }}**:

| Team | Cycle p50 | TTFR p50 | Latency p50 | Sub. review % | Meetings/wk | Focus/wk |
|---|---:|---:|---:|---:|---:|---:|
{% for team, rows in pop_per_team.items() -%}
| {{ team }} | {{ rows.cycle }} | {{ rows.ttfr }} | {{ rows.latency }} | {{ rows.substantive }} | {{ rows.meetings }} | {{ rows.focus }} |
{% endfor %}
{% endif %}
## Patterns worth discussing

{{ narrative }}

---

### What this measures (and doesn't)

- **Measures**: PR flow (cycle time, time-to-first-review, size), review health \
(latency, concentration, substantive reviews) for activity inside the configured \
GitHub orgs, and calendar load (meetings, focus blocks) from Google Calendar \
freebusy data.
- **Does not measure**: code quality, individual impact, work outside GitHub PRs \
(production incidents, planning, mentorship, customer calls), or reviews on team \
PRs by people outside the team (v1 limitation).
- **Cross-team comparison caveat**: teams ship different kinds of work. Long PR \
cycle times may reflect riskier, larger-batch changes — not slowness. Treat \
absolute differences between teams as conversation starters, not rankings.
- **Period-over-period is the most reliable signal**: same team, same work mix, \
trend over time.
"""


def render(reports: list[PeriodReport], out_dir: Path, api_key: str | None) -> Path:
    """Single markdown file across all teams + periods. No per-person data.
    If `api_key` is None, narrative is skipped."""
    if not reports:
        raise ValueError("exec.render: no reports provided")

    if api_key is None:
        narrative = (
            "_Narrative skipped (--skip-narrative). Re-run without the flag and "
            "with ANTHROPIC_API_KEY set to generate discussion patterns._"
        )
    else:
        log.info("[narrative] exec (%d reports)", len(reports))
        narrative = generate_exec_narrative(reports, api_key)

    by_team: dict[str, list[PeriodReport]] = defaultdict(list)
    for r in reports:
        by_team[r.team].append(r)
    team_names = sorted(by_team.keys())
    period_labels = sorted({r.period_label for r in reports})

    # Latest period: pick the report from each team with the lexicographically
    # last period label — main.py orders periods chronologically and uses the
    # last one's label as the "latest." Here we just trust input order.
    period_order = [r.period_label for r in reports]
    latest_period = period_order[-1] if period_order else ""
    latest_rows = [
        {"team": team, "tm": [r for r in trs if r.period_label == latest_period][0].team_metrics}
        for team, trs in by_team.items()
        if any(r.period_label == latest_period for r in trs)
    ]

    pop_per_team = None
    pop_from = pop_to = None
    if len({r.period_label for r in reports}) >= 2:
        pop_from = period_order[0]
        pop_to = period_order[-1]
        pop_per_team = _pop_table(by_team, pop_from, pop_to)

    env = Environment(trim_blocks=True, lstrip_blocks=True)
    template = env.from_string(TEMPLATE)
    body = template.render(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        team_names=team_names,
        period_labels=period_labels,
        latest_period=latest_period,
        latest_rows=latest_rows,
        pop_per_team=pop_per_team,
        pop_from=pop_from,
        pop_to=pop_to,
        narrative=narrative,
        h=fmt_hours,
        pct=fmt_pct,
        flt=fmt_float,
        lines=fmt_lines,
    )

    out_path = out_dir / "exec.md"
    out_path.write_text(body)
    log.info("[report] wrote %s", out_path)
    return out_path


def _pop_table(
    by_team: dict[str, list[PeriodReport]], pop_from: str, pop_to: str
) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for team, trs in by_team.items():
        a = next((r.team_metrics for r in trs if r.period_label == pop_from), None)
        b = next((r.team_metrics for r in trs if r.period_label == pop_to), None)
        if a is None or b is None:
            continue
        rows[team] = {
            "cycle": fmt_delta(a.pr_cycle_time_p50_hours, b.pr_cycle_time_p50_hours, suffix="h"),
            "ttfr": fmt_delta(a.time_to_first_review_p50_hours, b.time_to_first_review_p50_hours, suffix="h"),
            "latency": fmt_delta(a.review_latency_p50_hours, b.review_latency_p50_hours, suffix="h"),
            "substantive": fmt_delta(a.pct_prs_with_substantive_review, b.pct_prs_with_substantive_review, places=2),
            "meetings": fmt_delta(a.meeting_hours_per_week_avg, b.meeting_hours_per_week_avg, suffix="h"),
            "focus": fmt_delta(a.focus_block_hours_per_week_avg, b.focus_block_hours_per_week_avg, suffix="h"),
        }
    return rows
