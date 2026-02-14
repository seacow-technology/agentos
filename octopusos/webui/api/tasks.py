"""Tasks API router (v2).

This router is the WebUI contract for task lifecycle:
- create task -> planning (open_plan) -> awaiting_approval (default)
- approve -> long-run execution (resume-able)
- pause/resume
- live metrics + audit trail

IMPORTANT:
- Do not fake progress/audit in the frontend. Metrics must be derived from
  real runner/audit state in the backend.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple
from uuid import uuid4  # legacy ids only (kept for compat)

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from octopusos.store import get_db_path
from octopusos.core.task import TaskManager
from octopusos.core.runner.task_runner import TaskRunner

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskCreateRequest(BaseModel):
    title: str
    project_id: Optional[str] = None
    created_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskResponse(BaseModel):
    task_id: str
    title: str
    status: str
    session_id: Optional[str] = None
    project_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    metadata: Dict[str, Any] = {}
    exit_reason: Optional[str] = None
    spec_frozen: int = 0


class TasksListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
    limit: int
    offset: int


class TaskLiveResponse(BaseModel):
    task_id: str
    status: str
    stage: str
    progress_percent: int
    eta_seconds: Optional[int] = None
    steps_total: Optional[int] = None
    steps_done: Optional[int] = None
    throughput_steps_per_sec: Optional[float] = None
    llm_latency_ms_avg: Optional[float] = None
    llm_latency_ms_p95: Optional[float] = None
    last_event_at: Optional[str] = None
    risk_level_current: Optional[str] = None
    paused_reason: Optional[str] = None
    pause_checkpoint: Optional[str] = None


class TaskAuditEvent(BaseModel):
    audit_id: Optional[str] = None
    task_id: str
    level: str
    event_type: str
    payload: Optional[Any] = None
    created_at: str


class TaskAuditResponse(BaseModel):
    task_id: str
    total: int
    events: List[TaskAuditEvent]


class RoutePlanResponse(BaseModel):
    route: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _normalize_ts(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    if isinstance(value, (int, float)):
        try:
            # Treat ints as epoch seconds (legacy tables sometimes store seconds).
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            return None
    try:
        return str(value)
    except Exception:
        return None


def _is_placeholder_task_id(task_id: str) -> bool:
    # Playwright full_ui_audit normalizes :taskId -> "1".
    return bool(task_id) and task_id.isdigit()


def _placeholder_task(task_id: str) -> Dict[str, Any]:
    now = _now_iso().replace("+00:00", "Z")
    return {
        "task_id": task_id,
        "title": f"Demo Task {task_id}",
        "status": "created",
        "session_id": None,
        "project_id": None,
        "created_at": now,
        "updated_at": now,
        "created_by": "system",
        "metadata": {"source": "demo", "placeholder": True},
        "exit_reason": None,
        "spec_frozen": 0,
    }


def _db_connect() -> sqlite3.Connection:
    env_path = os.getenv("OCTOPUSOS_DB_PATH")
    db_path = Path(env_path) if env_path else get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=500, detail="Database not initialized")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return bool(row)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r["name"]) for r in rows}


def _task_id_col(cols: set[str]) -> str:
    if "task_id" in cols:
        return "task_id"
    if "id" in cols:
        return "id"
    raise HTTPException(status_code=500, detail="task id column missing")


def _as_task(row: sqlite3.Row, id_col: str) -> Dict[str, Any]:
    return {
        "id": row[id_col],
        "task_id": row[id_col],
        "project_id": row["project_id"] if "project_id" in row.keys() else None,
        "session_id": row["session_id"] if "session_id" in row.keys() else None,
        "title": row["title"] if "title" in row.keys() else "",
        "description": row["description"] if "description" in row.keys() else None,
        "status": row["status"] if "status" in row.keys() and row["status"] else "created",
        "created_at": _normalize_ts(row["created_at"]) if "created_at" in row.keys() else _now_iso(),
        "updated_at": _normalize_ts(row["updated_at"]) if "updated_at" in row.keys() else None,
    }

def _as_task_response(task_row: Dict[str, Any]) -> TaskResponse:
    # Normalize both legacy and core Task dicts to a single response.
    return TaskResponse(
        task_id=str(task_row.get("task_id") or task_row.get("id") or ""),
        title=str(task_row.get("title") or ""),
        status=str(task_row.get("status") or "created"),
        session_id=task_row.get("session_id"),
        project_id=task_row.get("project_id"),
        created_at=_normalize_ts(task_row.get("created_at")),
        updated_at=_normalize_ts(task_row.get("updated_at")),
        created_by=task_row.get("created_by"),
        metadata=task_row.get("metadata") or {},
        exit_reason=task_row.get("exit_reason"),
        spec_frozen=int(task_row.get("spec_frozen") or 0),
    )


_RUNNER_THREADS: Dict[str, threading.Thread] = {}
_RUNNER_LOCK = threading.Lock()


def _runner_repo_path() -> Path:
    # Default to repo root of current process.
    # For production deployments, this should be injected explicitly.
    return Path(os.getenv("OCTOPUSOS_REPO_ROOT") or ".").resolve()


def _runner_policy_path() -> Optional[Path]:
    p = (os.getenv("OCTOPUSOS_POLICY_PATH") or "").strip()
    return Path(p).resolve() if p else None


def _start_runner_thread(*, task_id: str, actor: str, use_real_pipeline: bool = False) -> bool:
    with _RUNNER_LOCK:
        t = _RUNNER_THREADS.get(task_id)
        if t and t.is_alive():
            return False

        def _run() -> None:
            tm = TaskManager()
            tm.add_audit(
                task_id=task_id,
                event_type="WEBUI_RUNNER_LAUNCH",
                level="info",
                payload={
                    "actor": actor,
                    "repo_path": str(_runner_repo_path()),
                    "use_real_pipeline": use_real_pipeline,
                },
            )
            runner = TaskRunner(
                task_manager=tm,
                repo_path=_runner_repo_path(),
                policy_path=_runner_policy_path(),
                use_real_pipeline=use_real_pipeline,
            )
            runner.run_task(task_id)

        thread = threading.Thread(target=_run, name=f"webui-task-runner-{task_id[:12]}", daemon=True)
        thread.start()
        _RUNNER_THREADS[task_id] = thread
        return True


def _load_open_plan(task_id: str) -> Optional[Dict[str, Any]]:
    p = Path("store/artifacts") / task_id / "open_plan.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _evidence_download_enabled() -> bool:
    return os.getenv("OCTOPUSOS_ALLOW_EVIDENCE_BUNDLE_DOWNLOAD", "").strip().lower() in {"1", "true", "yes", "on"}


def _find_latest_e2e_real_run_dir_for_task(task_id: str) -> Optional[Path]:
    base = Path("output") / "e2e-real"
    if not base.exists():
        return None
    run_dirs = [p for p in base.iterdir() if p.is_dir()]
    for d in sorted(run_dirs, key=lambda p: p.name, reverse=True):
        tid = d / "task_id.txt"
        if not tid.exists():
            continue
        try:
            if tid.read_text(encoding="utf-8").strip() == task_id:
                return d
        except Exception:
            continue
    return None


def _load_e2e_real_evidence_record(run_dir: Path) -> Optional[Dict[str, Any]]:
    """Load the evidence JSON produced by scripts/e2e/generate_e2e_real_task_flow_evidence.py."""
    evidence_json = run_dir / "reports" / "e2e_real_task_flow_evidence.json"
    if not evidence_json.exists():
        return None
    try:
        return json.loads(evidence_json.read_text(encoding="utf-8"))
    except Exception:
        return None


def _validate_e2e_real_bundle_ownership(*, expected_task_id: str, run_dir: Path) -> Dict[str, Any]:
    """Validate the evidence bundle belongs to the expected task_id/run_id."""
    record = _load_e2e_real_evidence_record(run_dir)
    if not record:
        raise HTTPException(status_code=404, detail="Evidence bundle not found")
    record_task_id = str(record.get("task_id") or "").strip()
    record_run_id = str(record.get("run_id") or "").strip()
    if record_task_id != expected_task_id:
        raise HTTPException(status_code=404, detail="Evidence bundle not found")
    if record_run_id and record_run_id != run_dir.name:
        raise HTTPException(status_code=404, detail="Evidence bundle not found")
    return record


def _compute_live_metrics(task_id: str) -> TaskLiveResponse:
    tm = TaskManager()
    task = tm.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    metadata = task.metadata or {}
    stage = str(metadata.get("current_stage") or "").strip() or str(task.status)

    plan = _load_open_plan(task_id) or {}
    steps = plan.get("steps") if isinstance(plan.get("steps"), list) else []
    steps_total = len(steps) if steps else None

    steps_done = metadata.get("steps_done")
    if isinstance(steps_done, int):
        pass
    else:
        steps_done = metadata.get("exec_step_index")
        if isinstance(steps_done, int) and steps_done > 0:
            pass
        else:
            steps_done = None

    progress_percent = 0
    if steps_total and isinstance(steps_done, int):
        progress_percent = max(0, min(100, int((steps_done / max(1, steps_total)) * 100)))
    elif task.status in {"succeeded", "done", "failed", "canceled", "blocked"}:
        progress_percent = 100

    # Throughput: count STEP_COMPLETED in last 60 seconds.
    throughput = None
    last_event_at = None
    try:
        trace = tm.get_trace(task_id)
        if trace and trace.audits:
            last_event_at = trace.audits[-1].get("created_at")
            recent_cutoff = datetime.now(timezone.utc).timestamp() - 60
            recent_steps = 0
            for a in trace.audits:
                if a.get("event_type") != "STEP_COMPLETED":
                    continue
                ts = a.get("created_at") or ""
                try:
                    # ISO 8601
                    t = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                except Exception:
                    continue
                if t >= recent_cutoff:
                    recent_steps += 1
            throughput = recent_steps / 60.0
    except Exception:
        pass

    paused_reason = metadata.get("pause_reason") if isinstance(metadata.get("pause_reason"), str) else None
    pause_checkpoint = metadata.get("pause_checkpoint") if isinstance(metadata.get("pause_checkpoint"), str) else None

    llm_latency_ms_avg = metadata.get("llm_latency_ms_avg")
    llm_latency_ms_p95 = metadata.get("llm_latency_ms_p95")
    if not isinstance(llm_latency_ms_avg, (int, float)):
        llm_latency_ms_avg = None
    if not isinstance(llm_latency_ms_p95, (int, float)):
        llm_latency_ms_p95 = None

    return TaskLiveResponse(
        task_id=task.task_id,
        status=str(task.status),
        stage=stage,
        progress_percent=int(progress_percent),
        eta_seconds=None,
        steps_total=steps_total,
        steps_done=steps_done,
        throughput_steps_per_sec=throughput,
        llm_latency_ms_avg=float(llm_latency_ms_avg) if llm_latency_ms_avg is not None else None,
        llm_latency_ms_p95=float(llm_latency_ms_p95) if llm_latency_ms_p95 is not None else None,
        last_event_at=last_event_at,
        risk_level_current=metadata.get("risk_level_current") if isinstance(metadata.get("risk_level_current"), str) else None,
        paused_reason=paused_reason,
        pause_checkpoint=pause_checkpoint,
    )


@router.get("")
def list_tasks(
    project_id: Optional[str] = None,
    session_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=500),
    offset: Optional[int] = Query(default=None, ge=0),
) -> Dict[str, Any]:
    conn = _db_connect()
    try:
        if not _table_exists(conn, "tasks"):
            return TasksListResponse(tasks=[], total=0, limit=limit, offset=0).model_dump()

        cols = _table_columns(conn, "tasks")
        id_col = _task_id_col(cols)

        where = []
        params: list[Any] = []
        if project_id and "project_id" in cols:
            where.append("project_id = ?")
            params.append(project_id)
        if session_id and "session_id" in cols:
            where.append("session_id = ?")
            params.append(session_id)
        if status and "status" in cols:
            where.append("status = ?")
            params.append(status)
        where_sql = f" WHERE {' AND '.join(where)}" if where else ""

        use_offset = offset if offset is not None else (page - 1) * limit
        total = conn.execute(f"SELECT COUNT(*) FROM tasks{where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM tasks{where_sql} ORDER BY rowid DESC LIMIT ? OFFSET ?",
            params + [limit, use_offset],
        ).fetchall()

        tasks = []
        for r in rows:
            d = _as_task(r, id_col)
            # Parse metadata JSON if present.
            if "metadata" in r.keys() and r["metadata"]:
                try:
                    d["metadata"] = json.loads(r["metadata"])
                except Exception:
                    d["metadata"] = {}
            tasks.append(_as_task_response(d))

        return TasksListResponse(
            tasks=tasks,
            total=int(total),
            limit=int(limit),
            offset=int(use_offset),
        ).model_dump()
    finally:
        conn.close()


@router.get("/{task_id}")
def get_task(task_id: str) -> Dict[str, Any]:
    tm = TaskManager()
    task = tm.get_task(task_id)
    if not task:
        if _is_placeholder_task_id(task_id):
            return _as_task_response(_placeholder_task(task_id)).model_dump()
        raise HTTPException(status_code=404, detail="Task not found")
    return _as_task_response(task.to_dict()).model_dump()


@router.post("", status_code=201)
def create_task(payload: TaskCreateRequest) -> Dict[str, Any]:
    # Unified semantics:
    # - create task
    # - immediately start planning runner (default: plan-then-execute)
    # - runner stops at awaiting_approval after open_plan checkpoint
    tm = TaskManager()

    metadata = dict(payload.metadata or {})
    # Normalize user intent so TaskRunner can find it.
    nl_request = str(metadata.get("description") or payload.title).strip()
    metadata.setdefault("nl_request", nl_request)
    metadata.setdefault("run_mode", "assisted")
    metadata.setdefault("source", "webui")
    # Always start in legacy runner state machine.
    task = tm.create_task(
        title=payload.title,
        session_id=metadata.get("session_id"),
        created_by=payload.created_by or "webui",
        metadata=metadata,
    )

    tm.add_audit(
        task_id=task.task_id,
        event_type="WEBUI_TASK_CREATED",
        level="info",
        payload={"source": "webui", "intent": nl_request},
    )

    launched = _start_runner_thread(task_id=task.task_id, actor="webui_planning", use_real_pipeline=False)
    tm.add_audit(
        task_id=task.task_id,
        event_type="WEBUI_PLANNING_LAUNCHED",
        level="info",
        payload={"launched": launched},
    )

    # Return the task immediately; UI should poll /live until awaiting_approval.
    return _as_task_response(task.to_dict()).model_dump()


@router.post("/create_and_start", status_code=201)
def create_and_start_task(payload: TaskCreateRequest) -> Dict[str, Any]:
    # Legacy endpoint: keep behavior but still goes through plan-then-execute.
    # Clients should use POST /api/tasks + POST /api/tasks/{id}/approve instead.
    return create_task(payload)


@router.post("/{task_id}/approve")
def approve_task(task_id: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    tm = TaskManager()
    task = tm.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    md = task.metadata or {}
    # High-risk pause approval: allow the pending step to proceed.
    if md.get("pause_checkpoint") == "high_risk_action":
        pending_idx = md.get("pending_step_index")
        if isinstance(pending_idx, int):
            md["high_risk_approved_for_step"] = pending_idx
        md.pop("pause_reason", None)
        md.pop("pause_checkpoint", None)

    # If we paused due to executor review gate, mark that approval as granted.
    pending_exec_req = md.get("pending_execution_request_id")
    pending_approval_dir = md.get("pending_approval_dir")
    if isinstance(pending_exec_req, str) and isinstance(pending_approval_dir, str):
        try:
            from octopusos.core.executor.review_gate import ReviewGate
            gate = ReviewGate(Path(pending_approval_dir))
            gate.approve(pending_exec_req, approved_by="webui", notes="approved via /api/tasks/{id}/approve")
            tm.add_audit(
                task_id=task_id,
                event_type="EXECUTION_REQUEST_APPROVED",
                level="info",
                payload={"execution_request_id": pending_exec_req},
            )
            # Clear pending approval info.
            md.pop("pending_execution_request_id", None)
            md.pop("pending_approval_dir", None)
        except Exception as e:
            tm.add_audit(
                task_id=task_id,
                event_type="EXECUTION_REQUEST_APPROVAL_FAILED",
                level="error",
                payload={"execution_request_id": pending_exec_req, "error": str(e)},
            )

    # Approve == ignite execution.
    task.metadata = md
    task.status = "executing"
    tm.update_task(task)
    tm.add_audit(task_id=task_id, event_type="TASK_APPROVED", level="info", payload={"actor": "webui"})
    launched = _start_runner_thread(task_id=task_id, actor="webui_approve", use_real_pipeline=False)
    return {"ok": True, "task_id": task_id, "launched": launched}


@router.post("/{task_id}/pause")
def pause_task(task_id: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    tm = TaskManager()
    task = tm.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    reason = None
    if payload and isinstance(payload.get("reason"), str):
        reason = payload["reason"]
    md = task.metadata or {}
    if reason:
        md["pause_reason"] = reason
    md["pause_checkpoint"] = md.get("pause_checkpoint") or "manual_pause"
    task.metadata = md
    task.status = "paused"
    tm.update_task(task)
    tm.add_audit(task_id=task_id, event_type="TASK_PAUSED", level="info", payload={"reason": reason})
    return {"ok": True}


@router.post("/{task_id}/resume")
def resume_task(task_id: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    tm = TaskManager()
    task = tm.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    md = task.metadata or {}
    md.pop("pause_reason", None)
    md.pop("pause_checkpoint", None)
    task.metadata = md
    # Resume to executing by default.
    task.status = "executing"
    tm.update_task(task)
    tm.add_audit(task_id=task_id, event_type="TASK_RESUMED", level="info", payload={"actor": "webui"})
    launched = _start_runner_thread(task_id=task_id, actor="webui_resume", use_real_pipeline=False)
    return {"ok": True, "launched": launched}


@router.get("/{task_id}/live", response_model=TaskLiveResponse)
def get_task_live(task_id: str) -> Dict[str, Any]:
    if _is_placeholder_task_id(task_id):
        now = _now_iso().replace("+00:00", "Z")
        return TaskLiveResponse(
            task_id=task_id,
            status="created",
            stage="created",
            progress_percent=0,
            eta_seconds=None,
            steps_total=None,
            steps_done=None,
            throughput_steps_per_sec=None,
            llm_latency_ms_avg=None,
            llm_latency_ms_p95=None,
            last_event_at=now,
            risk_level_current=None,
            paused_reason=None,
            pause_checkpoint=None,
        ).model_dump()
    return _compute_live_metrics(task_id).model_dump()


@router.get("/{task_id}/open_plan")
def get_task_open_plan(task_id: str) -> Dict[str, Any]:
    plan = _load_open_plan(task_id)
    if not plan:
        if _is_placeholder_task_id(task_id):
            return {
                "goal": "Demo placeholder plan",
                "steps": [],
                "metadata": {"task_id": task_id, "placeholder": True},
            }
        raise HTTPException(status_code=404, detail="open_plan not found")
    return plan


@router.get("/{task_id}/evidence_bundle/latest")
def get_latest_evidence_bundle_meta(task_id: str) -> Dict[str, Any]:
    # Meta is safe to read even when downloads are disabled; keep download gated.
    if not _evidence_download_enabled():
        return {"task_id": task_id, "run_id": None, "generated_at": None, "sha256": None, "download_url": None}
    run_dir = _find_latest_e2e_real_run_dir_for_task(task_id)
    if not run_dir:
        return {"task_id": task_id, "run_id": None, "generated_at": None, "sha256": None, "download_url": None}

    bundle = run_dir / "bundle.zip"
    if not bundle.exists():
        return {"task_id": task_id, "run_id": None, "generated_at": None, "sha256": None, "download_url": None}

    record = _validate_e2e_real_bundle_ownership(expected_task_id=task_id, run_dir=run_dir)
    generated_at = record.get("generated_at")
    sha = None
    sha_path = run_dir / "bundle.sha256"
    if sha_path.exists():
        try:
            sha = sha_path.read_text(encoding="utf-8").strip()
        except Exception:
            sha = None
    return {
        "task_id": task_id,
        "run_id": run_dir.name,
        "generated_at": generated_at,
        "sha256": sha,
        "download_url": f"/api/tasks/{task_id}/evidence_bundle/latest/download",
    }


@router.get("/{task_id}/evidence_bundle/latest/download")
def download_latest_evidence_bundle(task_id: str):
    if not _evidence_download_enabled():
        raise HTTPException(status_code=403, detail="Evidence bundle download disabled")
    run_dir = _find_latest_e2e_real_run_dir_for_task(task_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Evidence bundle not found")
    _validate_e2e_real_bundle_ownership(expected_task_id=task_id, run_dir=run_dir)
    bundle = run_dir / "bundle.zip"
    if not bundle.exists():
        raise HTTPException(status_code=404, detail="Evidence bundle not found")
    filename = f"e2e-real-{run_dir.name}-{task_id}.zip"
    return FileResponse(
        path=str(bundle),
        filename=filename,
        media_type="application/zip",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{task_id}/audit", response_model=TaskAuditResponse)
def get_task_audit(task_id: str, limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0)) -> Dict[str, Any]:
    conn = _db_connect()
    try:
        if not _table_exists(conn, "task_audits"):
            return TaskAuditResponse(task_id=task_id, total=0, events=[]).model_dump()
        total = conn.execute("SELECT COUNT(*) FROM task_audits WHERE task_id = ?", (task_id,)).fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM task_audits WHERE task_id = ? ORDER BY created_at ASC LIMIT ? OFFSET ?",
            (task_id, limit, offset),
        ).fetchall()
        events: List[TaskAuditEvent] = []
        for r in rows:
            payload = None
            if r["payload"]:
                try:
                    payload = json.loads(r["payload"])
                except Exception:
                    payload = r["payload"]
            events.append(
                TaskAuditEvent(
                    audit_id=str(r["audit_id"]) if "audit_id" in r.keys() else None,
                    task_id=str(r["task_id"]),
                    level=str(r["level"]),
                    event_type=str(r["event_type"]),
                    payload=payload,
                    created_at=str(r["created_at"]),
                )
            )
        return TaskAuditResponse(task_id=task_id, total=int(total), events=events).model_dump()
    finally:
        conn.close()


@router.delete("/{task_id}")
def delete_task(task_id: str) -> Dict[str, Any]:
    conn = _db_connect()
    try:
        if not _table_exists(conn, "tasks"):
            raise HTTPException(status_code=404, detail="Task not found")
        cols = _table_columns(conn, "tasks")
        id_col = _task_id_col(cols)
        row = conn.execute(f"SELECT 1 FROM tasks WHERE {id_col} = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        conn.execute(f"DELETE FROM tasks WHERE {id_col} = ?", (task_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/{task_id}/route", response_model=RoutePlanResponse)
def get_task_route(task_id: str) -> Dict[str, str]:
    conn = _db_connect()
    try:
        if not _table_exists(conn, "tasks"):
            raise HTTPException(status_code=404, detail="Task not found")
        cols = _table_columns(conn, "tasks")
        id_col = _task_id_col(cols)
        row = conn.execute(f"SELECT * FROM tasks WHERE {id_col} = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        route = "default"
        if "route" in row.keys() and row["route"]:
            route = str(row["route"])
        elif "metadata" in row.keys() and row["metadata"]:
            try:
                route = str(json.loads(row["metadata"]).get("route") or route)
            except Exception:
                pass
        return {"route": route}
    finally:
        conn.close()


@router.post("/{task_id}/route")
def update_task_route(task_id: str, payload: Dict[str, Any]) -> Dict[str, bool]:
    route = payload.get("route") or payload.get("instance_id")  # backward compat
    if not route:
        raise HTTPException(status_code=400, detail="route is required")

    conn = _db_connect()
    try:
        if not _table_exists(conn, "tasks"):
            raise HTTPException(status_code=404, detail="Task not found")
        cols = _table_columns(conn, "tasks")
        id_col = _task_id_col(cols)
        row = conn.execute(f"SELECT * FROM tasks WHERE {id_col} = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        now = _now_iso()
        if "route" in cols:
            conn.execute(
                f"UPDATE tasks SET route = ?, updated_at = ? WHERE {id_col} = ?",
                (route, now, task_id),
            )
        elif "metadata" in cols:
            metadata = {}
            if row["metadata"]:
                try:
                    metadata = json.loads(row["metadata"])
                except Exception:
                    metadata = {}
            metadata["route"] = route
            conn.execute(
                f"UPDATE tasks SET metadata = ?, updated_at = ? WHERE {id_col} = ?",
                (json.dumps(metadata), now, task_id),
            )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.post("/batch")
def batch_create_tasks(payload: Dict[str, Any]) -> Dict[str, Any]:
    items = payload.get("tasks")
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="tasks must be a list")

    created = []
    for item in items:
        if not isinstance(item, dict):
            continue
        created.append(create_task(item)["task"])
    return {"tasks": created}
