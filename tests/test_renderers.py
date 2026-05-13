"""End-to-end renderer tests using synthetic PeriodReports.

api_key=None skips the Claude call so these tests run offline. The goal is
to catch template/format errors before a real run.
"""
from silo.report import exec as exec_report
from silo.report import team_lead
from silo.types import PeriodReport, PersonMetrics, TeamMetrics


def _person(github: str, **kw) -> PersonMetrics:
    base = {
        "github": github,
        "google": f"{github}@example.com",
        "prs_authored": 5,
        "prs_reviewed": 10,
        "comments_left": 20,
        "pr_cycle_time_p50_hours": 12.3,
        "pr_cycle_time_p90_hours": 36.7,
        "time_to_first_review_p50_hours": 4.5,
        "pr_size_p50_lines": 120.0,
        "pr_size_p90_lines": 800.0,
        "meeting_hours_per_week": 8.2,
        "focus_block_hours_per_week": 18.5,
        "fragmentation_score": 0.12,
        "after_hours_busy_per_week": 1.4,
    }
    base.update(kw)
    return PersonMetrics(**base)


def _team_metrics(team: str, **kw) -> TeamMetrics:
    base = {
        "team": team,
        "pr_cycle_time_p50_hours": 14.0,
        "pr_cycle_time_p90_hours": 42.0,
        "time_to_first_review_p50_hours": 5.0,
        "pr_size_p50_lines": 130.0,
        "review_latency_p50_hours": 8.0,
        "reviewer_concentration": 0.55,
        "pct_prs_with_substantive_review": 0.62,
        "contribution_gini": 0.21,
        "meeting_hours_per_week_avg": 7.8,
        "focus_block_hours_per_week_avg": 19.0,
    }
    base.update(kw)
    return TeamMetrics(**base)


def _report(team: str, period: str, **tm_overrides) -> PeriodReport:
    return PeriodReport(
        period_label=period,
        team=team,
        team_metrics=_team_metrics(team, **tm_overrides),
        person_metrics=[_person("alice"), _person("bob", prs_authored=2, meeting_hours_per_week=None)],
    )


def test_team_lead_render_single_period(tmp_path):
    reports = [_report("backend", "Q1")]
    out = team_lead.render("backend", reports, tmp_path, api_key=None)
    body = out.read_text()
    assert "# backend — Team Lead Report" in body
    assert "## Q1" in body
    assert "alice" in body and "bob" in body
    assert "Narrative skipped" in body
    assert "Period-over-period" not in body  # only one period


def test_team_lead_render_multi_period_shows_delta(tmp_path):
    reports = [
        _report("backend", "Q1", pr_cycle_time_p50_hours=10.0),
        _report("backend", "Q2", pr_cycle_time_p50_hours=14.0),
    ]
    out = team_lead.render("backend", reports, tmp_path, api_key=None)
    body = out.read_text()
    assert "Period-over-period" in body
    assert "Q1" in body and "Q2" in body


def test_team_lead_rejects_mixed_teams(tmp_path):
    import pytest

    reports = [_report("backend", "Q1"), _report("frontend", "Q1")]
    with pytest.raises(ValueError, match="frontend"):
        team_lead.render("backend", reports, tmp_path, api_key=None)


def test_exec_render_writes_disclaimer_and_omits_persons(tmp_path):
    reports = [
        _report("backend", "Q1", pr_cycle_time_p50_hours=10.0),
        _report("backend", "Q2", pr_cycle_time_p50_hours=14.0),
        _report("frontend", "Q1", pr_cycle_time_p50_hours=8.0),
        _report("frontend", "Q2", pr_cycle_time_p50_hours=7.5),
    ]
    out = exec_report.render(reports, tmp_path, api_key=None)
    body = out.read_text()
    assert "# Exec Report" in body
    assert "Cross-team — latest period" in body
    assert "backend" in body and "frontend" in body
    # No per-person handles should appear in the exec report.
    assert "alice" not in body and "bob" not in body
    assert "What this measures" in body
    assert "Period-over-period" in body


def test_exec_render_handles_missing_period_data(tmp_path):
    # frontend only has one period — exec should not crash.
    reports = [
        _report("backend", "Q1"),
        _report("backend", "Q2"),
        _report("frontend", "Q2"),
    ]
    out = exec_report.render(reports, tmp_path, api_key=None)
    assert out.exists()
