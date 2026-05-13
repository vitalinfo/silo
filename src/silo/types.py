"""Raw + aggregated domain types shared across collectors, metrics, and reports."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


# --- Raw GitHub records ---------------------------------------------------

ReviewState = Literal["APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"]


class Review(BaseModel):
    pr_org: str
    pr_repo: str
    pr_number: int
    pr_author: str
    reviewer: str  # gh login
    state: ReviewState
    submitted_at: datetime
    body_chars: int


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
    # Fields below default to safe zero/empty values so tests and ad-hoc construction
    # don't need to set them. The collector always populates them from GraphQL.
    title: str = ""
    url: str = ""
    is_bot: bool = False
    commits_count: int = 0
    # Count of reviewers requested but who never submitted a review. For a merged PR
    # this is effectively the "pending review requests at merge" snapshot.
    pending_review_requests: int = 0
    # All reviews on this PR, regardless of reviewer. Lets downstream analysis compute
    # review counts/latency without a separate per-PR query.
    reviews: list[Review] = []


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


class RawPeriodData(BaseModel):
    """Raw collector output for one (team, period). Carried alongside metrics so the
    JSON serializer can dump everything Cowork might want to analyse downstream."""
    prs: list[PullRequest] = []                    # team-authored PRs (with embedded reviews)
    reviews_given: list[Review] = []               # by team members on others' PRs
    comments_left: list[IssueComment] = []         # by team members on others' PRs
    busy_blocks_by_member: dict[str, list[BusyBlock]] = {}  # google email -> blocks


class PeriodReport(BaseModel):
    period_label: str
    period_from: date
    period_to: date
    team: str
    team_metrics: TeamMetrics
    person_metrics: list[PersonMetrics]
    raw: RawPeriodData | None = None
