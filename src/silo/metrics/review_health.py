"""Review-health metrics: latency, reviewer concentration, % PRs with substantive review."""
from __future__ import annotations

from collections import Counter

from ..types import PullRequest, Review

SUBSTANTIVE_REVIEW_MIN_CHARS = 50
_SECONDS_PER_HOUR = 3600.0


def review_latency_hours(prs: list[PullRequest], reviews: list[Review]) -> list[float]:
    """Hours from PR opened to each review submission. Reviews on PRs not in `prs` are skipped."""
    pr_open: dict[tuple[str, str, int], object] = {(p.org, p.repo, p.number): p.created_at for p in prs}
    out: list[float] = []
    for r in reviews:
        opened = pr_open.get((r.pr_org, r.pr_repo, r.pr_number))
        if opened is None:
            continue
        out.append((r.submitted_at - opened).total_seconds() / _SECONDS_PER_HOUR)  # type: ignore[operator]
    return out


def reviewer_concentration(reviews: list[Review]) -> float | None:
    """Share of reviews authored by the single top reviewer. 0..1. None if no reviews."""
    if not reviews:
        return None
    counts = Counter(r.reviewer for r in reviews)
    top = max(counts.values())
    return top / len(reviews)


def pct_prs_with_substantive_review(prs: list[PullRequest], reviews: list[Review]) -> float | None:
    """Share of PRs with >=1 review that is either CHANGES_REQUESTED or has body >= 50 chars.
    0..1. None if no PRs."""
    if not prs:
        return None
    substantive_prs: set[tuple[str, str, int]] = set()
    for r in reviews:
        if r.state == "CHANGES_REQUESTED" or r.body_chars >= SUBSTANTIVE_REVIEW_MIN_CHARS:
            substantive_prs.add((r.pr_org, r.pr_repo, r.pr_number))
    hits = sum(1 for p in prs if (p.org, p.repo, p.number) in substantive_prs)
    return hits / len(prs)
