"""Unified logs query for bridge-managed shell/ssh/sftp surfaces."""

from __future__ import annotations

import json
import os
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from octopusos.webui.api.compat_state import ensure_schema as ensure_compat_schema
from octopusos.webui.api.shell import _audit_db_connect
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


def _safe_json_load(s: str) -> Dict[str, Any]:
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {"value": obj}
    except Exception:
        return {"raw": s}


def _logs_query_internal(
    *,
    want: set[str],
    q: Optional[str],
    host_id: Optional[str],
    connection_id: Optional[str],
    limit: int,
    offset: int,
) -> Dict[str, Any]:
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        items: List[Dict[str, Any]] = []

        if "shell" in want:
            rows = conn.execute(
                """
                SELECT session_id AS ref_id, ts, type, data_json
                FROM terminal_events
                ORDER BY ts DESC, seq DESC
                LIMIT 500
                """
            ).fetchall()
            for r in rows:
                data = _safe_json_load(str(r["data_json"]))
                summary = ""
                if str(r["type"]) == "status" and isinstance(data.get("message"), str):
                    summary = str(data.get("message"))
                    if isinstance(data.get("command"), str):
                        summary += f": {data.get('command')}"
                elif isinstance(data.get("text"), str):
                    summary = data.get("text")[:200]
                items.append(
                    {
                        "ts": str(r["ts"]),
                        "type": f"shell.{r['type']}",
                        "capability_id": "local.shell",
                        "risk_tier": "LOW",
                        "ref_id": str(r["ref_id"]),
                        "host_id": None,
                        "connection_id": None,
                        "summary": summary or f"shell {r['type']}",
                        "severity": "info" if str(r["type"]) != "stderr" else "warning",
                        "raw": {"ref_id": str(r["ref_id"]), "type": str(r["type"]), "data": data},
                    }
                )

        if "ssh" in want:
            sql = """
                SELECT e.connection_id AS ref_id, e.ts, e.type, e.data_json, c.host_id
                FROM ssh_connection_events e
                JOIN ssh_connections c ON c.connection_id = e.connection_id
            """
            where: List[str] = []
            params: List[Any] = []
            if host_id:
                where.append("c.host_id = ?")
                params.append(host_id)
            if connection_id:
                where.append("c.connection_id = ?")
                params.append(connection_id)
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY e.ts DESC, e.seq DESC LIMIT 500"
            rows = conn.execute(sql, params).fetchall()
            for r in rows:
                data = _safe_json_load(str(r["data_json"]))
                summary = ""
                if str(r["type"]) == "status" and isinstance(data.get("message"), str):
                    summary = str(data.get("message"))
                elif str(r["type"]) == "exec.started" and isinstance(data.get("command_preview"), str):
                    summary = f"exec started: {data.get('command_preview')}"
                elif str(r["type"]) == "exec.completed" and isinstance(data.get("exit_code"), int):
                    summary = f"exec completed: exit={data.get('exit_code')}"
                elif isinstance(data.get("text"), str):
                    summary = data.get("text")[:200]
                items.append(
                    {
                        "ts": str(r["ts"]),
                        "type": f"ssh.{r['type']}",
                        "capability_id": "ssh.exec",
                        "risk_tier": "MEDIUM",
                        "ref_id": str(r["ref_id"]),
                        "host_id": str(r["host_id"]),
                        "connection_id": str(r["ref_id"]),
                        "summary": summary or f"ssh {r['type']}",
                        "severity": "info" if str(r["type"]) != "stderr" else "warning",
                        "raw": {"connection_id": str(r["ref_id"]), "host_id": str(r["host_id"]), "type": str(r["type"]), "data": data},
                    }
                )

        if "sftp" in want:
            rows = conn.execute(
                """
                SELECT transfer_id AS ref_id, sftp_session_id, started_at AS ts, direction, remote_path, bytes_total, bytes_done, status
                FROM sftp_transfers
                ORDER BY started_at DESC
                LIMIT 500
                """
            ).fetchall()
            for r in rows:
                items.append(
                    {
                        "ts": str(r["ts"]),
                        "type": f"sftp.{r['direction']}",
                        "capability_id": "sftp.transfer",
                        "risk_tier": "MEDIUM",
                        "ref_id": str(r["ref_id"]),
                        "host_id": None,
                        "connection_id": None,
                        "summary": f"{r['direction']} {r['remote_path']} ({r['status']})",
                        "severity": "info",
                        "raw": {k: r[k] for k in r.keys()},
                    }
                )

        if q:
            qn = q.strip().lower()
            if qn:
                items = [it for it in items if qn in str(it.get("summary") or "").lower()]

        items.sort(key=lambda it: str(it.get("ts") or ""), reverse=True)
        total = len(items)
        sliced = items[int(offset): int(offset) + int(limit)]
        return {"total": total, "items": sliced, "limit": int(limit), "offset": int(offset)}
    finally:
        conn.close()


@router.get("/api/logs")
def logs_query(
    types: str = Query(default="shell,ssh,sftp"),
    q: Optional[str] = Query(default=None),
    host_id: Optional[str] = Query(default=None),
    connection_id: Optional[str] = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    want = {x.strip().lower() for x in (types or "").split(",") if x.strip()}
    if not want:
        want = {"shell", "ssh", "sftp"}

    _audit(
        "logs.query",
        endpoint="/api/logs",
        payload={"types": sorted(want), "q": q, "host_id": host_id, "connection_id": connection_id, "capability_id": "logs.query", "risk_tier": "LOW"},
        result={"ok": True},
    )
    return _logs_query_internal(want=want, q=q, host_id=host_id, connection_id=connection_id, limit=limit, offset=offset)


@router.get("/api/logs/export")
def logs_export(
    types: str = Query(default="shell,ssh,sftp"),
    q: Optional[str] = Query(default=None),
    host_id: Optional[str] = Query(default=None),
    connection_id: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    want = {x.strip().lower() for x in (types or "").split(",") if x.strip()}
    if not want:
        want = {"shell", "ssh", "sftp"}

    payload = _logs_query_internal(want=want, q=q, host_id=host_id, connection_id=connection_id, limit=500, offset=0)
    generated_at = _now_iso()
    blob = json.dumps(
        {
            "generated_at": generated_at,
            "filters": {"types": sorted(want), "q": q, "host_id": host_id, "connection_id": connection_id},
            "data": payload,
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    sha = hashlib.sha256(blob).hexdigest()
    export_id = sha[:16]
    out_dir = Path(os.getcwd()) / "output" / "logs_exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{export_id}.json"
    out_path.write_bytes(blob)

    _audit(
        "logs.export",
        endpoint="/api/logs/export",
        payload={"types": sorted(want), "q": q, "host_id": host_id, "connection_id": connection_id, "capability_id": "logs.query", "risk_tier": "LOW"},
        result={"ok": True, "sha256": sha, "export_id": export_id},
    )
    return {"ok": True, "export_id": export_id, "sha256": sha, "generated_at": generated_at, "download_url": f"/api/logs/exports/{export_id}"}


@router.get("/api/logs/exports/{export_id}")
def logs_export_download(export_id: str):
    out_path = Path(os.getcwd()) / "output" / "logs_exports" / f"{export_id}.json"
    if not out_path.exists():
        raise HTTPException(status_code=404, detail="export not found")
    return StreamingResponse(out_path.open("rb"), media_type="application/json")
