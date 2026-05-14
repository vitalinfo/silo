"""Tests for the JSON serializer. Builds synthetic PeriodReports, verifies the
emitted metrics.json has the expected shape and is round-trippable."""
import json
from datetime import date, datetime, timezone

from silo.config import RunConfig, TeamsConfig
from silo.serialize import SCHEMA_VERSION, serialize_run, write_instructions
from silo.types import (
    BusyBlock,
    IssueComment,
    PeriodReport,
    PersonMetrics,
    PullRequest,
    RawPeriodData,
    Review,
    TeamMetrics,
)

_TEAMS_CFG = {
    "github_orgs": ["acme-org"],
    "teams": [
        {
            "name": "backend",
            "lead": "alice@example.com",
            "members": [
                {"github": "alice", "google": "alice@example.com", "tz": "UTC"},
                {"github": "bob", "google": "bob@example.com", "tz": "Europe/Kyiv"},
            ],
        },
    ],
}

_RUN_CFG = {
    "periods": [{"label": "Q1", "from": "2026-01-01", "to": "2026-03-31"}],
    "teams": "all",
    "comparisons": {"period_over_period": True, "cross_team": True},
    "reports": ["team_lead", "exec"],
    "work_hours": {"start": "09:00", "end": "18:00", "workdays": ["mon", "tue", "wed", "thu", "fri"]},
}


def _build_period_report() -> PeriodReport:
    pr = PullRequest(
        org="acme-org",
        repo="api",
        number=42,
        title="[PORT-1] Make widget faster",
        url="https://github.com/acme-org/api/pull/42",
        author="alice",
        is_bot=False,
        created_at=datetime(2026, 1, 5, 9, tzinfo=timezone.utc),
        merged_at=datetime(2026, 1, 5, 15, tzinfo=timezone.utc),
        closed_at=datetime(2026, 1, 5, 15, tzinfo=timezone.utc),
        additions=100,
        deletions=50,
        commits_count=3,
        pending_review_requests=0,
        reviews=[
            Review(
                pr_org="acme-org", pr_repo="api", pr_number=42, pr_author="alice",
                reviewer="bob", state="APPROVED",
                submitted_at=datetime(2026, 1, 5, 12, tzinfo=timezone.utc), body_chars=100,
            )
        ],
    )
    return PeriodReport(
        period_label="Q1",
        period_from=date(2026, 1, 1),
        period_to=date(2026, 3, 31),
        team="backend",
        team_metrics=TeamMetrics(
            team="backend", pr_cycle_time_p50_hours=6.0, reviewer_concentration=1.0,
        ),
        person_metrics=[
            PersonMetrics(github="alice", google="alice@example.com", prs_authored=1),
            PersonMetrics(github="bob", google="bob@example.com", prs_reviewed=1),
        ],
        raw=RawPeriodData(
            prs=[pr],
            reviews_given=[pr.reviews[0]],
            comments_left=[
                IssueComment(
                    pr_org="acme-org", pr_repo="api", pr_number=99, pr_author="carol",
                    author="alice",
                    created_at=datetime(2026, 1, 10, tzinfo=timezone.utc), body_chars=20,
                )
            ],
            busy_blocks_by_member={
                "alice@example.com": [
                    BusyBlock(
                        google_email="alice@example.com",
                        start=datetime(2026, 1, 5, 14, tzinfo=timezone.utc),
                        end=datetime(2026, 1, 5, 15, tzinfo=timezone.utc),
                    )
                ],
                "bob@example.com": [],
            },
            all_day_blocks_by_member={
                "alice@example.com": [
                    BusyBlock(
                        google_email="alice@example.com",
                        start=datetime(2026, 1, 5, 5, tzinfo=timezone.utc),
                        end=datetime(2026, 1, 6, 5, tzinfo=timezone.utc),
                    )
                ],
            },
        ),
    )


def test_serialize_run_writes_expected_shape(tmp_path):
    teams_cfg = TeamsConfig.model_validate(_TEAMS_CFG)
    run_cfg = RunConfig.model_validate(_RUN_CFG)
    teams = run_cfg.resolve_teams(teams_cfg)
    reports = [_build_period_report()]

    out_path = serialize_run(run_cfg, teams_cfg, teams, reports, tmp_path)
    assert out_path.exists()
    payload = json.loads(out_path.read_text())

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["config"]["github_orgs"] == ["acme-org"]
    assert payload["config"]["work_hours"]["start"] == "09:00"
    assert payload["config"]["periods"][0]["label"] == "Q1"

    assert len(payload["teams"]) == 1
    team = payload["teams"][0]
    assert team["name"] == "backend"
    assert team["lead"] == "alice@example.com"
    assert team["members"][1]["tz"] == "Europe/Kyiv"

    period = team["periods"][0]
    assert period["label"] == "Q1"
    assert period["team_metrics"]["pr_cycle_time_p50_hours"] == 6.0
    assert len(period["person_metrics"]) == 2

    raw = period["raw"]
    assert len(raw["prs"]) == 1
    assert raw["prs"][0]["title"].startswith("[PORT-1]")
    assert raw["prs"][0]["commits_count"] == 3
    assert raw["prs"][0]["is_bot"] is False
    assert len(raw["prs"][0]["reviews"]) == 1
    assert len(raw["reviews_given"]) == 1
    assert len(raw["comments_left"]) == 1
    assert "alice@example.com" in raw["busy_blocks_by_member"]
    assert "alice@example.com" in raw["all_day_blocks_by_member"]
    assert len(raw["all_day_blocks_by_member"]["alice@example.com"]) == 1


def test_serialize_omits_raw_when_missing(tmp_path):
    teams_cfg = TeamsConfig.model_validate(_TEAMS_CFG)
    run_cfg = RunConfig.model_validate(_RUN_CFG)
    teams = run_cfg.resolve_teams(teams_cfg)
    report = _build_period_report()
    report.raw = None
    out_path = serialize_run(run_cfg, teams_cfg, teams, [report], tmp_path)
    payload = json.loads(out_path.read_text())
    assert "raw" not in payload["teams"][0]["periods"][0]


def test_write_instructions_references_prompts_and_data(tmp_path):
    (tmp_path / "metrics.json").write_text("{}")
    out = write_instructions(tmp_path, ["team_lead", "exec"])
    body = out.read_text()
    assert "INSTRUCTIONS" in body or "instructions" in body
    assert "prompts/team_lead.md" in body
    assert "prompts/exec.md" in body
    assert "metrics.json" in body
