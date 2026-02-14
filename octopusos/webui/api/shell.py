"""Local shell (non-SSH) session API.

MVP goals:
- session_id stable across refresh (UI stores it)
- command execution continues server-side if UI disconnects
- output written as (events + seq) and can be re-fetched via from_seq polling
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from octopusos.core.storage.paths import ensure_db_exists
from octopusos.webui.api import compat_state
from octopusos.webui.api._db_bridgeos import connect_bridgeos, ensure_bridgeos_schema, insert_terminal_event


router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _audit_db_connect() -> sqlite3.Connection:
    """Connect to OctopusOS audit DB (compat_audit_events).

    Honors OCTOPUSOS_DB_PATH for tests, otherwise uses canonical ~/.octopusos/store/octopusos/db.sqlite.
    """
    env_path = (os.getenv("OCTOPUSOS_DB_PATH") or "").strip()
    if env_path:
        p = Path(env_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(p))
    else:
        p = ensure_db_exists("octopusos")
        conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    return conn


def _audit(event_type: str, *, endpoint: str, payload: Any, result: Any) -> None:
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _audit_db_connect()
        compat_state.ensure_schema(conn)
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


class CreateSessionResponse(BaseModel):
    session_id: str


class ExecRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=5000)


class ExecResponse(BaseModel):
    ok: bool
    job_id: str


class TerminalEvent(BaseModel):
    session_id: str
    seq: int
    ts: str
    type: str
    data: Dict[str, Any]


class EventsResponse(BaseModel):
    ok: bool
    session_id: str
    items: List[TerminalEvent]
    next_seq: int


@dataclass
class _SessionRow:
    session_id: str
    cwd: str
    status: str


def _get_session(conn: sqlite3.Connection, session_id: str) -> _SessionRow:
    ensure_bridgeos_schema(conn)
    row = conn.execute(
        "SELECT session_id, cwd, status FROM terminal_sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="session not found")
    return _SessionRow(
        session_id=str(row["session_id"]),
        cwd=str(row["cwd"] or os.getcwd()),
        status=str(row["status"] or "OPEN"),
    )


def _read_stream_thread(session_id: str, job_id: str, stream, event_type: str) -> None:
    conn = connect_bridgeos()
    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            insert_terminal_event(
                conn,
                session_id=session_id,
                event_type=event_type,
                data_json=json.dumps({"job_id": job_id, "text": line}, ensure_ascii=False),
            )
    finally:
        try:
            stream.close()
        except Exception:
            pass
        conn.close()


def _run_job_sync(session_id: str, cwd: str, command: str, job_id: str) -> None:
    conn = connect_bridgeos()
    try:
        insert_terminal_event(
            conn,
            session_id=session_id,
            event_type="status",
            data_json=json.dumps(
                {"job_id": job_id, "message": "started", "command": command},
                ensure_ascii=False,
            ),
        )
    finally:
        conn.close()

    proc = subprocess.Popen(
        ["bash", "-lc", command],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    assert proc.stdout is not None
    assert proc.stderr is not None

    t_out = threading.Thread(
        target=_read_stream_thread, args=(session_id, job_id, proc.stdout, "stdout"), daemon=True
    )
    t_err = threading.Thread(
        target=_read_stream_thread, args=(session_id, job_id, proc.stderr, "stderr"), daemon=True
    )
    t_out.start()
    t_err.start()

    exit_code = proc.wait()
    t_out.join(timeout=5)
    t_err.join(timeout=5)

    conn2 = connect_bridgeos()
    try:
        insert_terminal_event(
            conn2,
            session_id=session_id,
            event_type="status",
            data_json=json.dumps(
                {"job_id": job_id, "message": "exited", "exit_code": int(exit_code)},
                ensure_ascii=False,
            ),
        )
    finally:
        conn2.close()


@router.post("/api/shell/sessions", response_model=CreateSessionResponse)
async def shell_session_create() -> CreateSessionResponse:
    session_id = uuid4().hex
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        now = _now_iso()
        conn.execute(
            """
            INSERT INTO terminal_sessions (session_id, status, cwd, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, "OPEN", os.getcwd(), now, now),
        )
        conn.commit()
    finally:
        conn.close()

    _audit(
        "shell.session.create",
        endpoint="/api/shell/sessions",
        payload={"session_id": session_id, "capability_id": "local.shell"},
        result={"ok": True},
    )
    return CreateSessionResponse(session_id=session_id)


@router.post("/api/shell/sessions/{session_id}/exec", response_model=ExecResponse)
async def shell_session_exec(session_id: str, req: ExecRequest) -> ExecResponse:
    command = req.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="command required")

    conn = connect_bridgeos()
    try:
        s = _get_session(conn, session_id)
        if s.status != "OPEN":
            raise HTTPException(status_code=409, detail=f"session not open: {s.status}")
    finally:
        conn.close()

    job_id = uuid4().hex

    _audit(
        "shell.input",
        endpoint=f"/api/shell/sessions/{session_id}/exec",
        payload={"session_id": session_id, "job_id": job_id, "command": command, "capability_id": "local.shell"},
        result={"ok": True},
    )

    # Fire-and-forget: job keeps running even if client disconnects.
    threading.Thread(
        target=_run_job_sync,
        args=(session_id, s.cwd, command, job_id),
        daemon=True,
    ).start()
    return ExecResponse(ok=True, job_id=job_id)


@router.get("/api/shell/sessions/{session_id}/events", response_model=EventsResponse)
async def shell_session_events(session_id: str, from_seq: int = 0, limit: int = 500) -> EventsResponse:
    if from_seq < 0:
        from_seq = 0
    limit = max(1, min(int(limit or 500), 2000))

    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        _get_session(conn, session_id)
        rows = conn.execute(
            """
            SELECT session_id, seq, ts, type, data_json
            FROM terminal_events
            WHERE session_id = ? AND seq >= ?
            ORDER BY seq ASC
            LIMIT ?
            """,
            (session_id, int(from_seq), int(limit)),
        ).fetchall()
        items: List[TerminalEvent] = []
        max_seq = 0
        for r in rows:
            max_seq = max(max_seq, int(r["seq"]))
            try:
                data = json.loads(r["data_json"])
            except Exception:
                data = {"raw": r["data_json"]}
            items.append(
                TerminalEvent(
                    session_id=str(r["session_id"]),
                    seq=int(r["seq"]),
                    ts=str(r["ts"]),
                    type=str(r["type"]),
                    data=data,
                )
            )
        if max_seq == 0:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM terminal_events WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            max_seq = int(row["max_seq"] or 0)
        next_seq = max_seq + 1
        return EventsResponse(ok=True, session_id=session_id, items=items, next_seq=next_seq)
    finally:
        conn.close()


@router.post("/api/shell/sessions/{session_id}/close")
async def shell_session_close(session_id: str) -> Dict[str, Any]:
    conn = connect_bridgeos()
    try:
        ensure_bridgeos_schema(conn)
        _get_session(conn, session_id)
        conn.execute(
            "UPDATE terminal_sessions SET status = ?, updated_at = ? WHERE session_id = ?",
            ("CLOSED", _now_iso(), session_id),
        )
        conn.commit()
    finally:
        conn.close()

    _audit(
        "shell.session.close",
        endpoint=f"/api/shell/sessions/{session_id}/close",
        payload={"session_id": session_id, "capability_id": "local.shell"},
        result={"ok": True},
    )
    return {"ok": True, "session_id": session_id}
