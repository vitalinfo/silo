from datetime import datetime, timezone

from silo.metrics.flow import pr_cycle_time_hours, pr_sizes_lines, time_to_first_review_hours
from silo.types import PullRequest, Review


def _pr(num, created, merged=None, author="alice", additions=10, deletions=5, org="o", repo="r"):
    return PullRequest(
        org=org,
        repo=repo,
        number=num,
        author=author,
        created_at=created,
        merged_at=merged,
        closed_at=merged,
        additions=additions,
        deletions=deletions,
    )


def _review(pr_num, reviewer, submitted, pr_author="alice", state="APPROVED", body_chars=0, org="o", repo="r"):
    return Review(
        pr_org=org,
        pr_repo=repo,
        pr_number=pr_num,
        pr_author=pr_author,
        reviewer=reviewer,
        state=state,
        submitted_at=submitted,
        body_chars=body_chars,
    )


def test_cycle_time_excludes_unmerged():
    prs = [
        _pr(1, datetime(2026, 1, 1, 9, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 15, tzinfo=timezone.utc)),  # 6h
        _pr(2, datetime(2026, 1, 2, 9, tzinfo=timezone.utc)),  # unmerged
    ]
    out = pr_cycle_time_hours(prs)
    assert out == [6.0]


def test_time_to_first_review_picks_earliest_non_author():
    pr = _pr(1, datetime(2026, 1, 1, 9, tzinfo=timezone.utc), author="alice")
    reviews = [
        _review(1, "alice", datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)),  # self, skip
        _review(1, "bob", datetime(2026, 1, 1, 12, tzinfo=timezone.utc)),       # 3h
        _review(1, "carol", datetime(2026, 1, 1, 18, tzinfo=timezone.utc)),     # later
    ]
    out = time_to_first_review_hours([pr], reviews)
    assert out == [3.0]


def test_time_to_first_review_skips_unreviewed_prs():
    prs = [_pr(1, datetime(2026, 1, 1, tzinfo=timezone.utc))]
    out = time_to_first_review_hours(prs, [])
    assert out == []


def test_pr_sizes():
    prs = [
        _pr(1, datetime(2026, 1, 1, tzinfo=timezone.utc), additions=100, deletions=50),
        _pr(2, datetime(2026, 1, 1, tzinfo=timezone.utc), additions=0, deletions=10),
    ]
    assert pr_sizes_lines(prs) == [150, 10]
