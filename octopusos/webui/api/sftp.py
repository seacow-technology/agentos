"""SFTP API (BridgeOS).

Default behavior is probe-only for CI stability.
Real network SFTP operations require explicit opt-in via OCTO_SSH_REAL=1.
"""

from __future__ import annotations

import hashlib
import io
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from octopusos.webui.api.compat_state import ensure_schema as ensure_compat_schema
from octopusos.webui.api.shell import _audit_db_connect
from octopusos.webui.api._db_bridgeos import connect_bridgeos, ensure_bridgeos_schema
from octopusos.webui.api._gate_errors import gate_detail
from octopusos.webui.api._ssh_config import ssh_default_timeout_ms, ssh_probe_only, ssh_real_enabled
from octopusos.webui.api._ssh_trust import get_fingerprint, is_trusted
from octopusos.core.providers.ssh_provider_registry import resolve_ssh_provider
from octopusos.execution import get_capability
from octopusos.execution.gate import policy_gate
from octopusos.providers.factory import get_ssh_provider


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


def _enforce_provider_policy(*, cap, endpoint: str) -> None:
    selection = resolve_ssh_provider()
    if selection.provider == "mcp":
        policy_gate(
            capability=cap,
            error_code="PROVIDER_UNAVAILABLE",
            message="Selected SSH provider is MCP but it is not available in this build.",
            context={"provider": "mcp", "endpoint": endpoint},
        )
    if selection.provider == "system" and not bool(selection.allow_real):
        policy_gate(
            capability=cap,
            error_code="REAL_NOT_ALLOWED",
            message="Real SSH provider is disabled by policy (allow_real=false).",
            context={"provider": "system", "endpoint": endpoint},
        )


class SftpOpenRequest(BaseModel):
    connection_id: str = Field(..., min_length=1, max_length=128)


class SftpOpenResponse(BaseModel):
    session_id: str


class SftpListResponse(BaseModel):
    ok: bool
    session_id: str
    path: str
    items: List[Dict[str, Any]]


class SftpDownloadRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=4096)


class SftpRemoveRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=4096)
    confirm: bool = False
    confirm_token: Optional[str] = Field(default=None, max_length=200)
    reason: Optional[str] = Field(default=None, max_length=2000)


@router.post("/api/sftp/sessions/open", response_model=SftpOpenResponse)
def sftp_open(payload: SftpOpenRequest) -> SftpOpenResponse:
    sftp_session_id = uuid4().hex
    now = _now_iso()
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        row = conn.execute(
            "SELECT connection_id FROM ssh_connections WHERE connection_id = ?",
            (payload.connection_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="connection not found")
        conn.execute(
            """
            INSERT INTO sftp_sessions (sftp_session_id, connection_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sftp_session_id, payload.connection_id, "OPEN", now, now),
        )
        conn.commit()
    finally:
        conn.close()

    _audit(
        "sftp.session.open",
        endpoint="/api/sftp/sessions/open",
        payload={"sftp_session_id": sftp_session_id, "connection_id": payload.connection_id, "capability_id": "sftp.transfer", "risk_tier": "MEDIUM"},
        result={"ok": True},
    )
    return SftpOpenResponse(session_id=sftp_session_id)


@router.get("/api/sftp/sessions/{session_id}/list", response_model=SftpListResponse)
def sftp_list(session_id: str, path: str = Query(default=".")) -> SftpListResponse:
    timeout_ms = ssh_default_timeout_ms()
    cap = get_capability("sftp.transfer")
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        row = conn.execute(
            "SELECT sftp_session_id, connection_id FROM sftp_sessions WHERE sftp_session_id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="sftp session not found")
        # Trust gate (probe + real)
        conn_row = conn.execute(
            "SELECT host_id, username, auth_ref, probe_only FROM ssh_connections WHERE connection_id = ?",
            (str(row["connection_id"]),),
        ).fetchone()
        if not conn_row:
            raise HTTPException(status_code=404, detail="connection not found")
        host_row = conn.execute(
            "SELECT hostname, port FROM hosts WHERE host_id = ?",
            (str(conn_row["host_id"]),),
        ).fetchone()
        if not host_row:
            raise HTTPException(status_code=404, detail="host not found")
        hostname = str(host_row["hostname"])
        port = int(host_row["port"] or 22)
        fp = get_fingerprint(hostname, port)
        trusted, mismatch = is_trusted(conn, hostname=hostname, port=port, fingerprint=fp.fingerprint)
        if not trusted:
            _audit(
                "known_hosts.missing",
                endpoint=f"/api/sftp/sessions/{session_id}/list",
                payload={
                    "session_id": session_id,
                    "connection_id": str(row["connection_id"]),
                    "host": hostname,
                    "port": port,
                    "fingerprint": fp.fingerprint,
                    "algo": fp.algo,
                    "capability_id": "sftp.transfer",
                    "risk_tier": "MEDIUM",
                },
                result={"ok": False, "error_code": mismatch or "NEEDS_TRUST"},
            )
            raise HTTPException(
                status_code=409,
                detail=gate_detail(
                    error_code=mismatch or "NEEDS_TRUST",
                    gate="trust",
                    message="Host key not trusted. Add it to Known Hosts to proceed.",
                    context={"host": hostname, "port": port, "fingerprint": fp.fingerprint, "algo": fp.algo},
                    capability_id="sftp.transfer",
                    risk_tier="MEDIUM",
                ),
            )
    finally:
        conn.close()

    probe_only = bool(int(conn_row["probe_only"] or 0))
    is_real = not (probe_only or ssh_probe_only() or not ssh_real_enabled())
    _enforce_provider_policy(cap=cap, endpoint=f"/api/sftp/sessions/{session_id}/list")
    provider = get_ssh_provider(allow_real=is_real)
    username = str(conn_row["username"] or "").strip() or None
    auth_ref = str(conn_row["auth_ref"] or "").strip() or None

    items2 = provider.sftp_list(hostname=hostname, port=port, username=username, auth_ref=auth_ref, path=path, timeout_ms=timeout_ms)
    items = [{"name": it.name, "type": it.type, "size": it.size} for it in items2]

    _audit(
        "sftp.list",
        endpoint=f"/api/sftp/sessions/{session_id}/list",
        payload={"session_id": session_id, "path": path, "capability_id": cap.id, "risk_tier": cap.risk_tier.value},
        result={"ok": True, "items": len(items)},
    )
    return SftpListResponse(ok=True, session_id=session_id, path=path, items=items)


@router.post("/api/sftp/sessions/{session_id}/download")
def sftp_download(session_id: str, payload: SftpDownloadRequest):
    timeout_ms = ssh_default_timeout_ms()
    transfer_id = uuid4().hex
    cap = get_capability("sftp.transfer")

    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        srow = conn.execute(
            "SELECT sftp_session_id, connection_id FROM sftp_sessions WHERE sftp_session_id = ?",
            (session_id,),
        ).fetchone()
        if not srow:
            raise HTTPException(status_code=404, detail="sftp session not found")
        crow = conn.execute(
            "SELECT host_id, username, auth_ref, probe_only FROM ssh_connections WHERE connection_id = ?",
            (str(srow["connection_id"]),),
        ).fetchone()
        if not crow:
            raise HTTPException(status_code=404, detail="connection not found")
        hrow = conn.execute(
            "SELECT hostname, port FROM hosts WHERE host_id = ?",
            (str(crow["host_id"]),),
        ).fetchone()
        if not hrow:
            raise HTTPException(status_code=404, detail="host not found")
        hostname = str(hrow["hostname"])
        port = int(hrow["port"] or 22)
        fp = get_fingerprint(hostname, port)
        trusted, mismatch = is_trusted(conn, hostname=hostname, port=port, fingerprint=fp.fingerprint)
        if not trusted:
            raise HTTPException(
                status_code=409,
                detail=gate_detail(
                    error_code=mismatch or "NEEDS_TRUST",
                    gate="trust",
                    message="Host key not trusted. Add it to Known Hosts to proceed.",
                    context={"host": hostname, "port": port, "fingerprint": fp.fingerprint, "algo": fp.algo},
                    capability_id=cap.id,
                    risk_tier=cap.risk_tier.value,
                ),
            )

        probe_only = bool(int(crow["probe_only"] or 0))
        is_real = not (probe_only or ssh_probe_only() or not ssh_real_enabled())
        _enforce_provider_policy(cap=cap, endpoint=f"/api/sftp/sessions/{session_id}/download")
        provider = get_ssh_provider(allow_real=is_real)
        username = str(crow["username"] or "").strip() or None
        auth_ref = str(crow["auth_ref"] or "").strip() or None

        # Perform download to a local temp file (provider-managed).
        tmp_path, t = provider.sftp_download(
            hostname=hostname,
            port=port,
            username=username,
            auth_ref=auth_ref,
            remote_path=payload.path,
            timeout_ms=timeout_ms,
        )

        with open(tmp_path, "rb") as f:
            content = f.read()
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        sha = hashlib.sha256(content).hexdigest()
        now = _now_iso()
        conn.execute(
            """
            INSERT INTO sftp_transfers (transfer_id, sftp_session_id, direction, remote_path, bytes_total, bytes_done, status, started_at, finished_at, sha256)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transfer_id,
                session_id,
                "download",
                payload.path,
                len(content),
                len(content),
                "COMPLETED" if not t.error_code else "FAILED",
                now,
                now,
                sha,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    _audit(
        "sftp.download",
        endpoint=f"/api/sftp/sessions/{session_id}/download",
        payload={"session_id": session_id, "transfer_id": transfer_id, "remote_path": payload.path, "capability_id": cap.id, "risk_tier": cap.risk_tier.value},
        result={"ok": True, "bytes": len(content), "transfer_id": transfer_id, "sha256": sha},
    )
    return StreamingResponse(io.BytesIO(content), media_type="application/octet-stream")


@router.post("/api/sftp/sessions/{session_id}/upload")
async def sftp_upload(session_id: str, path: str = Query(...), file: UploadFile = File(...)) -> Dict[str, Any]:
    timeout_ms = ssh_default_timeout_ms()
    data = await file.read()
    sha = hashlib.sha256(data).hexdigest()
    transfer_id = uuid4().hex
    cap = get_capability("sftp.transfer")

    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        srow = conn.execute(
            "SELECT sftp_session_id, connection_id FROM sftp_sessions WHERE sftp_session_id = ?",
            (session_id,),
        ).fetchone()
        if not srow:
            raise HTTPException(status_code=404, detail="sftp session not found")
        crow = conn.execute(
            "SELECT host_id, username, auth_ref, probe_only FROM ssh_connections WHERE connection_id = ?",
            (str(srow["connection_id"]),),
        ).fetchone()
        if not crow:
            raise HTTPException(status_code=404, detail="connection not found")
        hrow = conn.execute(
            "SELECT hostname, port FROM hosts WHERE host_id = ?",
            (str(crow["host_id"]),),
        ).fetchone()
        if not hrow:
            raise HTTPException(status_code=404, detail="host not found")
        hostname = str(hrow["hostname"])
        port = int(hrow["port"] or 22)
        fp = get_fingerprint(hostname, port)
        trusted, mismatch = is_trusted(conn, hostname=hostname, port=port, fingerprint=fp.fingerprint)
        if not trusted:
            raise HTTPException(
                status_code=409,
                detail=gate_detail(
                    error_code=mismatch or "NEEDS_TRUST",
                    gate="trust",
                    message="Host key not trusted. Add it to Known Hosts to proceed.",
                    context={"host": hostname, "port": port, "fingerprint": fp.fingerprint, "algo": fp.algo},
                    capability_id=cap.id,
                    risk_tier=cap.risk_tier.value,
                ),
            )

        probe_only = bool(int(crow["probe_only"] or 0))
        is_real = not (probe_only or ssh_probe_only() or not ssh_real_enabled())
        _enforce_provider_policy(cap=cap, endpoint=f"/api/sftp/sessions/{session_id}/upload")
        provider = get_ssh_provider(allow_real=is_real)
        username = str(crow["username"] or "").strip() or None
        auth_ref = str(crow["auth_ref"] or "").strip() or None

        t = provider.sftp_upload(
            hostname=hostname,
            port=port,
            username=username,
            auth_ref=auth_ref,
            remote_path=path,
            content=data,
            timeout_ms=timeout_ms,
        )

        now = _now_iso()
        conn.execute(
            """
            INSERT INTO sftp_transfers (transfer_id, sftp_session_id, direction, remote_path, bytes_total, bytes_done, status, started_at, finished_at, sha256)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transfer_id,
                session_id,
                "upload",
                path,
                len(data),
                len(data),
                "COMPLETED" if not t.error_code else "FAILED",
                now,
                now,
                sha,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    _audit(
        "sftp.upload",
        endpoint=f"/api/sftp/sessions/{session_id}/upload",
        payload={"session_id": session_id, "transfer_id": transfer_id, "remote_path": path, "sha256": sha, "capability_id": cap.id, "risk_tier": cap.risk_tier.value},
        result={"ok": True, "bytes": len(data), "transfer_id": transfer_id},
    )
    return {"ok": True, "session_id": session_id, "transfer_id": transfer_id, "remote_path": path, "bytes": len(data), "sha256": sha}


@router.post("/api/sftp/sessions/{session_id}/remove")
def sftp_remove(session_id: str, payload: SftpRemoveRequest) -> Dict[str, Any]:
    timeout_ms = ssh_default_timeout_ms()
    cap = get_capability("sftp.transfer")

    if "\n" in payload.path or "\r" in payload.path:
        raise HTTPException(status_code=400, detail="invalid path")

    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        srow = conn.execute(
            "SELECT sftp_session_id, connection_id FROM sftp_sessions WHERE sftp_session_id = ?",
            (session_id,),
        ).fetchone()
        if not srow:
            raise HTTPException(status_code=404, detail="sftp session not found")
        crow = conn.execute(
            "SELECT host_id, username, auth_ref, probe_only FROM ssh_connections WHERE connection_id = ?",
            (str(srow["connection_id"]),),
        ).fetchone()
        if not crow:
            raise HTTPException(status_code=404, detail="connection not found")
        hrow = conn.execute(
            "SELECT hostname, port FROM hosts WHERE host_id = ?",
            (str(crow["host_id"]),),
        ).fetchone()
        if not hrow:
            raise HTTPException(status_code=404, detail="host not found")
        hostname = str(hrow["hostname"])
        port = int(hrow["port"] or 22)

        # Trust gate (probe + real) before issuing confirmation token.
        fp = get_fingerprint(hostname, port)
        trusted, mismatch = is_trusted(conn, hostname=hostname, port=port, fingerprint=fp.fingerprint)
        if not trusted:
            _audit(
                "known_hosts.missing",
                endpoint=f"/api/sftp/sessions/{session_id}/remove",
                payload={
                    "session_id": session_id,
                    "connection_id": str(srow["connection_id"]),
                    "host": hostname,
                    "port": port,
                    "fingerprint": fp.fingerprint,
                    "algo": fp.algo,
                    "capability_id": cap.id,
                    "risk_tier": cap.risk_tier.value,
                },
                result={"ok": False, "error_code": mismatch or "NEEDS_TRUST"},
            )
            raise HTTPException(
                status_code=409,
                detail=gate_detail(
                    error_code=mismatch or "NEEDS_TRUST",
                    gate="trust",
                    message="Host key not trusted. Add it to Known Hosts to proceed.",
                    context={"host": hostname, "port": port, "fingerprint": fp.fingerprint, "algo": fp.algo},
                    capability_id=cap.id,
                    risk_tier=cap.risk_tier.value,
                ),
            )

        probe_only = bool(int(crow["probe_only"] or 0))
        is_real = not (probe_only or ssh_probe_only() or not ssh_real_enabled())
        _enforce_provider_policy(cap=cap, endpoint=f"/api/sftp/sessions/{session_id}/remove")
        provider = get_ssh_provider(allow_real=is_real)
        username = str(crow["username"] or "").strip() or None
        auth_ref = str(crow["auth_ref"] or "").strip() or None

        now = _now_iso()

        # High-risk operation: require an explicit confirmation token.
        if not payload.confirm or not (payload.confirm_token or "").strip():
            transfer_id = uuid4().hex
            conn.execute(
                """
                INSERT INTO sftp_transfers (transfer_id, sftp_session_id, direction, remote_path, bytes_total, bytes_done, status, started_at, finished_at, sha256)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transfer_id,
                    session_id,
                    "remove",
                    payload.path,
                    None,
                    0,
                    "CONFIRM_REQUIRED",
                    now,
                    None,
                    None,
                ),
            )
            conn.commit()
            _audit(
                "sftp.remove.confirm_required",
                endpoint=f"/api/sftp/sessions/{session_id}/remove",
                payload={
                    "session_id": session_id,
                    "transfer_id": transfer_id,
                    "remote_path": payload.path,
                    "capability_id": cap.id,
                    "risk_tier": cap.risk_tier.value,
                },
                result={"ok": False, "error_code": "CONFIRM_REQUIRED"},
            )
            raise HTTPException(
                status_code=409,
                detail=gate_detail(
                    error_code="CONFIRM_REQUIRED",
                    gate="confirm",
                    confirm_token=transfer_id,
                    message="High-risk operation. Re-submit with confirm=true, confirm_token, and optional reason to proceed.",
                    context={"transfer_id": transfer_id, "remote_path": payload.path, "session_id": session_id},
                    capability_id=cap.id,
                    risk_tier=cap.risk_tier.value,
                ),
            )

        token = (payload.confirm_token or "").strip()
        row = conn.execute(
            "SELECT transfer_id, status, remote_path FROM sftp_transfers WHERE transfer_id = ? AND sftp_session_id = ?",
            (token, session_id),
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
                    context={"transfer_id": token, "remote_path": payload.path, "session_id": session_id},
                    capability_id="sftp.transfer",
                    risk_tier="HIGH",
                ),
            )
        if str(row["remote_path"]) != payload.path:
            raise HTTPException(
                status_code=409,
                detail=gate_detail(
                    error_code="INVALID_CONFIRM_TOKEN",
                    gate="confirm",
                    message="path mismatch",
                    context={"transfer_id": token, "remote_path": payload.path, "session_id": session_id},
                    capability_id="sftp.transfer",
                    risk_tier="HIGH",
                ),
            )

        err_code: Optional[str] = None
        try:
            t = provider.sftp_remove(
                hostname=hostname,
                port=port,
                username=username,
                auth_ref=auth_ref,
                remote_path=payload.path,
                timeout_ms=timeout_ms,
            )
            err_code = t.error_code
            conn.execute(
                "UPDATE sftp_transfers SET status = ?, finished_at = ?, bytes_done = ? WHERE transfer_id = ?",
                ("COMPLETED" if not err_code else "FAILED", _now_iso(), 0, token),
            )
            conn.commit()
        except Exception:
            conn.execute(
                "UPDATE sftp_transfers SET status = ?, finished_at = ?, bytes_done = ? WHERE transfer_id = ?",
                ("FAILED", _now_iso(), 0, token),
            )
            conn.commit()
            raise
    finally:
        conn.close()
    _audit(
        "sftp.remove",
        endpoint=f"/api/sftp/sessions/{session_id}/remove",
        payload={
            "session_id": session_id,
            "transfer_id": token,
            "remote_path": payload.path,
            "reason": payload.reason,
            "capability_id": cap.id,
            "risk_tier": cap.risk_tier.value,
        },
        result={"ok": True, "transfer_id": token, "error_code": err_code},
    )
    return {"ok": True, "session_id": session_id, "transfer_id": token, "remote_path": payload.path, "error_code": err_code}


@router.get("/api/sftp/transfers")
def sftp_transfers(
    session_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        where = ""
        params: list[Any] = []
        if session_id:
            where = " WHERE sftp_session_id = ?"
            params.append(session_id)
        total = conn.execute(f"SELECT COUNT(*) FROM sftp_transfers{where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM sftp_transfers{where} ORDER BY started_at DESC LIMIT ? OFFSET ?",
            params + [int(limit), int(offset)],
        ).fetchall()
        items = []
        for r in rows:
            items.append({k: r[k] for k in r.keys()})
        return {"total": int(total), "items": items, "limit": int(limit), "offset": int(offset)}
    finally:
        conn.close()
