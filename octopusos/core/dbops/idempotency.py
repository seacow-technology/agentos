from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(slots=True)
class IdempotencyRecord:
    token: str
    status: str
    result: Optional[Dict[str, Any]]


class DBOpsIdempotencyStore:
    """Minimal sqlite-backed idempotency store for confirm token execution safety."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dbops_confirm_tokens (
                    token TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                    updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
                )
                """
            )
            conn.commit()

    def get(self, token: str) -> Optional[IdempotencyRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT token, status, result_json FROM dbops_confirm_tokens WHERE token = ?",
                (token,),
            ).fetchone()
            if not row:
                return None
            result = json.loads(row[2]) if row[2] else None
            return IdempotencyRecord(token=row[0], status=row[1], result=result)

    def begin_once(self, token: str) -> IdempotencyRecord:
        """
        Attempt to begin execution for token.
        - If token does not exist: inserts PENDING and returns PENDING.
        - If token exists: returns existing record.
        """
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO dbops_confirm_tokens (token, status, result_json)
                VALUES (?, 'PENDING', NULL)
                """,
                (token,),
            )
            conn.commit()

        rec = self.get(token)
        if rec is None:
            # Defensive fallback; should never happen after INSERT OR IGNORE
            return IdempotencyRecord(token=token, status="PENDING", result=None)
        return rec

    def mark_executed(self, token: str, result: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE dbops_confirm_tokens
                SET status = 'EXECUTED',
                    result_json = ?,
                    updated_at = strftime('%s','now')
                WHERE token = ?
                """,
                (json.dumps(result, ensure_ascii=False), token),
            )
            conn.commit()

    def mark_failed(self, token: str, result: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE dbops_confirm_tokens
                SET status = 'FAILED',
                    result_json = ?,
                    updated_at = strftime('%s','now')
                WHERE token = ?
                """,
                (json.dumps(result, ensure_ascii=False), token),
            )
            conn.commit()
