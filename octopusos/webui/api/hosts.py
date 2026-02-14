"""SSH Hosts inventory API (BridgeOS).

Stores host definitions for SSH/SFTP connections.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from octopusos.webui.api.compat_state import ensure_schema as ensure_compat_schema
from octopusos.webui.api.shell import _audit_db_connect  # reuse audit DB connector
from octopusos.webui.api._db_bridgeos import connect_bridgeos, ensure_bridgeos_schema


router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _audit(event_type: str, *, endpoint: str, payload: Any, result: Any) -> None:
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _audit_db_connect()
        ensure_compat_schema(conn)
        from octopusos.webui.api import compat_state

        compat_state.audit_event(
            conn,
            event_type=event_type,
            endpoint=endpoint,
            actor="webui",
            payload=payload,
            result=result,
        )
        conn.commit()
    finally:
        if conn is not None:
            conn.close()


class HostIn(BaseModel):
    label: Optional[str] = Field(default=None, max_length=200)
    hostname: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class HostOut(BaseModel):
    host_id: str
    label: Optional[str]
    hostname: str
    port: int
    tags: List[str]
    meta: Dict[str, Any]
    created_at: str
    updated_at: str


def _row_to_host(row: sqlite3.Row) -> HostOut:
    try:
        tags = json.loads(row["tags_json"]) if row["tags_json"] else []
    except Exception:
        tags = []
    try:
        meta = json.loads(row["meta_json"]) if row["meta_json"] else {}
    except Exception:
        meta = {}
    return HostOut(
        host_id=str(row["host_id"]),
        label=row["label"],
        hostname=str(row["hostname"]),
        port=int(row["port"] or 22),
        tags=list(tags) if isinstance(tags, list) else [],
        meta=dict(meta) if isinstance(meta, dict) else {},
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


@router.get("/api/hosts", response_model=List[HostOut])
def hosts_list() -> List[HostOut]:
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        rows = conn.execute(
            "SELECT host_id, label, hostname, port, tags_json, meta_json, created_at, updated_at FROM hosts ORDER BY updated_at DESC"
        ).fetchall()
        return [_row_to_host(r) for r in rows]
    finally:
        conn.close()


@router.post("/api/hosts", response_model=HostOut)
def hosts_create(payload: HostIn) -> HostOut:
    host_id = uuid4().hex
    now = _now_iso()
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        conn.execute(
            """
            INSERT INTO hosts (host_id, label, hostname, port, tags_json, meta_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                host_id,
                payload.label,
                payload.hostname.strip(),
                int(payload.port),
                json.dumps(payload.tags, ensure_ascii=False, sort_keys=True),
                json.dumps(payload.meta, ensure_ascii=False, sort_keys=True),
                now,
                now,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT host_id, label, hostname, port, tags_json, meta_json, created_at, updated_at FROM hosts WHERE host_id = ?",
            (host_id,),
        ).fetchone()
        assert row is not None
        host = _row_to_host(row)
    finally:
        conn.close()

    _audit(
        "ssh.host.create",
        endpoint="/api/hosts",
        payload={"host_id": host_id, "hostname": host.hostname, "port": host.port, "capability_id": "ssh.exec"},
        result={"ok": True},
    )
    return host


@router.get("/api/hosts/{host_id}", response_model=HostOut)
def hosts_get(host_id: str) -> HostOut:
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        row = conn.execute(
            "SELECT host_id, label, hostname, port, tags_json, meta_json, created_at, updated_at FROM hosts WHERE host_id = ?",
            (host_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="host not found")
        return _row_to_host(row)
    finally:
        conn.close()


@router.put("/api/hosts/{host_id}", response_model=HostOut)
def hosts_update(host_id: str, payload: HostIn) -> HostOut:
    now = _now_iso()
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        existing = conn.execute("SELECT host_id FROM hosts WHERE host_id = ?", (host_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="host not found")
        conn.execute(
            """
            UPDATE hosts
            SET label = ?, hostname = ?, port = ?, tags_json = ?, meta_json = ?, updated_at = ?
            WHERE host_id = ?
            """,
            (
                payload.label,
                payload.hostname.strip(),
                int(payload.port),
                json.dumps(payload.tags, ensure_ascii=False, sort_keys=True),
                json.dumps(payload.meta, ensure_ascii=False, sort_keys=True),
                now,
                host_id,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT host_id, label, hostname, port, tags_json, meta_json, created_at, updated_at FROM hosts WHERE host_id = ?",
            (host_id,),
        ).fetchone()
        assert row is not None
        host = _row_to_host(row)
    finally:
        conn.close()

    _audit(
        "ssh.host.update",
        endpoint=f"/api/hosts/{host_id}",
        payload={"host_id": host_id, "capability_id": "ssh.exec"},
        result={"ok": True},
    )
    return host


@router.delete("/api/hosts/{host_id}")
def hosts_delete(host_id: str) -> Dict[str, Any]:
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        row = conn.execute("SELECT host_id FROM hosts WHERE host_id = ?", (host_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="host not found")
        conn.execute("DELETE FROM hosts WHERE host_id = ?", (host_id,))
        conn.commit()
    finally:
        conn.close()

    _audit(
        "ssh.host.delete",
        endpoint=f"/api/hosts/{host_id}",
        payload={"host_id": host_id, "capability_id": "ssh.exec"},
        result={"ok": True},
    )
    return {"ok": True, "host_id": host_id}

