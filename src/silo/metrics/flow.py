"""Flow metrics: PR cycle time, time-to-first-review, PR size."""
from __future__ import annotations

from ..types import PullRequest, Review

_SECONDS_PER_HOUR = 3600.0


def pr_cycle_time_hours(prs: list[PullRequest]) -> list[float]:
    """Hours from PR opened to merged. Unmerged PRs excluded."""
    out: list[float] = []
    for p in prs:
        if p.merged_at is None:
            continue
        out.append((p.merged_at - p.created_at).total_seconds() / _SECONDS_PER_HOUR)
    return out


def time_to_first_review_hours(prs: list[PullRequest], reviews: list[Review]) -> list[float]:
    """Hours from PR opened to first review by anyone other than the author.
    PRs with no qualifying review are excluded.

    The `reviews` list may contain reviews on PRs not in `prs` (e.g. when one is from
    person A's authored list and the other is from person B's reviews-given list); we
    join on (org, repo, number)."""
    first_by_pr: dict[tuple[str, str, int], Review] = {}
    for r in reviews:
        if r.reviewer == r.pr_author:
            continue  # ignore self-reviews so they don't shadow the real first review
        key = (r.pr_org, r.pr_repo, r.pr_number)
        existing = first_by_pr.get(key)
        if existing is None or r.submitted_at < existing.submitted_at:
            first_by_pr[key] = r

    out: list[float] = []
    for p in prs:
        r = first_by_pr.get((p.org, p.repo, p.number))
        if r is None:
            continue
        out.append((r.submitted_at - p.created_at).total_seconds() / _SECONDS_PER_HOUR)
    return out


def pr_sizes_lines(prs: list[PullRequest]) -> list[int]:
    """Per-PR additions + deletions."""
    return [p.additions + p.deletions for p in prs]
