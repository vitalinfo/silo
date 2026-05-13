"""Google Calendar freebusy collector.

Uses freebusy.query to read busy blocks for any calendar shared with the
authenticated user (typical Workspace default). Stores no event detail —
only (email, start, end) intervals.

OAuth: first call triggers a browser consent flow. The resulting token is
cached at ~/.config/silo/google_token.json and auto-refreshed thereafter.

Freebusy windows are capped at ~90 days per query, so longer periods are
fetched in chunks. Results are cached per (source, google_email, from, to).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterator

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from ..cache import Cache
from ..paths import GOOGLE_TOKEN_PATH
from ..types import BusyBlock

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.freebusy"]
MAX_WINDOW_DAYS = 90


class CalendarCollector:
    SOURCE = "google:busy"

    def __init__(
        self,
        oauth_client_id: str,
        oauth_client_secret: str,
        cache: Cache,
        token_path: Path | None = None,
    ) -> None:
        self._client_id = oauth_client_id
        self._client_secret = oauth_client_secret
        self._cache = cache
        self._token_path = token_path or GOOGLE_TOKEN_PATH
        self._service = None

    def busy_blocks(self, google_email: str, frm: date, to: date) -> list[BusyBlock]:
        cached = self._cache.get(self.SOURCE, google_email, frm, to)
        if cached is not None:
            return [BusyBlock.model_validate(r) for r in cached]

        service = self._authenticate()
        results: list[BusyBlock] = []

        for window_start, window_end in _split_windows(frm, to, MAX_WINDOW_DAYS):
            time_min = datetime.combine(window_start, time.min, tzinfo=timezone.utc).isoformat()
            time_max = datetime.combine(window_end, time.max, tzinfo=timezone.utc).isoformat()
            body = {"timeMin": time_min, "timeMax": time_max, "items": [{"id": google_email}]}
            resp = service.freebusy().query(body=body).execute()

            cal = resp.get("calendars", {}).get(google_email, {})
            errs = cal.get("errors")
            if errs:
                log.warning("freebusy errors for %s in %s..%s: %s", google_email, window_start, window_end, errs)
                continue
            for slot in cal.get("busy", []):
                results.append(
                    BusyBlock(
                        google_email=google_email,
                        start=_parse_rfc3339(slot["start"]),
                        end=_parse_rfc3339(slot["end"]),
                    )
                )

        self._cache.put(
            self.SOURCE, google_email, frm, to,
            [r.model_dump(mode="json") for r in results],
        )
        return results

    # --- internal ------------------------------------------------------

    def _authenticate(self):
        if self._service is not None:
            return self._service

        creds: Credentials | None = None
        if self._token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self._token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                client_config = {
                    "installed": {
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["http://localhost"],
                    }
                }
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                creds = flow.run_local_server(port=0)
            self._token_path.parent.mkdir(parents=True, exist_ok=True)
            self._token_path.write_text(creds.to_json())

        self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return self._service


def _split_windows(frm: date, to: date, max_days: int) -> Iterator[tuple[date, date]]:
    cur = frm
    while cur <= to:
        end = min(cur + timedelta(days=max_days - 1), to)
        yield cur, end
        cur = end + timedelta(days=1)


def _parse_rfc3339(s: str) -> datetime:
    # Python 3.11's fromisoformat doesn't accept trailing 'Z'.
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
