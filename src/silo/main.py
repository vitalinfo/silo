"""Entry point: load configs, collect, aggregate, render reports.

Usage:
    silo                       # read config/teams.yaml + config/run.yaml, write reports/<ts>/
    silo --no-cache            # force fresh fetch (cache still updated)
    silo --skip-narrative      # render markdown without Claude API calls
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .aggregate import build_period_report
from .cache import Cache
from .collectors.calendar import CalendarCollector
from .collectors.github import GitHubCollector
from .config import RunConfig, TeamsConfig, load_run, load_teams
from .paths import CACHE_DIR, CONFIG_DIR, REPORTS_DIR
from .report import exec as exec_report
from .report import team_lead

log = logging.getLogger(__name__)


def run() -> int:
    parser = argparse.ArgumentParser(prog="silo", description=__doc__)
    parser.add_argument("--no-cache", action="store_true", help="force fresh fetch")
    parser.add_argument(
        "--skip-narrative",
        action="store_true",
        help="render markdown without calling Claude (useful for dry runs)",
    )
    parser.add_argument(
        "--teams-config",
        default=str(CONFIG_DIR / "teams.yaml"),
        help="path to teams.yaml (default: config/teams.yaml)",
    )
    parser.add_argument(
        "--run-config",
        default=str(CONFIG_DIR / "run.yaml"),
        help="path to run.yaml (default: config/run.yaml)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    load_dotenv()

    gh_token = os.environ.get("GITHUB_TOKEN")
    google_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    google_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    missing = [
        name
        for name, val in [
            ("GITHUB_TOKEN", gh_token),
            ("GOOGLE_OAUTH_CLIENT_ID", google_id),
            ("GOOGLE_OAUTH_CLIENT_SECRET", google_secret),
        ]
        if not val
    ]
    if missing:
        print(f"missing env vars: {', '.join(missing)}", file=sys.stderr)
        return 1
    if not args.skip_narrative and not anthropic_key:
        print(
            "ANTHROPIC_API_KEY missing. Pass --skip-narrative to render without it.",
            file=sys.stderr,
        )
        return 1

    teams_cfg = load_teams(Path(args.teams_config))
    run_cfg = load_run(Path(args.run_config))
    teams = run_cfg.resolve_teams(teams_cfg)
    periods = sorted(run_cfg.periods, key=lambda p: p.to)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = REPORTS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("output dir: %s", out_dir)

    cache = Cache(CACHE_DIR / "silo.sqlite", bypass=args.no_cache)
    if args.no_cache:
        log.info("cache bypass enabled — fetching fresh")
    gh = GitHubCollector(gh_token, teams_cfg.github_orgs, cache)
    cal = CalendarCollector(google_id, google_secret, cache)

    # Build PeriodReports for every (team, period). Cache makes repeats cheap.
    all_reports = []
    for team in teams:
        for period in periods:
            log.info("aggregating team=%s period=%s", team.name, period.label)
            all_reports.append(build_period_report(team, period, run_cfg, gh, cal))

    api_key = None if args.skip_narrative else anthropic_key
    written: list[Path] = []

    if "team_lead" in run_cfg.reports:
        for team in teams:
            team_reports = [r for r in all_reports if r.team == team.name]
            written.append(team_lead.render(team.name, team_reports, out_dir, api_key))

    if "exec" in run_cfg.reports:
        written.append(exec_report.render(all_reports, out_dir, api_key))

    gh.close()
    print("\nReports written:")
    for p in written:
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
