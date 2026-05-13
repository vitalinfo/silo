"""Raw + aggregated domain types shared across collectors, metrics, and reports."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# --- Raw GitHub records ---------------------------------------------------

ReviewState = Literal["APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"]


class PullRequest(BaseModel):
    org: str
    repo: str
    number: int
    author: str  # gh login
    created_at: datetime
    merged_at: datetime | None
    closed_at: datetime | None
    additions: int
    deletions: int


class Review(BaseModel):
    pr_org: str
    pr_repo: str
    pr_number: int
    pr_author: str
    reviewer: str  # gh login
    state: ReviewState
    submitted_at: datetime
    body_chars: int


class IssueComment(BaseModel):
    """Comment on a PR (issue comment, not inline review comment)."""
    pr_org: str
    pr_repo: str
    pr_number: int
    pr_author: str
    author: str  # gh login of commenter
    created_at: datetime
    body_chars: int


# --- Raw Calendar records -------------------------------------------------

class BusyBlock(BaseModel):
    google_email: str
    start: datetime
    end: datetime


# --- Aggregated metrics ---------------------------------------------------

class PersonMetrics(BaseModel):
    github: str
    google: str
    prs_authored: int = 0
    prs_reviewed: int = 0
    comments_left: int = 0
    pr_cycle_time_p50_hours: float | None = None
    pr_cycle_time_p90_hours: float | None = None
    time_to_first_review_p50_hours: float | None = None
    pr_size_p50_lines: float | None = None
    pr_size_p90_lines: float | None = None
    meeting_hours_per_week: float | None = None
    focus_block_hours_per_week: float | None = None
    fragmentation_score: float | None = None
    after_hours_busy_per_week: float | None = None


class TeamMetrics(BaseModel):
    team: str
    pr_cycle_time_p50_hours: float | None = None
    pr_cycle_time_p90_hours: float | None = None
    time_to_first_review_p50_hours: float | None = None
    pr_size_p50_lines: float | None = None
    review_latency_p50_hours: float | None = None
    reviewer_concentration: float | None = None  # share of reviews by top reviewer (0..1)
    pct_prs_with_substantive_review: float | None = None  # 0..1
    contribution_gini: float | None = None  # 0..1; 0 = even, 1 = concentrated
    meeting_hours_per_week_avg: float | None = None
    focus_block_hours_per_week_avg: float | None = None


class PeriodReport(BaseModel):
    period_label: str
    team: str
    team_metrics: TeamMetrics
    person_metrics: list[PersonMetrics]
