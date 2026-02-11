"""Persistent FX time-series samples for window analysis."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from octopusos.core.storage.paths import component_db_path

from .types import utc_now_iso


def _parse_datetime(value: str):
    from datetime import datetime, timezone

    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class FxTimeSeriesStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        path = Path(db_path) if db_path else component_db_path("octopusos")
        self.db_path = str(path)
        self._ensure_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS external_facts_fx_samples (
                    id TEXT PRIMARY KEY,
                    pair TEXT NOT NULL,
                    base TEXT NOT NULL,
                    quote TEXT NOT NULL,
                    rate REAL NOT NULL,
                    as_of TEXT NOT NULL,
                    source_name TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_external_facts_fx_samples_pair_as_of "
                "ON external_facts_fx_samples(pair, as_of DESC)"
            )

    def add_sample(
        self,
        *,
        pair: str,
        base: str,
        quote: str,
        rate: float,
        as_of: str,
        source_name: Optional[str] = None,
    ) -> None:
        created_at = utc_now_iso()
        sample_id = f"{pair}:{as_of}:{rate}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO external_facts_fx_samples(
                    id, pair, base, quote, rate, as_of, source_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample_id,
                    pair.upper(),
                    base.upper(),
                    quote.upper(),
                    float(rate),
                    as_of,
                    source_name or "",
                    created_at,
                ),
            )

    def list_window(
        self,
        *,
        base: str,
        quote: str,
        window_minutes: int,
        now_iso: str,
        limit: int = 300,
    ) -> List[Dict[str, Any]]:
        now_dt = _parse_datetime(now_iso)
        start_dt = now_dt - timedelta(minutes=max(1, int(window_minutes)))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT pair, base, quote, rate, as_of, source_name
                FROM external_facts_fx_samples
                WHERE base = ? AND quote = ? AND as_of >= ? AND as_of <= ?
                ORDER BY as_of ASC
                LIMIT ?
                """,
                (
                    base.upper(),
                    quote.upper(),
                    start_dt.isoformat(),
                    now_dt.isoformat(),
                    int(limit),
                ),
            ).fetchall()
        return [
            {
                "pair": row["pair"],
                "base": row["base"],
                "quote": row["quote"],
                "rate": float(row["rate"]),
                "as_of": row["as_of"],
                "source": row["source_name"] or "",
            }
            for row in rows
        ]
