"""SQLite-backed cache for collected raw records.

Cache key = (source, entity, from_date, to_date). 'entity' is a gh login or
google email depending on source. Stored payload is JSON of a list of raw records.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    source     TEXT NOT NULL,
    entity     TEXT NOT NULL,
    from_date  TEXT NOT NULL,
    to_date    TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    payload    TEXT NOT NULL,
    PRIMARY KEY (source, entity, from_date, to_date)
);
"""


class Cache:
    def __init__(self, db_path: Path, bypass: bool = False) -> None:
        """If bypass=True, get() always returns None (forces fresh fetch);
        put() still writes, so the new data is cached for subsequent non-bypass runs."""
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(SCHEMA)
        self._conn.commit()
        self._bypass = bypass

    def get(self, source: str, entity: str, frm: date, to: date) -> list[Any] | None:
        if self._bypass:
            return None
        row = self._conn.execute(
            "SELECT payload FROM cache WHERE source=? AND entity=? AND from_date=? AND to_date=?",
            (source, entity, frm.isoformat(), to.isoformat()),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def put(self, source: str, entity: str, frm: date, to: date, payload: list[Any]) -> None:
        from datetime import datetime, timezone

        self._conn.execute(
            "INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?, ?, ?)",
            (
                source,
                entity,
                frm.isoformat(),
                to.isoformat(),
                datetime.now(timezone.utc).isoformat(),
                json.dumps(payload, default=str),
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
