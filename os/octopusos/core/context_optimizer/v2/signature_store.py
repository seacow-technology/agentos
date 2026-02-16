from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional


def default_store_path() -> Path:
    return Path.home() / ".octopusos" / "store" / "octopusos" / "optimizer_signatures.sqlite"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS signatures (
          signature TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          first_seen_ms INTEGER NOT NULL,
          last_seen_ms INTEGER NOT NULL,
          count INTEGER NOT NULL,
          sample_json TEXT
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_signatures_kind ON signatures(kind, last_seen_ms DESC);")
    conn.commit()


def upsert_signature(
    *,
    store_path: Optional[Path],
    signature: str,
    kind: str,
    sample: Optional[Dict[str, Any]] = None,
    now_ms: Optional[int] = None,
) -> Dict[str, Any]:
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    db = store_path or default_store_path()
    conn = _connect(db)
    try:
        ensure_schema(conn)
        # Atomic upsert to avoid race between SELECT and INSERT (multiple workers / UI requests).
        conn.execute(
            """
            INSERT INTO signatures(signature, kind, first_seen_ms, last_seen_ms, count, sample_json)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(signature) DO UPDATE SET
              last_seen_ms = excluded.last_seen_ms,
              count = signatures.count + 1
            ;
            """,
            (
                signature,
                kind,
                now_ms,
                now_ms,
                1,
                json.dumps(sample or {}, ensure_ascii=False),
            ),
        )
        conn.commit()
        # Determine if new by checking if first_seen_ms == now_ms and count == 1.
        row = conn.execute(
            "SELECT first_seen_ms, count FROM signatures WHERE signature = ?",
            (signature,),
        ).fetchone()
        is_new = bool(row and int(row["first_seen_ms"]) == now_ms and int(row["count"]) == 1)
        return {"signature": signature, "kind": kind, "count_delta": 1, "is_new": is_new, "db_path": str(db)}
    finally:
        conn.close()


def top_signatures(*, store_path: Optional[Path] = None, kind: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
    db = store_path or default_store_path()
    if not db.exists():
        return []
    conn = _connect(db)
    try:
        ensure_schema(conn)
        if kind:
            rows = conn.execute(
                "SELECT signature, kind, count, last_seen_ms FROM signatures WHERE kind = ? ORDER BY count DESC LIMIT ?",
                (kind, int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT signature, kind, count, last_seen_ms FROM signatures ORDER BY count DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def signatures_total(*, store_path: Optional[Path] = None) -> int:
    db = store_path or default_store_path()
    if not db.exists():
        return 0
    conn = _connect(db)
    try:
        ensure_schema(conn)
        row = conn.execute("SELECT COUNT(*) AS n FROM signatures").fetchone()
        return int(row["n"]) if row else 0
    finally:
        conn.close()
