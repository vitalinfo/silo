"""Lightweight schema validation tests — confirms our Pydantic models reject bad input."""
import pytest
from pydantic import ValidationError

from silo.config import RunConfig, TeamsConfig, WorkHours


def test_teams_unique_names():
    with pytest.raises(ValidationError, match="unique"):
        TeamsConfig.model_validate({
            "github_orgs": ["o"],
            "teams": [
                {"name": "x", "lead": "a@x.com", "members": [{"github": "a", "google": "a@x.com"}]},
                {"name": "x", "lead": "b@x.com", "members": [{"github": "b", "google": "b@x.com"}]},
            ],
        })


def test_period_from_after_to_rejected():
    with pytest.raises(ValidationError, match="from"):
        RunConfig.model_validate({
            "periods": [{"label": "p", "from": "2026-05-01", "to": "2026-01-01"}],
            "teams": "all",
            "comparisons": {},
            "reports": ["team_lead"],
            "work_hours": {
                "start": "09:00", "end": "18:00",
                "workdays": ["mon"], "tz": "UTC",
            },
        })


def test_work_hours_unknown_tz_rejected():
    with pytest.raises(ValidationError, match="unknown timezone"):
        WorkHours.model_validate({
            "start": "09:00", "end": "18:00",
            "workdays": ["mon"], "tz": "Mars/Olympus_Mons",
        })


def test_work_hours_start_after_end_rejected():
    with pytest.raises(ValidationError, match="start.*before"):
        WorkHours.model_validate({
            "start": "18:00", "end": "09:00",
            "workdays": ["mon"], "tz": "UTC",
        })


def test_work_hours_zoneinfo_property():
    wh = WorkHours.model_validate({
        "start": "09:00", "end": "18:00",
        "workdays": ["mon", "tue"], "tz": "America/New_York",
    })
    assert wh.zoneinfo.key == "America/New_York"
    assert wh.workday_indices == {0, 1}
