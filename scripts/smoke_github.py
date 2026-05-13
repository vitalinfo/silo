"""Smoke test for the GitHub collector.

Usage:
    .venv/bin/python scripts/smoke_github.py <gh_login> [days_back] [--no-cache]

Reads github_orgs from config/teams.yaml. Requires GITHUB_TOKEN in .env.
Prints summary + a sample of records. Re-runs are cached and fast.
Pass --no-cache to force a fresh fetch (cache is still updated).
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

from silo.cache import Cache
from silo.collectors.github import GitHubCollector
from silo.config import load_teams
from silo.paths import CACHE_DIR, CONFIG_DIR


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--no-cache"]
    no_cache = "--no-cache" in sys.argv
    if not args:
        print("usage: smoke_github.py <gh_login> [days_back=30] [--no-cache]", file=sys.stderr)
        return 2
    login = args[0]
    days_back = int(args[1]) if len(args) > 1 else 30

    load_dotenv()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN missing — copy .env.example to .env and fill it in.", file=sys.stderr)
        return 1

    teams = load_teams(CONFIG_DIR / "teams.yaml")
    to = date.today()
    frm = to - timedelta(days=days_back)

    cache = Cache(CACHE_DIR / "smoke.sqlite", bypass=no_cache)
    if no_cache:
        print("[cache bypass enabled — fetching fresh]\n")
    gh = GitHubCollector(token, teams.github_orgs, cache)

    print(f"querying {login} in {teams.github_orgs} from {frm} to {to}\n")

    prs = gh.prs_authored(login, frm, to)
    reviews = gh.reviews_given(login, frm, to)
    comments = gh.comments_left(login, frm, to)

    print(f"PRs authored:  {len(prs)}")
    print(f"reviews given: {len(reviews)}")
    print(f"comments left: {len(comments)}")

    if prs:
        print("\nfirst 3 PRs:")
        for p in prs[:3]:
            merged = p.merged_at.date() if p.merged_at else "unmerged"
            print(f"  {p.org}/{p.repo}#{p.number}  +{p.additions}/-{p.deletions}  merged={merged}")
    if reviews:
        print("\nfirst 3 reviews:")
        for r in reviews[:3]:
            print(
                f"  {r.pr_org}/{r.pr_repo}#{r.pr_number}  state={r.state}  "
                f"body={r.body_chars}ch  at={r.submitted_at.date()}"
            )

    cache.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
