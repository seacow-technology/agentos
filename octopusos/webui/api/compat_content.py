"""P1 compatibility router for content registry endpoints."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, Body, Header, HTTPException, Query

from octopusos.core.capabilities.admin_token import validate_admin_token
from octopusos.store import get_db_path
from octopusos.webui.api.compat_state import audit_event

router = APIRouter(prefix="/api/content", tags=["compat"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_connect() -> sqlite3.Connection:
    env_path = os.getenv("OCTOPUSOS_DB_PATH")
    db_path = Path(env_path) if env_path else get_db_path()
    if not db_path.exists():
        # Avoid 5xx for missing local state in e2e/smoke; treat as policy/unavailable.
        raise HTTPException(status_code=409, detail="Database not initialized")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS compat_content (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            source_uri TEXT,
            metadata TEXT,
            body TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT COUNT(*) AS c FROM compat_content").fetchone()
    if row and int(row["c"]) > 0:
        return
    now = _now_iso()
    conn.executemany(
        """
        INSERT INTO compat_content (
            id, type, name, version, status, source_uri, metadata, body, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "content:docs/ADR-001",
                "doc",
                "ADR-001",
                "1.0.0",
                "active",
                "docs/ADR-001.md",
                json.dumps({"description": "Architecture decision record seed item"}),
                "Compatibility seed content",
                now,
                now,
            ),
        ],
    )
    conn.commit()


def _require_admin_token(token: Optional[str]) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="Admin token required")
    if not validate_admin_token(token):
        raise HTTPException(status_code=403, detail="Invalid admin token")


def _to_content_item(row: sqlite3.Row) -> Dict[str, Any]:
    metadata = {}
    try:
        metadata = json.loads(row["metadata"] or "{}")
    except Exception:
        metadata = {}
    return {
        "id": row["id"],
        "type": row["type"],
        "name": row["name"],
        "title": row["name"],
        "version": row["version"],
        "status": row["status"],
        "source_uri": row["source_uri"],
        "metadata": metadata,
        "updated_at": row["updated_at"],
        "source": "compat",
    }


@router.get("")
def list_content(
    type: Optional[str] = Query(default=None),  # noqa: A002
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    conn = _db_connect()
    try:
        _ensure_table(conn)
        _seed_if_empty(conn)
        where = []
        params: list[Any] = []
        if type:
            where.append("type = ?")
            params.append(type)
        if status:
            where.append("status = ?")
            params.append(status)
        if search:
            where.append("(name LIKE ? OR id LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        where_sql = f" WHERE {' AND '.join(where)}" if where else ""

        total = int(conn.execute(f"SELECT COUNT(*) AS c FROM compat_content{where_sql}", params).fetchone()["c"])
        rows = conn.execute(
            f"SELECT * FROM compat_content{where_sql} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        items = [_to_content_item(r) for r in rows]
        return {
            "content": items,
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "source": "compat",
        }
    finally:
        conn.close()


@router.get("/{content_id:path}")
def get_content(content_id: str) -> Dict[str, Any]:
    # Special compatibility object consumed by ContentRegistryPage runtime mode bootstrap.
    if content_id == "mode":
        return {
            "content": {
                "id": "mode",
                "mode": "local",
                "features": {"admin_required": True},
                "source": "compat",
            }
        }

    conn = _db_connect()
    try:
        _ensure_table(conn)
        row = conn.execute("SELECT * FROM compat_content WHERE id = ?", (content_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Content not found")
        item = _to_content_item(row)
        body = row["body"] or ""
        return {
            "content": {
                **item,
                "body": body,
                "meta": item["metadata"],
            }
        }
    finally:
        conn.close()


@router.post("", status_code=201)
async def create_content(
    payload: Dict[str, Any] = Body(...),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    _require_admin_token(admin_token)

    content_type = payload.get("type")
    name = payload.get("name")
    version = payload.get("version")
    if not content_type or not name or not version:
        raise HTTPException(status_code=400, detail="type, name, and version are required")

    conn = _db_connect()
    try:
        _ensure_table(conn)
        content_id = payload.get("id") or f"content:{content_type}/{uuid4().hex[:10]}"
        now = _now_iso()
        metadata = payload.get("metadata", {})
        conn.execute(
            """
            INSERT INTO compat_content (
                id, type, name, version, status, source_uri, metadata, body, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                content_id,
                str(content_type),
                str(name),
                str(version),
                str(payload.get("status") or "active"),
                payload.get("source_uri"),
                json.dumps(metadata),
                payload.get("body"),
                now,
                now,
            ),
        )
        audit_event(
            conn,
            event_type="content_create",
            endpoint="/api/content",
            actor="admin",
            payload=payload,
            result={"id": content_id, "ok": True},
        )
        conn.commit()
        row = conn.execute("SELECT * FROM compat_content WHERE id = ?", (content_id,)).fetchone()
        item = _to_content_item(row)
        return {"ok": True, "data": item, "source": "compat"}
    finally:
        conn.close()
