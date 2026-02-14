"""SSH Connections API (BridgeOS).

Phase 2 MVP:
- status machine + detach/attach + exec
- events(seq) for refresh recovery
- probe-only mode for CI stability, with optional real SSH exec behind env flag
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from octopusos.webui.api.compat_state import ensure_schema as ensure_compat_schema
from octopusos.webui.api.shell import _audit_db_connect  # reuse audit DB connector
from octopusos.webui.api._db_bridgeos import (
    connect_bridgeos,
    ensure_bridgeos_schema,
    insert_ssh_connection_event,
)
from octopusos.webui.api._ssh_config import (
    ssh_default_timeout_ms,
    ssh_probe_only,
    ssh_real_allow_operators,
    ssh_real_command_allowlist,
    ssh_real_enabled,
)
from octopusos.webui.api._ssh_trust import get_fingerprint, is_trusted
from octopusos.core.providers.ssh_provider_registry import resolve_ssh_provider
from octopusos.execution import get_capability
from octopusos.execution.gate import policy_gate, trust_gate
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


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _command_preview(command: str) -> str:
    s = (command or "").strip().replace("\n", " ")
    # keep it short to reduce leakage risk in audit/logs
    return s[:32]


def _contains_restricted_operators(command: str) -> bool:
    s = command or ""
    restricted = ["&&", "||", ";", "|", "`", "$("]
    return any(tok in s for tok in restricted)


class ConnectionOpenRequest(BaseModel):
    host_id: str = Field(..., min_length=1, max_length=128)
    username: Optional[str] = Field(default=None, max_length=128)
    auth_ref: Optional[str] = Field(default=None, max_length=2000)
    mode: str = Field(default="ssh", max_length=32)
    label: Optional[str] = Field(default=None, max_length=200)
    probe_only: bool = Field(default=True)


class ConnectionOut(BaseModel):
    connection_id: str
    host_id: str
    status: str
    label: Optional[str]
    mode: str
    username: Optional[str] = None
    auth_ref: Optional[str]
    probe_only: bool
    created_at: str
    updated_at: str
    last_seen_at: Optional[str] = None
    detached_at: Optional[str] = None
    last_activity_at: Optional[str] = None
    detach_grace_ms: Optional[int] = None
    hard_ttl_ms: Optional[int] = None
    error_code: Optional[str] = None
    error: Optional[str] = None
    deprecation_warning: Optional[str] = None


class ConnectionExecRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=5000)
    timeout_ms: Optional[int] = Field(default=None, ge=100, le=600_000)


class ConnectionExecResponse(BaseModel):
    ok: bool
    connection_id: str
    job_id: str
    error_code: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None


class ConnectionEvent(BaseModel):
    connection_id: str
    seq: int
    ts: str
    type: str
    data: Dict[str, Any]


class EventsResponse(BaseModel):
    ok: bool
    connection_id: str
    items: List[ConnectionEvent]
    next_seq: int


def _get_connection_row(conn: sqlite3.Connection, connection_id: str) -> sqlite3.Row:
    ensure_bridgeos_schema(conn)
    row = conn.execute(
        "SELECT * FROM ssh_connections WHERE connection_id = ?",
        (connection_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="connection not found")
    return row


def _row_to_connection(row: sqlite3.Row) -> ConnectionOut:
    return ConnectionOut(
        connection_id=str(row["connection_id"]),
        host_id=str(row["host_id"]),
        status=str(row["status"]),
        label=row["label"],
        mode=str(row["mode"] or "ssh"),
        username=row["username"] if "username" in row.keys() else None,
        auth_ref=row["auth_ref"],
        probe_only=bool(int(row["probe_only"] or 0)),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        last_seen_at=row["last_seen_at"],
        detached_at=row["detached_at"],
        last_activity_at=row["last_activity_at"] if "last_activity_at" in row.keys() else None,
        detach_grace_ms=int(row["detach_grace_ms"]) if "detach_grace_ms" in row.keys() and row["detach_grace_ms"] is not None else None,
        hard_ttl_ms=int(row["hard_ttl_ms"]) if "hard_ttl_ms" in row.keys() and row["hard_ttl_ms"] is not None else None,
        error_code=row["error_code"],
        error=row["error"],
    )


def _parse_iso_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    s = str(ts).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _cleanup_expired_connections(conn: sqlite3.Connection) -> None:
    """Best-effort cleanup to prevent detached zombie accumulation."""
    ensure_bridgeos_schema(conn)
    now = datetime.now(timezone.utc)
    rows = conn.execute("SELECT * FROM ssh_connections WHERE status IN ('DETACHED','RUNNING')").fetchall()
    for r in rows:
        connection_id = str(r["connection_id"])
        created_at = _parse_iso_ts(r["created_at"])
        last_activity = _parse_iso_ts(r["last_activity_at"]) or created_at
        hard_ttl_ms = r["hard_ttl_ms"]
        detach_grace_ms = r["detach_grace_ms"]
        detached_at = _parse_iso_ts(r["detached_at"])

        # Hard TTL: close regardless of status.
        if hard_ttl_ms is not None and last_activity is not None:
            age_ms = int((now - last_activity).total_seconds() * 1000)
            if age_ms > int(hard_ttl_ms):
                conn.execute(
                    "UPDATE ssh_connections SET status = ?, updated_at = ?, error_code = ?, error = ? WHERE connection_id = ?",
                    ("CLOSED", _now_iso(), "EXPIRED", "hard ttl expired", connection_id),
                )
                conn.commit()
                insert_ssh_connection_event(
                    conn,
                    connection_id=connection_id,
                    event_type="status",
                    data_json=json.dumps({"status": "CLOSED", "message": "expired"}, ensure_ascii=False),
                )
                _audit(
                    "ssh.connection.expired",
                    endpoint="/api/connections",
                    payload={"connection_id": connection_id, "reason": "hard_ttl", "capability_id": "ssh.exec", "risk_tier": "LOW"},
                    result={"ok": True},
                )
                continue

        # Detach grace: close if detached too long.
        if str(r["status"]) == "DETACHED" and detach_grace_ms is not None and detached_at is not None:
            detached_ms = int((now - detached_at).total_seconds() * 1000)
            if detached_ms > int(detach_grace_ms):
                conn.execute(
                    "UPDATE ssh_connections SET status = ?, updated_at = ?, error_code = ?, error = ? WHERE connection_id = ?",
                    ("CLOSED", _now_iso(), "EXPIRED", "detach grace expired", connection_id),
                )
                conn.commit()
                insert_ssh_connection_event(
                    conn,
                    connection_id=connection_id,
                    event_type="status",
                    data_json=json.dumps({"status": "CLOSED", "message": "expired"}, ensure_ascii=False),
                )
                _audit(
                    "ssh.connection.expired",
                    endpoint="/api/connections",
                    payload={"connection_id": connection_id, "reason": "detach_grace", "capability_id": "ssh.exec", "risk_tier": "LOW"},
                    result={"ok": True},
                )


@router.get("/api/connections", response_model=List[ConnectionOut])
def connections_list() -> List[ConnectionOut]:
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        _cleanup_expired_connections(conn)
        rows = conn.execute(
            "SELECT * FROM ssh_connections ORDER BY updated_at DESC"
        ).fetchall()
        return [_row_to_connection(r) for r in rows]
    finally:
        conn.close()


@router.post("/api/connections/open", response_model=ConnectionOut)
def connections_open(payload: ConnectionOpenRequest) -> ConnectionOut:
    connection_id = uuid4().hex
    now = _now_iso()
    status = "OPENING"
    deprecation_warning = None

    username = (payload.username or "").strip() or None
    auth_ref = (payload.auth_ref or "").strip() or None
    # Backward-compat: old clients stuffed username into auth_ref.
    if not username and auth_ref and not auth_ref.startswith("secret_ref://"):
        username = auth_ref
        auth_ref = None
        deprecation_warning = "DEPRECATED: auth_ref-as-username. Use username field and auth_ref as secret_ref."

    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        _cleanup_expired_connections(conn)
        host = conn.execute("SELECT host_id FROM hosts WHERE host_id = ?", (payload.host_id,)).fetchone()
        if not host:
            raise HTTPException(status_code=404, detail="host not found")
        conn.execute(
            """
            INSERT INTO ssh_connections (
              connection_id, host_id, status, label, mode, username, auth_ref, probe_only,
              created_at, updated_at, last_seen_at, last_activity_at, detach_grace_ms, hard_ttl_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                connection_id,
                payload.host_id,
                status,
                payload.label,
                payload.mode or "ssh",
                username,
                auth_ref,
                1 if payload.probe_only else 0,
                now,
                now,
                now,
                now,
                30 * 60 * 1000,  # 30m default detach grace
                24 * 60 * 60 * 1000,  # 24h hard ttl
            ),
        )
        conn.commit()
        insert_ssh_connection_event(
            conn,
            connection_id=connection_id,
            event_type="status",
            data_json=json.dumps({"status": "OPENING", "message": "opening"}, ensure_ascii=False),
        )

        # MVP: transition to RUNNING immediately (real SSH handshake is deferred to exec)
        conn.execute(
            "UPDATE ssh_connections SET status = ?, updated_at = ?, last_seen_at = ? WHERE connection_id = ?",
            ("RUNNING", _now_iso(), _now_iso(), connection_id),
        )
        conn.commit()
        insert_ssh_connection_event(
            conn,
            connection_id=connection_id,
            event_type="status",
            data_json=json.dumps({"status": "RUNNING", "message": "running"}, ensure_ascii=False),
        )

        row = _get_connection_row(conn, connection_id)
        out = _row_to_connection(row)
        if deprecation_warning:
            out.deprecation_warning = deprecation_warning
    finally:
        conn.close()

    _audit(
        "ssh.connection.open",
        endpoint="/api/connections/open",
        payload={"connection_id": connection_id, "host_id": payload.host_id, "capability_id": "ssh.exec", "risk_tier": "MEDIUM"},
        result={"ok": True, "status": out.status},
    )
    if deprecation_warning:
        _audit(
            "ssh.auth_ref_compat_used",
            endpoint="/api/connections/open",
            payload={"connection_id": connection_id, "host_id": payload.host_id, "capability_id": "ssh.exec", "risk_tier": "LOW"},
            result={"ok": True, "warning": deprecation_warning},
        )
    return out


@router.post("/api/connections/{connection_id}/detach")
def connections_detach(connection_id: str) -> Dict[str, Any]:
    conn = connect_bridgeos()
    try:
        row = _get_connection_row(conn, connection_id)
        if str(row["status"]) not in {"RUNNING", "DETACHED"}:
            raise HTTPException(status_code=409, detail=f"cannot detach from status={row['status']}")
        conn.execute(
            "UPDATE ssh_connections SET status = ?, detached_at = ?, updated_at = ? WHERE connection_id = ?",
            ("DETACHED", _now_iso(), _now_iso(), connection_id),
        )
        conn.commit()
        insert_ssh_connection_event(
            conn,
            connection_id=connection_id,
            event_type="status",
            data_json=json.dumps({"status": "DETACHED", "message": "detached"}, ensure_ascii=False),
        )
    finally:
        conn.close()

    _audit(
        "ssh.connection.detach",
        endpoint=f"/api/connections/{connection_id}/detach",
        payload={"connection_id": connection_id, "capability_id": "ssh.exec", "risk_tier": "MEDIUM"},
        result={"ok": True},
    )
    return {"ok": True, "connection_id": connection_id, "status": "DETACHED"}


@router.post("/api/connections/{connection_id}/attach")
def connections_attach(connection_id: str) -> Dict[str, Any]:
    resume_token = uuid4().hex
    conn = connect_bridgeos()
    try:
        row = _get_connection_row(conn, connection_id)
        if str(row["status"]) not in {"RUNNING", "DETACHED"}:
            raise HTTPException(status_code=409, detail=f"cannot attach from status={row['status']}")
        conn.execute(
            "UPDATE ssh_connections SET status = ?, last_seen_at = ?, updated_at = ? WHERE connection_id = ?",
            ("RUNNING", _now_iso(), _now_iso(), connection_id),
        )
        conn.commit()
        insert_ssh_connection_event(
            conn,
            connection_id=connection_id,
            event_type="status",
            data_json=json.dumps({"status": "RUNNING", "message": "attached"}, ensure_ascii=False),
        )
    finally:
        conn.close()

    _audit(
        "ssh.connection.attach",
        endpoint=f"/api/connections/{connection_id}/attach",
        payload={"connection_id": connection_id, "resume_token": resume_token, "capability_id": "ssh.exec", "risk_tier": "MEDIUM"},
        result={"ok": True},
    )
    return {"ok": True, "connection_id": connection_id, "status": "RUNNING", "resume_token": resume_token}


@router.post("/api/connections/{connection_id}/close")
def connections_close(connection_id: str) -> Dict[str, Any]:
    conn = connect_bridgeos()
    try:
        _get_connection_row(conn, connection_id)
        conn.execute(
            "UPDATE ssh_connections SET status = ?, updated_at = ? WHERE connection_id = ?",
            ("CLOSED", _now_iso(), connection_id),
        )
        conn.commit()
        insert_ssh_connection_event(
            conn,
            connection_id=connection_id,
            event_type="status",
            data_json=json.dumps({"status": "CLOSED", "message": "closed"}, ensure_ascii=False),
        )
    finally:
        conn.close()

    _audit(
        "ssh.connection.close",
        endpoint=f"/api/connections/{connection_id}/close",
        payload={"connection_id": connection_id, "capability_id": "ssh.exec", "risk_tier": "MEDIUM"},
        result={"ok": True},
    )
    return {"ok": True, "connection_id": connection_id, "status": "CLOSED"}


def _probe_exec(conn: sqlite3.Connection, *, connection_id: str, command: str, job_id: str) -> None:
    insert_ssh_connection_event(
        conn,
        connection_id=connection_id,
        event_type="status",
        data_json=json.dumps({"job_id": job_id, "message": "started", "command": command}, ensure_ascii=False),
    )
    insert_ssh_connection_event(
        conn,
        connection_id=connection_id,
        event_type="stdout",
        data_json=json.dumps({"job_id": job_id, "text": f"[probe] {command}\n"}, ensure_ascii=False),
    )
    insert_ssh_connection_event(
        conn,
        connection_id=connection_id,
        event_type="status",
        data_json=json.dumps({"job_id": job_id, "message": "exited", "exit_code": 0}, ensure_ascii=False),
    )


def _real_exec(
    *,
    hostname: str,
    port: int,
    username: Optional[str],
    command: str,
    timeout_ms: int,
) -> Dict[str, Any]:
    """Real SSH exec via system OpenSSH client.

    Auth is delegated to the system's ssh-agent / keys.
    We disable OpenSSH known_hosts enforcement because we enforce our own trust gate.
    """
    user_host = f"{username}@{hostname}" if username else hostname
    args = [
        "ssh",
        "-p",
        str(int(port)),
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={max(1, int(timeout_ms / 1000))}",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        user_host,
        command,
    ]
    cp = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=max(0.1, timeout_ms / 1000.0),
    )
    return {
        "exit_code": int(cp.returncode),
        "stdout": cp.stdout or "",
        "stderr": cp.stderr or "",
    }


@router.post("/api/connections/{connection_id}/exec", response_model=ConnectionExecResponse)
def connections_exec(connection_id: str, payload: ConnectionExecRequest) -> ConnectionExecResponse:
    command = payload.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="command required")
    job_id = uuid4().hex

    conn = connect_bridgeos()
    try:
        row = _get_connection_row(conn, connection_id)
        _cleanup_expired_connections(conn)
        if str(row["status"]) not in {"RUNNING", "DETACHED"}:
            raise HTTPException(status_code=409, detail=f"cannot exec in status={row['status']}")
        probe_only = bool(int(row["probe_only"] or 0))
        timeout_ms = int(payload.timeout_ms or ssh_default_timeout_ms())
        cap = get_capability("ssh.exec")

        # Trust gate (probe + real): require known_hosts entry for host:port fingerprint.
        host_row = conn.execute(
            "SELECT hostname, port FROM hosts WHERE host_id = ?",
            (str(row["host_id"]),),
        ).fetchone()
        if not host_row:
            raise HTTPException(status_code=404, detail="host not found")
        hostname = str(host_row["hostname"])
        port = int(host_row["port"] or 22)
        fp = get_fingerprint(hostname, port)
        trusted, mismatch_reason = is_trusted(conn, hostname=hostname, port=port, fingerprint=fp.fingerprint)
        if not trusted:
            code = mismatch_reason or "NEEDS_TRUST"
            insert_ssh_connection_event(
                conn,
                connection_id=connection_id,
                event_type="status",
                data_json=json.dumps(
                    {
                        "status": "NEEDS_TRUST",
                        "message": "host key not trusted",
                        "error_code": code,
                        "fingerprint": fp.fingerprint,
                        "algo": fp.algo,
                        "host": hostname,
                        "port": port,
                    },
                    ensure_ascii=False,
                ),
            )
            _audit(
                "known_hosts.missing",
                endpoint=f"/api/connections/{connection_id}/exec",
                payload={
                    "connection_id": connection_id,
                    "host_id": str(row["host_id"]),
                    "host": hostname,
                    "port": port,
                    "fingerprint": fp.fingerprint,
                    "algo": fp.algo,
                    "capability_id": cap.id,
                    "risk_tier": cap.risk_tier.value,
                },
                result={"ok": False, "error_code": code},
            )
            trust_gate(
                capability=cap,
                error_code=code,
                message="Host key not trusted. Add it to Known Hosts to proceed.",
                context={"host": hostname, "port": port, "fingerprint": fp.fingerprint, "algo": fp.algo},
            )

        # Update last activity early so TTL doesn't expire a hot session.
        conn.execute(
            "UPDATE ssh_connections SET last_activity_at = ?, last_seen_at = ?, updated_at = ? WHERE connection_id = ?",
            (_now_iso(), _now_iso(), _now_iso(), connection_id),
        )
        conn.commit()

        # Connection events meta for explainability.
        insert_ssh_connection_event(
            conn,
            connection_id=connection_id,
            event_type="exec.started",
            data_json=json.dumps(
                {
                    "job_id": job_id,
                    "command_sha256": _sha256_text(command),
                    "command_preview": _command_preview(command),
                    "timeout_ms": timeout_ms,
                },
                ensure_ascii=False,
            ),
        )

        _audit(
            "ssh.exec.requested",
            endpoint=f"/api/connections/{connection_id}/exec",
            payload={
                "connection_id": connection_id,
                "job_id": job_id,
                "command_sha256": _sha256_text(command),
                "command_preview": _command_preview(command),
                "capability_id": cap.id,
                "risk_tier": cap.risk_tier.value,
            },
            result={"ok": True},
        )

        # Default: probe-only. Real exec requires explicit OCTO_SSH_REAL=1 (and probe_only=false).
        is_real = not (probe_only or ssh_probe_only() or not ssh_real_enabled())
        if is_real:
            # Optional "safe mode" policy for real exec.
            if not ssh_real_allow_operators() and _contains_restricted_operators(command):
                insert_ssh_connection_event(
                    conn,
                    connection_id=connection_id,
                    event_type="exec.completed",
                    data_json=json.dumps(
                        {
                            "job_id": job_id,
                            "exit_code": 2,
                            "duration_ms": 0,
                            "error_code": "SSH_COMMAND_REJECTED",
                            "message": "restricted operators are not allowed in real mode",
                        },
                        ensure_ascii=False,
                    ),
                )
                _audit(
                    "ssh.exec.completed",
                    endpoint=f"/api/connections/{connection_id}/exec",
                    payload={
                        "connection_id": connection_id,
                        "job_id": job_id,
                        "command_sha256": _sha256_text(command),
                        "command_preview": _command_preview(command),
                        "capability_id": cap.id,
                        "risk_tier": cap.risk_tier.value,
                    },
                    result={"ok": False, "error_code": "SSH_COMMAND_REJECTED", "exit_code": 2, "duration_ms": 0},
                )
                policy_gate(
                    capability=cap,
                    error_code="SSH_COMMAND_REJECTED",
                    message="Restricted operators are not allowed in real mode. Set OCTO_SSH_REAL_ALLOW_OPERATORS=1 to override.",
                    context={"connection_id": connection_id},
                )

            allow = ssh_real_command_allowlist()
            if allow:
                head = command.strip().split()[0]
                if head not in allow:
                    insert_ssh_connection_event(
                        conn,
                        connection_id=connection_id,
                        event_type="exec.completed",
                        data_json=json.dumps(
                            {
                                "job_id": job_id,
                                "exit_code": 2,
                                "duration_ms": 0,
                                "error_code": "SSH_COMMAND_REJECTED",
                                "message": "command not in allowlist",
                                "command_head": head,
                            },
                            ensure_ascii=False,
                        ),
                    )
                    _audit(
                        "ssh.exec.completed",
                        endpoint=f"/api/connections/{connection_id}/exec",
                        payload={
                            "connection_id": connection_id,
                            "job_id": job_id,
                            "command_sha256": _sha256_text(command),
                            "command_preview": _command_preview(command),
                            "capability_id": cap.id,
                            "risk_tier": cap.risk_tier.value,
                        },
                        result={"ok": False, "error_code": "SSH_COMMAND_REJECTED", "exit_code": 2, "duration_ms": 0},
                    )
                    policy_gate(
                        capability=cap,
                        error_code="SSH_COMMAND_REJECTED",
                        message="Command is not in real-mode allowlist.",
                        context={"connection_id": connection_id, "command_head": head},
                    )

        selection = resolve_ssh_provider()
        if selection.provider == "mcp":
            policy_gate(
                capability=cap,
                error_code="PROVIDER_UNAVAILABLE",
                message="Selected SSH provider is MCP but it is not available in this build.",
                context={"provider": "mcp"},
            )
        if selection.provider == "system" and not bool(selection.allow_real):
            policy_gate(
                capability=cap,
                error_code="REAL_NOT_ALLOWED",
                message="Real SSH provider is disabled by policy (allow_real=false).",
                context={"provider": "system"},
            )

        provider = get_ssh_provider(allow_real=is_real)
        username = str(row["username"] or "").strip() or None
        auth_ref = str(row["auth_ref"] or "").strip() or None
        result = provider.exec(
            hostname=hostname,
            port=port,
            username=username,
            auth_ref=auth_ref,
            command=command,
            timeout_ms=timeout_ms,
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        if stdout:
            insert_ssh_connection_event(
                conn,
                connection_id=connection_id,
                event_type="stdout",
                data_json=json.dumps({"job_id": job_id, "text": stdout}, ensure_ascii=False),
            )
        if stderr:
            insert_ssh_connection_event(
                conn,
                connection_id=connection_id,
                event_type="stderr",
                data_json=json.dumps({"job_id": job_id, "text": stderr}, ensure_ascii=False),
            )
        insert_ssh_connection_event(
            conn,
            connection_id=connection_id,
            event_type="exit",
            data_json=json.dumps({"job_id": job_id, "exit_code": int(result.exit_code)}, ensure_ascii=False),
        )

        insert_ssh_connection_event(
            conn,
            connection_id=connection_id,
            event_type="exec.completed",
            data_json=json.dumps(
                {
                    "job_id": job_id,
                    "exit_code": int(result.exit_code),
                    "duration_ms": int(result.duration_ms),
                    "stdout_sha256": _sha256_text(stdout) if stdout else None,
                    "stderr_sha256": _sha256_text(stderr) if stderr else None,
                    "error_code": result.error_code,
                },
                ensure_ascii=False,
            ),
        )

        _audit(
            "ssh.exec.completed",
            endpoint=f"/api/connections/{connection_id}/exec",
            payload={
                "connection_id": connection_id,
                "job_id": job_id,
                "command_sha256": _sha256_text(command),
                "command_preview": _command_preview(command),
                "capability_id": cap.id,
                "risk_tier": cap.risk_tier.value,
            },
            result={
                "ok": True,
                "exit_code": int(result.exit_code),
                "duration_ms": int(result.duration_ms),
                "stdout_sha256": _sha256_text(stdout) if stdout else None,
                "stderr_sha256": _sha256_text(stderr) if stderr else None,
                "error_code": result.error_code,
            },
        )

        if is_real and result.error_code:
            conn.execute(
                "UPDATE ssh_connections SET status = ?, updated_at = ?, error_code = ?, error = ? WHERE connection_id = ?",
                ("FAILED", _now_iso(), str(result.error_code), (stderr or stdout)[:800], connection_id),
            )
            conn.commit()
            insert_ssh_connection_event(
                conn,
                connection_id=connection_id,
                event_type="status",
                data_json=json.dumps({"status": "FAILED", "message": "ssh exec failed", "error_code": result.error_code}, ensure_ascii=False),
            )

        return ConnectionExecResponse(
            ok=True,
            connection_id=connection_id,
            job_id=job_id,
            error_code=result.error_code,
            exit_code=int(result.exit_code),
            duration_ms=int(result.duration_ms),
        )
    finally:
        conn.close()


@router.get("/api/connections/{connection_id}/events", response_model=EventsResponse)
def connections_events(
    connection_id: str,
    from_seq: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
) -> EventsResponse:
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        _get_connection_row(conn, connection_id)
        rows = conn.execute(
            """
            SELECT connection_id, seq, ts, type, data_json
            FROM ssh_connection_events
            WHERE connection_id = ? AND seq >= ?
            ORDER BY seq ASC
            LIMIT ?
            """,
            (connection_id, int(from_seq), int(limit)),
        ).fetchall()
        items: List[ConnectionEvent] = []
        max_seq = 0
        for r in rows:
            max_seq = max(max_seq, int(r["seq"]))
            try:
                data = json.loads(r["data_json"])
            except Exception:
                data = {"raw": r["data_json"]}
            items.append(
                ConnectionEvent(
                    connection_id=str(r["connection_id"]),
                    seq=int(r["seq"]),
                    ts=str(r["ts"]),
                    type=str(r["type"]),
                    data=data,
                )
            )
        if max_seq == 0:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM ssh_connection_events WHERE connection_id = ?",
                (connection_id,),
            ).fetchone()
            max_seq = int(row["max_seq"] or 0)
        return EventsResponse(ok=True, connection_id=connection_id, items=items, next_seq=max_seq + 1)
    finally:
        conn.close()
