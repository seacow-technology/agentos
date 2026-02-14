"""P0 compatibility router for /api/v0.31 projects/tasks endpoints."""

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
from octopusos.core.projects.factory import ensure_project_path
from octopusos.store import get_db_path
from octopusos.webui.api.compat_state import audit_event

router = APIRouter(prefix="/api/v0.31", tags=["compat"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _require_admin_token(token: Optional[str]) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Admin token required")
    if not validate_admin_token(token):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return "admin"


def _as_project(row: sqlite3.Row, id_col: str) -> Dict[str, Any]:
    pid = row[id_col]
    return {
        "id": pid,
        "project_id": pid,
        "name": row["name"] if "name" in row.keys() else "",
        "description": row["description"] if "description" in row.keys() else None,
        "status": row["status"] if "status" in row.keys() and row["status"] else "active",
        "created_at": row["created_at"] if "created_at" in row.keys() and row["created_at"] else _now_iso(),
        "updated_at": row["updated_at"] if "updated_at" in row.keys() else None,
    }


def _as_repo(row: sqlite3.Row) -> Dict[str, Any]:
    repo_id = row["repo_id"] if "repo_id" in row.keys() else row["id"]
    path = (
        row["workspace_relpath"]
        if "workspace_relpath" in row.keys()
        else row["local_path"]
        if "local_path" in row.keys()
        else row["path"]
        if "path" in row.keys()
        else "."
    )
    url = row["remote_url"] if "remote_url" in row.keys() else row["url"] if "url" in row.keys() else None
    return {
        "id": repo_id,
        "repo_id": repo_id,
        "project_id": row["project_id"] if "project_id" in row.keys() else "",
        "name": row["name"] if "name" in row.keys() else "",
        "path": path,
        "url": url,
        "created_at": row["created_at"] if "created_at" in row.keys() else _now_iso(),
        "updated_at": row["updated_at"] if "updated_at" in row.keys() else None,
    }


def _as_task(row: sqlite3.Row, id_col: str) -> Dict[str, Any]:
    tid = row[id_col]
    return {
        "id": tid,
        "task_id": tid,
        "project_id": row["project_id"] if "project_id" in row.keys() else None,
        "session_id": row["session_id"] if "session_id" in row.keys() else None,
        "title": row["title"] if "title" in row.keys() else "",
        "description": row["description"] if "description" in row.keys() else None,
        "status": row["status"] if "status" in row.keys() and row["status"] else "created",
        "created_at": row["created_at"] if "created_at" in row.keys() else _now_iso(),
        "updated_at": row["updated_at"] if "updated_at" in row.keys() else None,
    }


@router.get("/projects")
def list_projects(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=500),
    offset: Optional[int] = Query(default=None, ge=0),
    status: Optional[str] = None,
) -> Dict[str, Any]:
    conn = _db_connect()
    try:
        if not _table_exists(conn, "projects"):
            return {"success": True, "projects": [], "total": 0, "page": page, "limit": limit, "offset": 0, "source": "compat"}

        cols = _table_columns(conn, "projects")
        id_col = "project_id" if "project_id" in cols else "id" if "id" in cols else None
        if id_col is None:
            return {"success": True, "projects": [], "total": 0, "page": page, "limit": limit, "offset": 0, "source": "compat"}

        use_offset = offset if offset is not None else (page - 1) * limit
        where_sql = ""
        params: list[Any] = []
        if status and "status" in cols:
            where_sql = " WHERE status = ?"
            params.append(status)
        total = conn.execute(f"SELECT COUNT(*) FROM projects{where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM projects{where_sql} ORDER BY rowid DESC LIMIT ? OFFSET ?",
            params + [limit, use_offset],
        ).fetchall()
        projects = [_as_project(r, id_col) for r in rows]
        return {
            "success": True,
            "projects": projects,
            "total": total,
            "page": page,
            "limit": limit,
            "offset": use_offset,
            "source": "compat",
        }
    finally:
        conn.close()


@router.post("/projects", status_code=201)
async def create_project(
    payload: Dict[str, Any] = Body(...),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    conn = _db_connect()
    try:
        if not _table_exists(conn, "projects"):
            raise HTTPException(status_code=409, detail="projects table missing")
        cols = _table_columns(conn, "projects")
        id_col = "project_id" if "project_id" in cols else "id" if "id" in cols else None
        if id_col is None:
            raise HTTPException(status_code=409, detail="project id column missing")

        project_id = f"proj_{uuid4().hex[:12]}"
        now = _now_iso()
        resolved_path = payload.get("path")
        if "path" in cols:
            resolved_path = ensure_project_path(
                project_id=project_id,
                name=str(name),
                path=str(resolved_path).strip() if isinstance(resolved_path, str) else None,
            )
        data: Dict[str, Any] = {
            id_col: project_id,
            "name": str(name),
            "description": payload.get("description"),
            "status": payload.get("status") or "active",
            "created_at": now,
            "updated_at": now,
            "tags": json.dumps(payload.get("tags", [])),
            "settings": json.dumps(payload.get("settings", {})),
            "metadata": json.dumps(payload.get("metadata", {})),
            "path": resolved_path or "",
            "default_workdir": payload.get("default_workdir"),
            "created_by": "admin",
        }
        insert_data = {k: v for k, v in data.items() if k in cols}
        keys = list(insert_data.keys())
        conn.execute(
            f"INSERT INTO projects ({', '.join(keys)}) VALUES ({', '.join(['?'] * len(keys))})",
            [insert_data[k] for k in keys],
        )
        audit_event(
            conn,
            event_type="v031_project_create",
            endpoint="/api/v0.31/projects",
            actor=actor,
            payload=payload,
            result={"project_id": project_id},
        )
        conn.commit()
        row = conn.execute(f"SELECT * FROM projects WHERE {id_col} = ?", (project_id,)).fetchone()
        return {"success": True, "project": _as_project(row, id_col), "source": "compat"}
    finally:
        conn.close()


@router.get("/projects/{project_id}")
def get_project(project_id: str) -> Dict[str, Any]:
    conn = _db_connect()
    try:
        if not _table_exists(conn, "projects"):
            raise HTTPException(status_code=404, detail="Project not found")
        cols = _table_columns(conn, "projects")
        id_col = "project_id" if "project_id" in cols else "id" if "id" in cols else None
        if id_col is None:
            raise HTTPException(status_code=404, detail="Project not found")
        row = conn.execute(f"SELECT * FROM projects WHERE {id_col} = ?", (project_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")

        repos_count = 0
        if _table_exists(conn, "project_repos"):
            repos_count = conn.execute(
                "SELECT COUNT(*) FROM project_repos WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
        elif _table_exists(conn, "repos"):
            repos_count = conn.execute(
                "SELECT COUNT(*) FROM repos WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]

        tasks_count = 0
        if _table_exists(conn, "tasks"):
            tasks_count = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]

        return {
            "success": True,
            "project": _as_project(row, id_col),
            "repos": repos_count,
            "tasks_count": tasks_count,
            "source": "compat",
        }
    finally:
        conn.close()


@router.get("/projects/{project_id}/repos")
def list_project_repos(
    project_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=500),
    offset: Optional[int] = Query(default=None, ge=0),
) -> Dict[str, Any]:
    conn = _db_connect()
    try:
        table = "project_repos" if _table_exists(conn, "project_repos") else "repos" if _table_exists(conn, "repos") else None
        if table is None:
            return {"repos": [], "total": 0, "page": page, "limit": limit, "source": "compat"}

        use_offset = offset if offset is not None else (page - 1) * limit
        total = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE project_id = ? ORDER BY rowid DESC LIMIT ? OFFSET ?",
            (project_id, limit, use_offset),
        ).fetchall()
        return {
            "repos": [_as_repo(r) for r in rows],
            "total": total,
            "page": page,
            "limit": limit,
            "source": "compat",
        }
    finally:
        conn.close()


@router.post("/projects/{project_id}/repos", status_code=201)
async def create_project_repo(
    project_id: str,
    payload: Dict[str, Any] = Body(...),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = _db_connect()
    try:
        table = "project_repos" if _table_exists(conn, "project_repos") else "repos" if _table_exists(conn, "repos") else None
        if table is None:
            raise HTTPException(status_code=409, detail="repos table missing")
        cols = _table_columns(conn, table)
        repo_id = f"repo_{uuid4().hex[:12]}"
        now = _now_iso()
        data: Dict[str, Any] = {
            "repo_id": repo_id,
            "id": repo_id,
            "project_id": project_id,
            "name": payload.get("name") or f"repo-{repo_id[-4:]}",
            "workspace_relpath": payload.get("path") or payload.get("workspace_relpath") or ".",
            "local_path": payload.get("path") or ".",
            "path": payload.get("path") or ".",
            "remote_url": payload.get("url") or payload.get("remote_url"),
            "url": payload.get("url"),
            "default_branch": payload.get("default_branch") or "main",
            "role": payload.get("role") or "code",
            "is_writable": 1,
            "created_at": now,
            "updated_at": now,
            "metadata": json.dumps(payload.get("metadata", {})),
        }
        insert_data = {k: v for k, v in data.items() if k in cols}
        keys = list(insert_data.keys())
        conn.execute(
            f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({', '.join(['?'] * len(keys))})",
            [insert_data[k] for k in keys],
        )
        audit_event(
            conn,
            event_type="v031_repo_create",
            endpoint=f"/api/v0.31/projects/{project_id}/repos",
            actor=actor,
            payload=payload,
            result={"project_id": project_id, "name": data["name"]},
        )
        conn.commit()
        row = conn.execute(f"SELECT * FROM {table} WHERE project_id = ? AND name = ? ORDER BY rowid DESC LIMIT 1", (project_id, data["name"])).fetchone()
        return {"repo": _as_repo(row), "source": "compat"}
    finally:
        conn.close()


@router.get("/tasks")
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
            return {"tasks": [], "total": 0, "page": page, "limit": limit, "source": "compat"}
        cols = _table_columns(conn, "tasks")
        id_col = "task_id" if "task_id" in cols else "id" if "id" in cols else None
        if id_col is None:
            return {"tasks": [], "total": 0, "page": page, "limit": limit, "source": "compat"}

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
        return {
            "tasks": [_as_task(r, id_col) for r in rows],
            "total": total,
            "page": page,
            "limit": limit,
            "source": "compat",
        }
    finally:
        conn.close()


@router.post("/tasks", status_code=201)
async def create_task(
    payload: Dict[str, Any] = Body(...),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = _db_connect()
    try:
        if not _table_exists(conn, "tasks"):
            raise HTTPException(status_code=409, detail="tasks table missing")
        cols = _table_columns(conn, "tasks")
        id_col = "task_id" if "task_id" in cols else "id" if "id" in cols else None
        if id_col is None:
            raise HTTPException(status_code=409, detail="task id column missing")

        task_id = f"task_{uuid4().hex[:12]}"
        now = _now_iso()
        data: Dict[str, Any] = {
            id_col: task_id,
            "title": payload.get("title") or "Untitled Task",
            "description": payload.get("description"),
            "status": payload.get("status") or "created",
            "project_id": payload.get("project_id"),
            "session_id": payload.get("session_id"),
            "created_at": now,
            "updated_at": now,
            "created_by": "admin",
            "metadata": json.dumps(payload.get("metadata", {})),
            "created_at_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
            "updated_at_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
        insert_data = {k: v for k, v in data.items() if k in cols}
        keys = list(insert_data.keys())
        conn.execute(
            f"INSERT INTO tasks ({', '.join(keys)}) VALUES ({', '.join(['?'] * len(keys))})",
            [insert_data[k] for k in keys],
        )
        audit_event(
            conn,
            event_type="v031_task_create",
            endpoint="/api/v0.31/tasks",
            actor=actor,
            payload=payload,
            result={"task_id": task_id},
        )
        conn.commit()
        row = conn.execute(f"SELECT * FROM tasks WHERE {id_col} = ?", (task_id,)).fetchone()
        return {"task": _as_task(row, id_col), "source": "compat"}
    finally:
        conn.close()
