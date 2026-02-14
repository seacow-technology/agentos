"""Known hosts API (BridgeOS).

Maintains SSH fingerprints without touching system known_hosts file.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from octopusos.webui.api.compat_state import ensure_schema as ensure_compat_schema
from octopusos.webui.api.shell import _audit_db_connect  # reuse audit DB connector
from octopusos.webui.api._db_bridgeos import connect_bridgeos, ensure_bridgeos_schema
from octopusos.webui.api._gate_errors import gate_detail


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


class KnownHostIn(BaseModel):
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    fingerprint: str = Field(..., min_length=1, max_length=512)
    algo: Optional[str] = Field(default=None, max_length=64)


class KnownHostReplaceIn(BaseModel):
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    fingerprint: str = Field(..., min_length=1, max_length=512)
    algo: Optional[str] = Field(default=None, max_length=64)
    confirm: bool = False
    confirm_token: Optional[str] = Field(default=None, max_length=200)
    reason: Optional[str] = Field(default=None, max_length=2000)


class KnownHostOut(BaseModel):
    known_host_id: str
    host: str
    port: int
    fingerprint: str
    algo: Optional[str]
    created_at: str


def _row_to_item(row: sqlite3.Row) -> KnownHostOut:
    return KnownHostOut(
        known_host_id=str(row["known_host_id"]),
        host=str(row["host"]),
        port=int(row["port"] or 22),
        fingerprint=str(row["fingerprint"]),
        algo=row["algo"],
        created_at=str(row["created_at"]),
    )


@router.get("/api/known_hosts", response_model=List[KnownHostOut])
def known_hosts_list() -> List[KnownHostOut]:
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        rows = conn.execute(
            "SELECT known_host_id, host, port, fingerprint, algo, created_at FROM known_hosts ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_item(r) for r in rows]
    finally:
        conn.close()


@router.post("/api/known_hosts", response_model=KnownHostOut)
def known_hosts_add(payload: KnownHostIn) -> KnownHostOut:
    known_host_id = uuid4().hex
    now = _now_iso()
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        conn.execute(
            """
            INSERT INTO known_hosts (known_host_id, host, port, fingerprint, algo, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                known_host_id,
                payload.host.strip(),
                int(payload.port),
                payload.fingerprint.strip(),
                payload.algo.strip() if payload.algo else None,
                now,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT known_host_id, host, port, fingerprint, algo, created_at FROM known_hosts WHERE known_host_id = ?",
            (known_host_id,),
        ).fetchone()
        assert row is not None
        item = _row_to_item(row)
    finally:
        conn.close()

    _audit(
        "known_hosts.add",
        endpoint="/api/known_hosts",
        payload={"known_host_id": known_host_id, "host": item.host, "port": item.port, "capability_id": "ssh.exec"},
        result={"ok": True},
    )
    # Trust gate decision signal (used by ssh.exec / sftp.transfer flows).
    _audit(
        "known_hosts.trusted",
        endpoint="/api/known_hosts",
        payload={
            "known_host_id": known_host_id,
            "host": item.host,
            "port": item.port,
            "fingerprint": item.fingerprint,
            "algo": item.algo,
            "capability_id": "ssh.exec",
            "risk_tier": "MEDIUM",
        },
        result={"ok": True},
    )
    return item


@router.delete("/api/known_hosts/{known_host_id}")
def known_hosts_remove(known_host_id: str) -> Dict[str, Any]:
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        row = conn.execute(
            "SELECT known_host_id FROM known_hosts WHERE known_host_id = ?",
            (known_host_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="known_host not found")
        conn.execute("DELETE FROM known_hosts WHERE known_host_id = ?", (known_host_id,))
        conn.commit()
    finally:
        conn.close()

    _audit(
        "known_hosts.remove",
        endpoint=f"/api/known_hosts/{known_host_id}",
        payload={"known_host_id": known_host_id, "capability_id": "ssh.exec"},
        result={"ok": True},
    )
    return {"ok": True, "known_host_id": known_host_id}


@router.post("/api/known_hosts/replace")
def known_hosts_replace(payload: KnownHostReplaceIn) -> Dict[str, Any]:
    """Replace all known_hosts entries for (host, port) with the provided fingerprint.

    This is a HIGH-risk operation and requires two-step confirmation:
    1) call without confirm -> 409 CONFIRM_REQUIRED + confirm_token
    2) call with confirm + confirm_token + reason -> apply replacement
    """
    host = payload.host.strip()
    port = int(payload.port)
    fp = payload.fingerprint.strip()
    algo = payload.algo.strip() if payload.algo else None

    if not payload.confirm:
        request_id = uuid4().hex
        now = _now_iso()
        conn = connect_bridgeos()
        try:
            ensure_bridgeos_schema(conn)
            conn.execute(
                """
                INSERT INTO known_hosts_replace_requests (request_id, host, port, fingerprint, algo, status, reason, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (request_id, host, port, fp, algo, "CONFIRM_REQUIRED", None, now, now),
            )
            conn.commit()
        finally:
            conn.close()

        _audit(
            "known_hosts.replace.confirm_required",
            endpoint="/api/known_hosts/replace",
            payload={
                "request_id": request_id,
                "host": host,
                "port": port,
                "fingerprint": fp,
                "algo": algo,
                "capability_id": "ssh.exec",
                "risk_tier": "HIGH",
            },
            result={"ok": False, "error_code": "CONFIRM_REQUIRED"},
        )
        raise HTTPException(
            status_code=409,
            detail=gate_detail(
                error_code="CONFIRM_REQUIRED",
                gate="confirm",
                confirm_token=request_id,
                message="High-risk operation. Re-submit with confirm=true, confirm_token, and reason to proceed.",
                context={"request_id": request_id, "host": host, "port": port, "fingerprint": fp, "algo": algo},
                capability_id="ssh.exec",
                risk_tier="HIGH",
            ),
        )

    token = (payload.confirm_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="missing confirm_token")
    reason = (payload.reason or "").strip()
    if len(reason) < 10:
        raise HTTPException(status_code=400, detail="reason required (min 10 chars)")

    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        row = conn.execute(
            "SELECT request_id, status, host, port, fingerprint FROM known_hosts_replace_requests WHERE request_id = ?",
            (token,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="confirm token not found")
        if str(row["status"]) != "CONFIRM_REQUIRED":
            raise HTTPException(
                status_code=409,
                detail=gate_detail(
                    error_code="INVALID_CONFIRM_TOKEN",
                    gate="confirm",
                    message="token already used",
                    context={"request_id": token, "host": host, "port": port, "fingerprint": fp, "algo": algo},
                    capability_id="ssh.exec",
                    risk_tier="HIGH",
                ),
            )
        if str(row["host"]) != host or int(row["port"] or 22) != port or str(row["fingerprint"]) != fp:
            raise HTTPException(
                status_code=409,
                detail=gate_detail(
                    error_code="INVALID_CONFIRM_TOKEN",
                    gate="confirm",
                    message="payload mismatch",
                    context={"request_id": token, "host": host, "port": port, "fingerprint": fp, "algo": algo},
                    capability_id="ssh.exec",
                    risk_tier="HIGH",
                ),
            )

        removed = conn.execute("SELECT COUNT(*) AS n FROM known_hosts WHERE host = ? AND port = ?", (host, port)).fetchone()[0]
        conn.execute("DELETE FROM known_hosts WHERE host = ? AND port = ?", (host, port))
        known_host_id = uuid4().hex
        now = _now_iso()
        conn.execute(
            """
            INSERT INTO known_hosts (known_host_id, host, port, fingerprint, algo, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (known_host_id, host, port, fp, algo, now),
        )
        conn.execute(
            "UPDATE known_hosts_replace_requests SET status = ?, reason = ?, updated_at = ? WHERE request_id = ?",
            ("COMPLETED", reason, now, token),
        )
        conn.commit()
    finally:
        conn.close()

    _audit(
        "known_hosts.replaced",
        endpoint="/api/known_hosts/replace",
        payload={
            "request_id": token,
            "host": host,
            "port": port,
            "fingerprint": fp,
            "algo": algo,
            "reason": reason,
            "removed_count": int(removed),
            "capability_id": "ssh.exec",
            "risk_tier": "HIGH",
        },
        result={"ok": True},
    )
    return {"ok": True, "known_host_id": known_host_id, "host": host, "port": port, "fingerprint": fp, "algo": algo, "removed_count": int(removed)}
