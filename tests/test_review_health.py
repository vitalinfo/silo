from datetime import datetime, timezone

from silo.metrics.review_health import (
    pct_prs_with_substantive_review,
    review_latency_hours,
    reviewer_concentration,
)
from silo.types import PullRequest, Review


def _pr(num, created, author="alice"):
    return PullRequest(
        org="o", repo="r", number=num, author=author,
        created_at=created, merged_at=None, closed_at=None,
        additions=10, deletions=0,
    )


def _review(num, reviewer, submitted, state="APPROVED", body_chars=0, pr_author="alice"):
    return Review(
        pr_org="o", pr_repo="r", pr_number=num, pr_author=pr_author,
        reviewer=reviewer, state=state, submitted_at=submitted, body_chars=body_chars,
    )


def test_review_latency_only_for_matched_prs():
    prs = [_pr(1, datetime(2026, 1, 1, 9, tzinfo=timezone.utc))]
    reviews = [
        _review(1, "bob", datetime(2026, 1, 1, 11, tzinfo=timezone.utc)),  # 2h
        _review(99, "bob", datetime(2026, 1, 1, 11, tzinfo=timezone.utc)),  # orphan, skipped
    ]
    assert review_latency_hours(prs, reviews) == [2.0]


def test_reviewer_concentration_top_share():
    reviews = [
        _review(1, "bob", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _review(2, "bob", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _review(3, "bob", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _review(4, "carol", datetime(2026, 1, 1, tzinfo=timezone.utc)),
    ]
    assert reviewer_concentration(reviews) == 0.75


def test_reviewer_concentration_empty_is_none():
    assert reviewer_concentration([]) is None


def test_pct_substantive_changes_requested_counts():
    pr = _pr(1, datetime(2026, 1, 1, tzinfo=timezone.utc))
    reviews = [_review(1, "bob", datetime(2026, 1, 1, tzinfo=timezone.utc), state="CHANGES_REQUESTED")]
    assert pct_prs_with_substantive_review([pr], reviews) == 1.0


def test_pct_substantive_long_body_counts():
    pr = _pr(1, datetime(2026, 1, 1, tzinfo=timezone.utc))
    reviews = [_review(1, "bob", datetime(2026, 1, 1, tzinfo=timezone.utc), state="COMMENTED", body_chars=51)]
    assert pct_prs_with_substantive_review([pr], reviews) == 1.0


def test_pct_substantive_short_lgtm_does_not_count():
    pr = _pr(1, datetime(2026, 1, 1, tzinfo=timezone.utc))
    reviews = [_review(1, "bob", datetime(2026, 1, 1, tzinfo=timezone.utc), state="APPROVED", body_chars=5)]
    assert pct_prs_with_substantive_review([pr], reviews) == 0.0


def test_pct_substantive_mixed():
    prs = [_pr(1, datetime(2026, 1, 1, tzinfo=timezone.utc)), _pr(2, datetime(2026, 1, 1, tzinfo=timezone.utc))]
    reviews = [
        _review(1, "bob", datetime(2026, 1, 1, tzinfo=timezone.utc), state="APPROVED", body_chars=100),
        _review(2, "bob", datetime(2026, 1, 1, tzinfo=timezone.utc), state="APPROVED", body_chars=3),
    ]
    assert pct_prs_with_substantive_review(prs, reviews) == 0.5
