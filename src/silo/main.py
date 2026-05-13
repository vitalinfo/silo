"""Entry point: load configs, collect, aggregate, render reports.

Run with:  silo            (uses config/teams.yaml + config/run.yaml)
"""
from __future__ import annotations

import os
from datetime import datetime

from dotenv import load_dotenv

from .paths import CACHE_DIR, CONFIG_DIR, REPORTS_DIR


def run() -> None:
    load_dotenv()

    teams_path = CONFIG_DIR / "teams.yaml"
    run_path = CONFIG_DIR / "run.yaml"

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = REPORTS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    gh_token = os.environ["GITHUB_TOKEN"]
    google_client_id = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
    google_client_secret = os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]
    anthropic_key = os.environ["ANTHROPIC_API_KEY"]

    # TODO: load configs, build collectors + cache, run aggregator across
    # (period, team) pairs, hand resulting PeriodReports to enabled renderers.
    _ = (teams_path, run_path, gh_token, google_client_id, google_client_secret, anthropic_key, CACHE_DIR)
    raise NotImplementedError("wired in next chunk")


if __name__ == "__main__":
    run()
