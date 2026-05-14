"""Aggregate-level tests. Mostly cover plumbing logic that doesn't fit elsewhere."""
from datetime import datetime, timezone

from silo.aggregate import _restrict_bot_prs_to_team_repos
from silo.config import Member
from silo.types import PullRequest


def _pr(org: str, repo: str, number: int, author: str) -> PullRequest:
    return PullRequest(
        org=org,
        repo=repo,
        number=number,
        author=author,
        is_bot=author.endswith("[bot]"),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        merged_at=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
        closed_at=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
        additions=10,
        deletions=0,
    )


def _entry(github: str, prs: list[PullRequest], google: str | None = None):
    m = Member(github=github, google=google)
    return (m, prs, [], [], [], [])


def test_bot_prs_restricted_to_team_repos():
    alice_prs = [_pr("acme", "api", 1, "alice"), _pr("acme", "api", 2, "alice")]
    bot_prs = [
        _pr("acme", "api", 10, "dependabot[bot]"),       # repo team touched -> keep
        _pr("acme", "staff_sync", 11, "dependabot[bot]"),  # repo nobody touched -> drop
        _pr("acme", "billing", 12, "dependabot[bot]"),   # repo nobody touched -> drop
    ]
    per_person = [
        _entry("alice", alice_prs, google="alice@x.com"),
        _entry("dependabot[bot]", bot_prs),
    ]

    out = _restrict_bot_prs_to_team_repos(per_person)
    # alice's PRs untouched
    assert out[0][1] == alice_prs
    # bot's PRs restricted to api only
    assert [pr.number for pr in out[1][1]] == [10]


def test_bot_with_no_team_repos_yields_empty():
    bot_prs = [_pr("acme", "api", 1, "dependabot[bot]")]
    per_person = [
        _entry("dependabot[bot]", bot_prs),
        _entry("octobot[bot]", [_pr("acme", "api", 2, "octobot[bot]")]),
    ]
    out = _restrict_bot_prs_to_team_repos(per_person)
    # No non-bot member touched anything, so bots have nothing to attribute to.
    assert out[0][1] == []
    assert out[1][1] == []


def test_no_bot_members_passes_through_unchanged():
    prs_a = [_pr("acme", "api", 1, "alice")]
    prs_b = [_pr("acme", "ui", 2, "bob")]
    per_person = [
        _entry("alice", prs_a, google="alice@x.com"),
        _entry("bob", prs_b, google="bob@x.com"),
    ]
    out = _restrict_bot_prs_to_team_repos(per_person)
    assert out[0][1] == prs_a
    assert out[1][1] == prs_b
