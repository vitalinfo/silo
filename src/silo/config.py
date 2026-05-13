"""Pydantic schemas for teams.yaml and run.yaml + loaders."""
from __future__ import annotations

from datetime import date, time
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


def _validate_tz(v: str) -> str:
    try:
        ZoneInfo(v)
    except ZoneInfoNotFoundError as e:
        raise ValueError(f"unknown timezone: {v}") from e
    return v


class Member(BaseModel):
    github: str
    google: EmailStr
    tz: str = "UTC"

    @field_validator("tz")
    @classmethod
    def _tz_valid(cls, v: str) -> str:
        return _validate_tz(v)

    @property
    def zoneinfo(self) -> ZoneInfo:
        return ZoneInfo(self.tz)


class Team(BaseModel):
    name: str
    lead: EmailStr
    members: list[Member]


class TeamsConfig(BaseModel):
    github_orgs: list[str] = Field(min_length=1)
    teams: list[Team] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_team_names(self) -> "TeamsConfig":
        names = [t.name for t in self.teams]
        if len(names) != len(set(names)):
            raise ValueError("team names must be unique")
        return self

    def team(self, name: str) -> Team:
        for t in self.teams:
            if t.name == name:
                return t
        raise KeyError(f"team {name!r} not found in teams.yaml")


class Period(BaseModel):
    label: str
    from_: date = Field(alias="from")
    to: date

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _from_before_to(self) -> "Period":
        if self.from_ > self.to:
            raise ValueError(f"period {self.label!r}: 'from' must be <= 'to'")
        return self


class Comparisons(BaseModel):
    period_over_period: bool = True
    cross_team: bool = True


_DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


class WorkHours(BaseModel):
    """The shape of a workday (start/end wall-clock, which weekdays count).
    Timezone is per-member, supplied separately to metrics."""
    start: time
    end: time
    workdays: list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]]

    @model_validator(mode="after")
    def _start_before_end(self) -> "WorkHours":
        if self.start >= self.end:
            raise ValueError("work_hours.start must be before work_hours.end")
        return self

    @property
    def workday_indices(self) -> set[int]:
        return {_DAY_MAP[d] for d in self.workdays}


ReportKind = Literal["team_lead", "exec"]


class RunConfig(BaseModel):
    periods: list[Period] = Field(min_length=1)
    teams: list[str] | Literal["all"]
    comparisons: Comparisons
    reports: list[ReportKind]
    work_hours: WorkHours

    @field_validator("reports")
    @classmethod
    def _reports_non_empty(cls, v: list[ReportKind]) -> list[ReportKind]:
        if not v:
            raise ValueError("reports must contain at least one of: team_lead, exec")
        return v

    def resolve_teams(self, teams_cfg: TeamsConfig) -> list[Team]:
        if self.teams == "all":
            return list(teams_cfg.teams)
        return [teams_cfg.team(name) for name in self.teams]

    def latest_period(self) -> Period:
        return max(self.periods, key=lambda p: p.to)


def load_teams(path: Path) -> TeamsConfig:
    with path.open() as f:
        data = yaml.safe_load(f)
    return TeamsConfig.model_validate(data)


def load_run(path: Path) -> RunConfig:
    with path.open() as f:
        data = yaml.safe_load(f)
    return RunConfig.model_validate(data)
