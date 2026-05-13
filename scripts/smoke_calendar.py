"""Smoke test for the Google Calendar freebusy collector.

Usage:
    .venv/bin/python scripts/smoke_calendar.py <google_email> [days_back] [--no-cache]

Requires GOOGLE_OAUTH_CLIENT_ID + GOOGLE_OAUTH_CLIENT_SECRET in .env.
First run pops a browser consent flow; token is cached to ~/.config/silo/.

The given email can be your own or a coworker's; you'll get busy blocks back
if your org's Workspace settings allow freebusy sharing (default for most).
Pass --no-cache to force a fresh fetch.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv

logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")

from silo.cache import Cache
from silo.collectors.calendar import CalendarCollector
from silo.paths import CACHE_DIR


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--no-cache"]
    no_cache = "--no-cache" in sys.argv
    if not args:
        print("usage: smoke_calendar.py <google_email> [days_back=7] [--no-cache]", file=sys.stderr)
        return 2
    email = args[0]
    days_back = int(args[1]) if len(args) > 1 else 7

    load_dotenv()
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        print(
            "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET missing — "
            "create an OAuth client in Google Cloud Console (Desktop app) and fill in .env.",
            file=sys.stderr,
        )
        return 1

    to = date.today()
    frm = to - timedelta(days=days_back)

    cache = Cache(CACHE_DIR / "smoke.sqlite", bypass=no_cache)
    if no_cache:
        print("[cache bypass enabled — fetching fresh]\n")
    cal = CalendarCollector(client_id, client_secret, cache)

    print(f"querying freebusy for {email} from {frm} to {to}\n")
    blocks = cal.busy_blocks(email, frm, to)

    print(f"busy blocks: {len(blocks)}")
    if blocks:
        print("\nfirst 5:")
        for b in blocks[:5]:
            dur_min = int((b.end - b.start).total_seconds() / 60)
            print(f"  {b.start}  ->  {b.end}  ({dur_min} min)")
    else:
        print(
            "no blocks returned. Either the calendar has no events in the window, "
            "or your Workspace blocks freebusy sharing for this email."
        )

    cache.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
