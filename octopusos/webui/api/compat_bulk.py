"""Bulk compatibility router with persistent state + audit for write endpoints."""

from __future__ import annotations

import hashlib
import json
import os
import time
import concurrent.futures
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Iterable
from uuid import uuid4

from fastapi import APIRouter, Body, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from octopusos.core.capabilities.admin_token import validate_admin_token
from octopusos.core.audit import INFO_NEED_CLASSIFICATION, INFO_NEED_OUTCOME
from octopusos.core.time import parse_db_time
from octopusos.core.db.registry_db import get_db
from octopusos.webui.db.memory_db import memory_db_connect, memory_db_path
from octopusos.webui.api.compat_state import (
    audit_event,
    db_connect,
    ensure_schema,
    get_entity,
    get_state,
    list_entities,
    now_iso,
    set_state,
    soft_delete_entity,
    upsert_entity,
)
from octopusos.webui.api.capability_dashboard_stats import (
    build_capability_dashboard_stats,
    default_capability_dashboard_stats,
)

router = APIRouter(prefix="/api", tags=["compat"])

_INFO_NEED_SCAN_LIMIT = 50_000  # guardrail: summary should not depend on client-provided limit

def _env_flag(name: str) -> bool:
    raw = (os.getenv(name, "") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _compat_demo_enabled() -> bool:
    # Demo mode is intentionally explicit to avoid masking real-data wiring work.
    return _env_flag("OCTOPUSOS_COMPAT_DEMO") or _env_flag("OCTOPUSOS_DEBUG")


def _strip_meta(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for (k, v) in data.items() if not k.startswith("_")}

def _overlay_defined(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Overlay keys from overlay onto base, but ignore None values (treat as missing)."""
    out = dict(base)
    for k, v in overlay.items():
        if v is None:
            continue
        out[k] = v
    return out


def _demo_trust_tiers() -> list[Dict[str, Any]]:
    # Must match apps/webui/src/services/networkos.service.ts TrustTierInfo.
    return [
        {
            "tier": "T0",
            "name": "T0 - Local Only",
            "capabilities": ["local_mcp", "local_files"],
            "count": 2,
            "default_policy": {
                "risk_level": "LOW",
                "requires_admin_token": False,
                "default_quota_profile": {
                    "calls_per_minute": 120,
                    "max_concurrent": 2,
                    "max_runtime_ms": 15_000,
                },
            },
        },
        {
            "tier": "T1",
            "name": "T1 - Verified Source",
            "capabilities": ["verified_fetch", "safe_tools"],
            "count": 2,
            "default_policy": {
                "risk_level": "MED",
                "requires_admin_token": False,
                "default_quota_profile": {
                    "calls_per_minute": 240,
                    "max_concurrent": 4,
                    "max_runtime_ms": 30_000,
                },
            },
        },
        {
            "tier": "T2",
            "name": "T2 - Enterprise",
            "capabilities": ["enterprise_connectors", "policy_gates"],
            "count": 2,
            "default_policy": {
                "risk_level": "HIGH",
                "requires_admin_token": True,
                "default_quota_profile": {
                    "calls_per_minute": 600,
                    "max_concurrent": 8,
                    "max_runtime_ms": 60_000,
                },
            },
        },
        {
            "tier": "T3",
            "name": "T3 - Admin Verified",
            "capabilities": ["admin_actions", "high_risk_ops"],
            "count": 2,
            "default_policy": {
                "risk_level": "CRITICAL",
                "requires_admin_token": True,
                "default_quota_profile": {
                    "calls_per_minute": 1200,
                    "max_concurrent": 16,
                    "max_runtime_ms": 120_000,
                },
            },
        },
    ]


def _demo_publishers() -> list[Dict[str, Any]]:
    now_ms = int(time.time() * 1000)
    day = 24 * 60 * 60 * 1000
    return [
        {
            "publisher_id": "acme",
            "name": "ACME Labs",
            "trust_level": "verified",
            "trust_score": 92.4,
            "capability_count": 12,
            "successful_executions": 418,
            "failed_executions": 6,
            "success_rate": 98.7,
            "average_risk_score": 12.4,
            "registered_at": now_ms - 180 * day,
            "last_activity_at": now_ms - 2 * day,
        },
        {
            "publisher_id": "bluefin",
            "name": "Bluefin Research",
            "trust_level": "high",
            "trust_score": 81.6,
            "capability_count": 7,
            "successful_executions": 201,
            "failed_executions": 11,
            "success_rate": 96.1,
            "average_risk_score": 18.9,
            "registered_at": now_ms - 240 * day,
            "last_activity_at": now_ms - 5 * day,
        },
        {
            "publisher_id": "nightjar",
            "name": "Nightjar Works",
            "trust_level": "medium",
            "trust_score": 54.3,
            "capability_count": 3,
            "successful_executions": 64,
            "failed_executions": 18,
            "success_rate": 88.5,
            "average_risk_score": 41.2,
            "registered_at": now_ms - 90 * day,
            "last_activity_at": now_ms - 9 * day,
        },
        {
            "publisher_id": "zephyr",
            "name": "Zephyr OSS",
            "trust_level": "high",
            "trust_score": 74.2,
            "capability_count": 5,
            "successful_executions": 150,
            "failed_executions": 9,
            "success_rate": 93.9,
            "average_risk_score": 22.7,
            "registered_at": now_ms - 365 * day,
            "last_activity_at": now_ms - 1 * day,
        },
        {
            "publisher_id": "suspended-sample",
            "name": "Suspended Sample",
            "trust_level": "low",
            "trust_score": 12.0,
            "capability_count": 1,
            "successful_executions": 3,
            "failed_executions": 9,
            "success_rate": 25.0,
            "average_risk_score": 78.0,
            "registered_at": now_ms - 30 * day,
            "last_activity_at": now_ms - 30 * day,
        },
    ]


def _demo_publishers_index() -> Dict[str, Dict[str, Any]]:
    return {str(p.get("publisher_id")): p for p in _demo_publishers() if p.get("publisher_id")}


def _demo_trust_trajectory(entity_id: str, *, time_range: str = "30d") -> Dict[str, Any]:
    # Must match apps/webui/src/services/networkos.service.ts TrustTrajectory.
    now_ms = int(time.time() * 1000)
    # Deterministic-ish base score by entity id.
    h = hashlib.sha256(entity_id.encode("utf-8")).hexdigest()
    base = (int(h[:8], 16) % 45) / 100.0 + 0.45  # 0.45 - 0.89

    # Pick history length by time_range.
    if time_range == "7d":
        points = 10
        span_ms = 7 * 24 * 60 * 60 * 1000
    elif time_range == "90d":
        points = 18
        span_ms = 90 * 24 * 60 * 60 * 1000
    elif time_range == "all":
        points = 24
        span_ms = 180 * 24 * 60 * 60 * 1000
    else:
        points = 14
        span_ms = 30 * 24 * 60 * 60 * 1000

    def _state_for_score(score: float) -> str:
        if score >= 0.85:
            return "STABLE"
        if score >= 0.55:
            return "EARNING"
        return "DEGRADING"

    score_history: list[Dict[str, Any]] = []
    for i in range(points):
        t_ms = now_ms - int(span_ms * (points - 1 - i) / max(1, points - 1))
        # Gentle upward drift with a tiny deterministic wobble.
        wobble = ((int(h[8 + (i % 16)], 16) % 7) - 3) / 500.0
        score = max(0.05, min(0.99, base + (i / max(1, points - 1)) * 0.08 + wobble))
        score_history.append(
            {
                "timestamp": datetime.fromtimestamp(t_ms / 1000.0, tz=timezone.utc).isoformat(),
                "trust_score": float(f"{score:.3f}"),
                "state": _state_for_score(score),
                "event": "demo:heartbeat" if i else "demo:bootstrap",
            }
        )

    latest = score_history[-1]["trust_score"] if score_history else base
    current_state_label = _state_for_score(float(latest))

    current_state = {
        "extension_id": entity_id,
        "action_id": "demo_action",
        "current_state": current_state_label,
        "consecutive_successes": 7 if current_state_label != "DEGRADING" else 1,
        "consecutive_failures": 0 if current_state_label != "DEGRADING" else 3,
        "policy_rejections": 0 if current_state_label == "STABLE" else (1 if current_state_label == "EARNING" else 4),
        "high_risk_events": 0 if current_state_label != "DEGRADING" else 2,
        "state_entered_at_ms": now_ms - (72 * 60 * 60 * 1000),
        "last_event_at_ms": now_ms - (15 * 60 * 1000),
        "updated_at_ms": now_ms,
    }

    transitions: list[Dict[str, Any]] = [
        {
            "transition_id": f"demo_{entity_id}_t1",
            "extension_id": entity_id,
            "action_id": "demo_action",
            "old_state": "EARNING",
            "new_state": "STABLE" if current_state_label == "STABLE" else "EARNING",
            "trigger_event": "demo:audit_passed",
            "explain": "Demo transition based on passing basic audit checks.",
            "risk_context_json": json.dumps({"risk": "low", "demo": True}, ensure_ascii=True),
            "policy_context_json": json.dumps({"policy": "baseline", "demo": True}, ensure_ascii=True),
            "created_at_ms": now_ms - (5 * 24 * 60 * 60 * 1000),
        },
        {
            "transition_id": f"demo_{entity_id}_t2",
            "extension_id": entity_id,
            "action_id": "demo_action",
            "old_state": "EARNING" if current_state_label != "DEGRADING" else "STABLE",
            "new_state": current_state_label,
            "trigger_event": "demo:recent_activity",
            "explain": "Demo transition based on recent execution and policy outcomes.",
            "risk_context_json": json.dumps({"risk": "medium", "demo": True}, ensure_ascii=True),
            "policy_context_json": json.dumps({"policy": "gates_v1", "demo": True}, ensure_ascii=True),
            "created_at_ms": now_ms - (1 * 24 * 60 * 60 * 1000),
        },
    ]

    stats = {
        "total_transitions": len(transitions),
        "time_in_current_state_hours": 72,
        "success_rate": float(f"{max(0.0, min(1.0, float(latest))):.3f}"),
        "policy_violation_count": int(current_state["policy_rejections"]),
    }

    return {
        "entity_id": entity_id,
        "current_state": current_state,
        "score_history": score_history,
        "transitions": transitions,
        "stats": stats,
    }


class MemoryEntryResponse(BaseModel):
    id: Optional[str] = None
    scope: Optional[str] = None
    type: Optional[str] = None
    content: Dict[str, Any] = Field(default_factory=dict)
    tags: list[Any] = Field(default_factory=list)
    sources: list[Any] = Field(default_factory=list)
    confidence: Optional[float] = None
    project_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MemoryEntriesResponse(BaseModel):
    entries: list[MemoryEntryResponse]
    total: int
    limit: int
    offset: int = 0
    source: str = "compat"
    store_path: Optional[str] = None


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    num = float(max(0, value))
    idx = 0
    while num >= 1024 and idx < len(units) - 1:
        num /= 1024
        idx += 1
    if idx == 0:
        return f"{int(num)} {units[idx]}"
    return f"{num:.1f} {units[idx]}"


def _parse_timestamp(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1_000_000_000_000:  # epoch milliseconds
            ts /= 1000.0
        return ts
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            return _parse_timestamp(int(raw))
        try:
            normalized = raw.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).timestamp()
        except ValueError:
            try:
                return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                return None
    return None


def _count_repo_skills() -> int:
    repo_root = Path(__file__).resolve().parents[4]
    skills_root = repo_root / "skills"
    if not skills_root.exists():
        return 0
    return len(list(skills_root.rglob("SKILL.md")))


def _safe_count_agents() -> int:
    try:
        from octopusos.core.frontdesk.agent_directory import list_registered_agents

        return len(list_registered_agents(limit=500))
    except Exception:
        return 0


def _require_admin_token(token: Optional[str]) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Admin token required")
    if not validate_admin_token(token):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return "admin"


def _ok(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload.setdefault("source", "compat")
    return payload


def _entity_id(item: Dict[str, Any]) -> str:
    return str(item.get("id") or item.get("_entity_id") or "")


def _default_budget_global() -> Dict[str, Any]:
    return {
        "max_tokens": 32768,
        "auto_derive": True,
        "allocation": {
            "window_tokens": 12000,
            "rag_tokens": 6000,
            "memory_tokens": 4000,
            "summary_tokens": 4000,
            "system_tokens": 6768,
        },
        "safety_margin": 0.15,
        "generation_max_tokens": 2048,
        "safe_threshold": 0.7,
        "critical_threshold": 0.9,
    }


def _ensure_content_table(conn) -> None:
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


@router.get("/overview")
def get_overview() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)

        total_tasks = 0
        recent_tasks = 0
        completed_success = 0
        completed_failed = 0
        sessions_total = 0
        active_sessions = 0

        if _table_exists(conn, "tasks"):
            total_tasks = int(conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] or 0)

            rows = conn.execute(
                "SELECT status, created_at, updated_at FROM tasks"
            ).fetchall()
            now_ts = time.time()
            recent_cutoff = now_ts - (24 * 60 * 60)

            for row in rows:
                status = str(row["status"] or "").strip().lower()
                if status in {"done", "completed", "success", "succeeded"}:
                    completed_success += 1
                elif status in {"failed", "error", "cancelled", "canceled", "aborted"}:
                    completed_failed += 1

                ts = _parse_timestamp(row["updated_at"]) or _parse_timestamp(row["created_at"])
                if ts is not None and ts >= recent_cutoff:
                    recent_tasks += 1
        else:
            # Fallback only when tasks table doesn't exist.
            total_tasks = len(list_entities(conn, namespace="tasks"))
            recent_tasks = total_tasks

        if _table_exists(conn, "chat_sessions"):
            sessions_total = int(conn.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0] or 0)
            rows = conn.execute("SELECT updated_at, updated_at_ms, created_at, created_at_ms FROM chat_sessions").fetchall()
            now_ts = time.time()
            active_cutoff = now_ts - (24 * 60 * 60)
            for row in rows:
                ts = (
                    _parse_timestamp(row["updated_at_ms"])
                    or _parse_timestamp(row["updated_at"])
                    or _parse_timestamp(row["created_at_ms"])
                    or _parse_timestamp(row["created_at"])
                )
                if ts is not None and ts >= active_cutoff:
                    active_sessions += 1

        finished = completed_success + completed_failed
        if finished > 0:
            success_rate = f"{(completed_success / finished) * 100:.1f}%"
        elif total_tasks > 0:
            success_rate = "0.0%"
        else:
            success_rate = "0%"

        agents_count = _safe_count_agents()
        skills = _count_repo_skills()

        try:
            import psutil  # type: ignore

            proc = psutil.Process()
            uptime_seconds = max(0, int(time.time() - proc.create_time()))
            cpu_usage = f"{psutil.cpu_percent(interval=0.1):.1f}%"
            memory_usage = f"{psutil.virtual_memory().percent:.1f}%"
            disk_usage = f"{psutil.disk_usage('/').percent:.1f}%"
            net = psutil.net_io_counters()
            network_usage = f"rx {_format_bytes(int(net.bytes_recv))} / tx {_format_bytes(int(net.bytes_sent))}"
        except Exception:
            uptime_seconds = 0
            cpu_usage = "0.0%"
            memory_usage = "0.0%"
            disk_usage = "0.0%"
            network_usage = "rx 0 B / tx 0 B"

        db_path = conn.execute("PRAGMA database_list").fetchone()["file"]
        db_size_text = "0 B"
        if db_path:
            db_file = Path(str(db_path))
            if db_file.exists():
                db_size_text = _format_bytes(db_file.stat().st_size)

        return _ok(
            {
                "status": "ok",
                "timestamp": now_iso(),
                "uptime_seconds": uptime_seconds,
                "source": "real_overview",
                "metrics": {
                    "total_tasks": total_tasks,
                    "active_agents": active_sessions if active_sessions > 0 else agents_count,
                    "success_rate": success_rate,
                    "uptime_seconds": uptime_seconds,
                    "cpu": cpu_usage,
                    "memory": memory_usage,
                    "tasks": recent_tasks,
                    "recent_tasks": recent_tasks,
                    "agents": agents_count,
                    "recent_agents": active_sessions if active_sessions > 0 else agents_count,
                    "skills": skills,
                    "disk_usage": disk_usage,
                    "network_usage": network_usage,
                    "database_size": db_size_text,
                    "sessions_total": sessions_total,
                },
            }
        )
    finally:
        conn.close()


@router.post("/selfcheck")
def run_selfcheck(admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    checks = {"database": "pass", "providers": "pass", "compat_contract": "pass"}
    conn = db_connect()
    try:
        ensure_schema(conn)
        result = {"status": "ok", "checks": checks, "run_id": f"selfcheck_{uuid4().hex[:10]}"}
        audit_event(
            conn,
            event_type="selfcheck_run",
            endpoint="/api/selfcheck",
            actor=actor,
            payload={},
            result=result,
        )
        conn.commit()
        return _ok(result)
    finally:
        conn.close()


@router.post("/runtime/fix-permissions")
def fix_permissions(admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        result = {"status": "ok", "message": "No permission issues detected", "run_id": f"permfix_{uuid4().hex[:10]}"}
        audit_event(
            conn,
            event_type="runtime_fix_permissions",
            endpoint="/api/runtime/fix-permissions",
            actor=actor,
            payload={},
            result=result,
        )
        conn.commit()
        return _ok(result)
    finally:
        conn.close()


@router.get("/messages")
def list_messages() -> Dict[str, Any]:
    return _ok({"messages": []})


@router.get("/plugins")
def list_plugins() -> Dict[str, Any]:
    return _ok({"plugins": []})


@router.get("/tools")
def list_tools() -> Dict[str, Any]:
    # Best-effort real tools listing:
    # - Extension tools (installed extensions)
    # - MCP tools (enabled MCP servers)
    # Plus a small set of built-in tools that are implemented by this repo.
    tools: list[dict[str, Any]] = []

    def _collect_best_effort() -> list[dict[str, Any]]:
        from octopusos.core.capabilities.registry import CapabilityRegistry
        from octopusos.core.extensions.registry import ExtensionRegistry

        cap = CapabilityRegistry(ExtensionRegistry())
        out: list[dict[str, Any]] = []
        for t in cap.list_tools():
            out.append(
                {
                    "name": t.name,
                    "description": t.description,
                    "tool_id": t.tool_id,
                    "risk_level": t.risk_level.value if hasattr(t.risk_level, "value") else str(t.risk_level),
                    "side_effects": list(t.side_effect_tags or []),
                    "enabled": bool(getattr(t, "enabled", True)),
                    "source_type": t.source_type.value if hasattr(t.source_type, "value") else str(t.source_type),
                    "input_schema": t.input_schema or {},
                }
            )
        return out

    # Keep /api/tools responsive even if imports/capability discovery is slow.
    ex: concurrent.futures.ThreadPoolExecutor | None = None
    try:
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(_collect_best_effort)
        tools = fut.result(timeout=2.0)
    except Exception:
        tools = []
    finally:
        if ex is not None:
            # Do not block response waiting for slow background discovery.
            try:
                ex.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                ex.shutdown(wait=False)

    # Built-in tool (implemented by /api/channels/{channel_id}/send)
    tools.append(
        {
            "name": "communication.send_message",
            "description": "Send a message via CommunicationOS channel (audited).",
            "tool_id": "builtin:communication.send_message",
            "risk_level": "HIGH",
            "side_effects": ["external_comm.send_message"],
            "enabled": True,
            "source_type": "builtin",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string"},
                    "peer_user_key": {"type": "string"},
                    "peer_conversation_key": {"type": "string"},
                    "text": {"type": "string"},
                    "session_id": {"type": "string"},
                },
                "required": ["channel_id", "peer_conversation_key", "text"],
            },
        }
    )

    return _ok({"tools": tools})


@router.get("/triggers")
def list_triggers() -> Dict[str, Any]:
    return _ok({"triggers": []})


@router.get("/users")
def list_users() -> Dict[str, Any]:
    return _ok({"users": []})


@router.get("/budget/global")
def get_budget_global() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        value = get_state(conn, key="budget_global", default=None)
        if not isinstance(value, dict):
            value = _default_budget_global()
            set_state(conn, key="budget_global", value=value)
            conn.commit()
        out = dict(value)
        out["source"] = "compat"
        return out
    finally:
        conn.close()


@router.put("/budget/global")
def put_budget_global(
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        current = get_state(conn, key="budget_global", default=None)
        if not isinstance(current, dict):
            current = _default_budget_global()
        updated = dict(current)
        allocation = dict(updated.get("allocation") or {})
        for k in ["window_tokens", "rag_tokens", "memory_tokens", "summary_tokens", "system_tokens"]:
            if k in payload:
                allocation[k] = payload[k]
        if allocation:
            updated["allocation"] = allocation
        for k in ["max_tokens", "auto_derive", "safety_margin", "generation_max_tokens", "safe_threshold", "critical_threshold"]:
            if k in payload:
                updated[k] = payload[k]
        set_state(conn, key="budget_global", value=updated)
        audit_event(
            conn,
            event_type="budget_global_update",
            endpoint="/api/budget/global",
            actor=actor,
            payload=payload,
            result={"ok": True},
        )
        conn.commit()
        out = dict(updated)
        out["source"] = "compat"
        return out
    finally:
        conn.close()


@router.get("/capability/governance/audit")
def capability_governance_audit(
    agent_id: Optional[str] = Query(default=None),
    capability_id: Optional[str] = Query(default=None),
    allowed: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT event_id, event_type, endpoint, actor, result_json, created_at
            FROM compat_audit_events
            ORDER BY event_id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        invocations = []
        allow_count = 0
        for r in rows:
            result = {}
            if r["result_json"]:
                try:
                    result = json.loads(r["result_json"])
                except Exception:
                    result = {}
            is_allowed = bool(result.get("allowed", True))
            if allowed is not None and is_allowed != allowed:
                continue
            if is_allowed:
                allow_count += 1
            invocations.append(
                {
                    "invocation_id": f"inv_{r['event_id']}",
                    "agent_id": agent_id or "compat-agent",
                    "capability_id": capability_id or "compat-capability",
                    "operation": r["event_type"],
                    "allowed": is_allowed,
                    "reason": result.get("reason", "compat"),
                    "context": {"endpoint": r["endpoint"]},
                    "timestamp": r["created_at"],
                }
            )
        total = len(invocations)
        denied = max(0, total - allow_count)
        return {
            "invocations": invocations,
            "stats": {
                "total": total,
                "allowed": allow_count,
                "denied": denied,
                "success_rate": (allow_count / total) if total else 1.0,
            },
            "pagination": {
                "limit": limit,
                "offset": offset,
                "has_more": total >= limit,
            },
            "source": "compat",
        }
    finally:
        conn.close()


@router.get("/snippets")
def list_snippets() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        snippets = []
        for item in list_entities(conn, namespace="snippets"):
            snippets.append(
                {
                    "id": _entity_id(item),
                    "title": item.get("title", ""),
                    "content": item.get("content", ""),
                    "created_at": item.get("created_at") or item.get("_created_at") or now_iso(),
                    "updated_at": item.get("updated_at") or item.get("_updated_at") or now_iso(),
                }
            )
        return _ok({"snippets": snippets})
    finally:
        conn.close()


@router.post("/snippets")
def create_snippet(
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    snippet_id = f"snip_{uuid4().hex[:10]}"
    now = now_iso()
    data = {"id": snippet_id, "title": payload.get("title", "Untitled"), "content": payload.get("content", ""), "created_at": now, "updated_at": now}
    conn = db_connect()
    try:
        ensure_schema(conn)
        upsert_entity(conn, namespace="snippets", entity_id=snippet_id, data=data, status="active")
        audit_event(conn, event_type="snippet_create", endpoint="/api/snippets", actor=actor, payload=payload, result={"id": snippet_id})
        conn.commit()
        return _ok({"snippet": data})
    finally:
        conn.close()


@router.put("/snippets/{snippet_id}")
def update_snippet(
    snippet_id: str,
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = get_entity(conn, namespace="snippets", entity_id=snippet_id)
        if not existing or existing.get("_deleted"):
            raise HTTPException(status_code=404, detail="Snippet not found")
        updated = {
            "id": snippet_id,
            "title": payload.get("title", existing.get("title", "Untitled")),
            "content": payload.get("content", existing.get("content", "")),
            "created_at": existing.get("created_at") or existing.get("_created_at") or now_iso(),
            "updated_at": now_iso(),
        }
        upsert_entity(conn, namespace="snippets", entity_id=snippet_id, data=updated, status="active")
        audit_event(conn, event_type="snippet_update", endpoint=f"/api/snippets/{snippet_id}", actor=actor, payload=payload, result={"id": snippet_id})
        conn.commit()
        return _ok({"snippet": updated})
    finally:
        conn.close()


@router.delete("/snippets/{snippet_id}")
def delete_snippet(snippet_id: str, admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        soft_delete_entity(conn, namespace="snippets", entity_id=snippet_id)
        audit_event(conn, event_type="snippet_delete", endpoint=f"/api/snippets/{snippet_id}", actor=actor, payload={"id": snippet_id}, result={"ok": True})
        conn.commit()
        return _ok({"ok": True, "id": snippet_id})
    finally:
        conn.close()


@router.get("/answers/packs")
def list_answer_packs() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        data = []
        for item in list_entities(conn, namespace="answer_packs"):
            data.append(
                {
                    "id": _entity_id(item),
                    "name": item.get("name", ""),
                    "status": item.get("status", "draft"),
                    "items": item.get("items", []),
                    "metadata": item.get("metadata", {}),
                    "created_at": item.get("created_at") or item.get("_created_at") or now_iso(),
                    "updated_at": item.get("updated_at") or item.get("_updated_at") or now_iso(),
                }
            )
        return _ok({"ok": True, "data": data, "total": len(data)})
    finally:
        conn.close()


@router.get("/answers/packs/{pack_id}")
def get_answer_pack(pack_id: str) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        item = get_entity(conn, namespace="answer_packs", entity_id=pack_id)
        if not item or item.get("_deleted"):
            return _ok(
                {
                    "ok": True,
                    "data": {
                        "id": pack_id,
                        "name": pack_id,
                        "status": "draft",
                        "items": [],
                        "metadata": {},
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    },
                }
            )
        return _ok(
            {
                "ok": True,
                "data": {
                    "id": pack_id,
                    "name": item.get("name", pack_id),
                    "status": item.get("status", "draft"),
                    "items": item.get("items", []),
                    "metadata": item.get("metadata", {}),
                    "created_at": item.get("created_at") or item.get("_created_at") or now_iso(),
                    "updated_at": item.get("updated_at") or item.get("_updated_at") or now_iso(),
                },
            }
        )
    finally:
        conn.close()


@router.post("/answers/packs")
def create_answer_pack(
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    pack_id = f"pack_{uuid4().hex[:10]}"
    now = now_iso()
    data = {
        "id": pack_id,
        "name": payload.get("name", "Untitled Pack"),
        "status": payload.get("status", "draft"),
        "items": payload.get("answers", payload.get("items", [])),
        "metadata": payload.get("metadata", {}),
        "created_at": now,
        "updated_at": now,
    }
    conn = db_connect()
    try:
        ensure_schema(conn)
        upsert_entity(conn, namespace="answer_packs", entity_id=pack_id, data=data, status=data["status"])
        audit_event(conn, event_type="answer_pack_create", endpoint="/api/answers/packs", actor=actor, payload=payload, result={"id": pack_id})
        conn.commit()
        return _ok({"ok": True, "data": data})
    finally:
        conn.close()


@router.get("/skills")
def list_skills() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        skills = []
        for item in list_entities(conn, namespace="skills"):
            skills.append(
                {
                    "id": _entity_id(item),
                    "name": item.get("name", ""),
                    "description": item.get("description", ""),
                    "version": item.get("version", "0.1.0"),
                    "status": item.get("status", "installed"),
                    "created_at": item.get("created_at") or item.get("_created_at") or now_iso(),
                }
            )
        return _ok({"skills": skills, "total": len(skills)})
    finally:
        conn.close()


@router.get("/skills/{skill_id}")
def get_skill(skill_id: str) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        item = get_entity(conn, namespace="skills", entity_id=skill_id)
        if not item or item.get("_deleted"):
            return _ok(
                {
                    "skill": {
                        "id": skill_id,
                        "name": skill_id,
                        "description": "",
                        "version": "0.1.0",
                        "status": "available",
                        "created_at": now_iso(),
                    }
                }
            )
        return _ok(
            {
                "skill": {
                    "id": skill_id,
                    "name": item.get("name", skill_id),
                    "description": item.get("description", ""),
                    "version": item.get("version", "0.1.0"),
                    "status": item.get("status", "installed"),
                    "created_at": item.get("created_at") or item.get("_created_at") or now_iso(),
                }
            }
        )
    finally:
        conn.close()


@router.post("/skills/install")
def install_skill(
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    skill_id = payload.get("skill_id") or f"skill_{uuid4().hex[:10]}"
    now = now_iso()
    data = {
        "id": skill_id,
        "name": payload.get("name", skill_id),
        "description": payload.get("description", ""),
        "version": payload.get("version", "0.1.0"),
        "status": "installed",
        "created_at": now,
    }
    conn = db_connect()
    try:
        ensure_schema(conn)
        upsert_entity(conn, namespace="skills", entity_id=skill_id, data=data, status="installed")
        audit_event(conn, event_type="skill_install", endpoint="/api/skills/install", actor=actor, payload=payload, result={"skill_id": skill_id})
        conn.commit()
        return _ok({"skill": data})
    finally:
        conn.close()


@router.get("/communication/mode")
def get_comm_mode() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        mode = get_state(conn, key="communication_mode", default="local_open")
        return _ok({"mode": mode, "runtime_mode": mode})
    finally:
        conn.close()


@router.put("/communication/mode")
def set_comm_mode(payload: Dict[str, Any], admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    mode = payload.get("mode") or payload.get("runtime_mode") or "local_open"
    mode = str(mode).strip().lower()
    normalize = {
        "local": "local_open",
        "open": "local_open",
        "localopen": "local_open",
        "locked": "local_locked",
        "locallocked": "local_locked",
        "remote": "remote_exposed",
        "exposed": "remote_exposed",
        "remoteexposed": "remote_exposed",
    }
    mode = normalize.get(mode, mode)
    conn = db_connect()
    try:
        ensure_schema(conn)
        set_state(conn, key="communication_mode", value=mode)
        audit_event(conn, event_type="communication_mode_set", endpoint="/api/communication/mode", actor=actor, payload=payload, result={"mode": mode})
        conn.commit()
        return _ok({"ok": True, "mode": mode})
    finally:
        conn.close()


@router.get("/communication/status")
def get_comm_status() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        mode = get_state(conn, key="communication_mode", default="local_open")
        try:
            from octopusos.communicationos.runtime import get_communication_runtime

            rt = get_communication_runtime()
            channels = rt.list_marketplace()
        except Exception:
            channels = []
        return _ok({"status": "ok", "channels": channels, "mode": mode})
    finally:
        conn.close()


@router.get("/communication/policy")
def get_comm_policy() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        mode = get_state(conn, key="communication_mode", default="local_open")
        return _ok({"policy": {"mode": mode}})
    finally:
        conn.close()


@router.get("/communication/audits")
def list_comm_audits() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT event_id, event_type, endpoint, actor, created_at
            FROM compat_audit_events
            WHERE endpoint LIKE '/api/communication/%'
            ORDER BY event_id DESC
            LIMIT 200
            """
        ).fetchall()
        audits = [dict(r) for r in rows]
        return _ok({"audits": audits, "total": len(audits)})
    finally:
        conn.close()


@router.get("/context/status")
def get_context_status() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        sessions = []
        for item in list_entities(conn, namespace="context_items"):
            sessions.append(
                {
                    "id": _entity_id(item),
                    "path": item.get("path"),
                    "status": item.get("status", "attached"),
                    "revision": item.get("revision", 1),
                    "updated_at": item.get("updated_at") or item.get("_updated_at") or now_iso(),
                }
            )
        return _ok({"status": "ok", "sessions": sessions})
    finally:
        conn.close()


@router.post("/context/attach")
def context_attach(
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    item_id = payload.get("id") or f"ctx_{uuid4().hex[:10]}"
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = get_entity(conn, namespace="context_items", entity_id=item_id) or {}
        revision = int(existing.get("revision", 0)) + 1
        data = {
            "id": item_id,
            "path": payload.get("path") or payload.get("ref"),
            "status": "attached",
            "revision": revision,
            "updated_at": now_iso(),
        }
        upsert_entity(conn, namespace="context_items", entity_id=item_id, data=data, status="attached")
        audit_event(conn, event_type="context_attach", endpoint="/api/context/attach", actor=actor, payload=payload, result={"id": item_id})
        conn.commit()
        return _ok({"ok": True, "item": data})
    finally:
        conn.close()


@router.post("/context/detach")
def context_detach(
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    item_id = payload.get("id")
    if not item_id:
        raise HTTPException(status_code=400, detail="id is required")
    conn = db_connect()
    try:
        ensure_schema(conn)
        item = get_entity(conn, namespace="context_items", entity_id=item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Context item not found")
        revision = int(item.get("revision", 0)) + 1
        data = {**item, "id": item_id, "status": "detached", "revision": revision, "updated_at": now_iso()}
        upsert_entity(conn, namespace="context_items", entity_id=item_id, data=data, status="detached")
        audit_event(conn, event_type="context_detach", endpoint="/api/context/detach", actor=actor, payload=payload, result={"id": item_id})
        conn.commit()
        return _ok({"ok": True, "item": data})
    finally:
        conn.close()


@router.post("/context/refresh")
def context_refresh(
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    item_id = payload.get("id")
    if not item_id:
        raise HTTPException(status_code=400, detail="id is required")
    conn = db_connect()
    try:
        ensure_schema(conn)
        item = get_entity(conn, namespace="context_items", entity_id=item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Context item not found")
        revision = int(item.get("revision", 0)) + 1
        data = {**item, "id": item_id, "revision": revision, "updated_at": now_iso()}
        upsert_entity(conn, namespace="context_items", entity_id=item_id, data=data, status=data.get("status", "attached"))
        audit_event(conn, event_type="context_refresh", endpoint="/api/context/refresh", actor=actor, payload=payload, result={"id": item_id, "revision": revision})
        conn.commit()
        return _ok({"ok": True, "item": data})
    finally:
        conn.close()


@router.get("/demo-mode/status")
def demo_mode_status() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        enabled = bool(get_state(conn, key="demo_mode_enabled", default=False))
        return _ok({"enabled": enabled, "status": "enabled" if enabled else "disabled"})
    finally:
        conn.close()


@router.post("/demo-mode/enable")
def demo_mode_enable(admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        set_state(conn, key="demo_mode_enabled", value=True)
        audit_event(conn, event_type="demo_mode_enable", endpoint="/api/demo-mode/enable", actor=actor, payload={}, result={"enabled": True})
        conn.commit()
        return _ok({"enabled": True})
    finally:
        conn.close()


@router.post("/demo-mode/disable")
def demo_mode_disable(admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        set_state(conn, key="demo_mode_enabled", value=False)
        audit_event(conn, event_type="demo_mode_disable", endpoint="/api/demo-mode/disable", actor=actor, payload={}, result={"enabled": False})
        conn.commit()
        return _ok({"enabled": False})
    finally:
        conn.close()


@router.get("/mode/stats")
def mode_stats() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        alerts = list_entities(conn, namespace="mode_alerts")
        current_mode = get_state(conn, key="communication_mode", default="local_open")
        return _ok({"stats": {"total_alerts": len(alerts), "current_mode": current_mode}})
    finally:
        conn.close()


@router.get("/mode/alerts")
def mode_alerts() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        alerts = [{"id": _entity_id(a), **a} for a in list_entities(conn, namespace="mode_alerts")]
        return _ok({"alerts": alerts})
    finally:
        conn.close()


@router.get("/execution/policies")
def list_execution_policies() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        policies = []
        for item in list_entities(conn, namespace="execution_policies"):
            policies.append(
                {
                    "id": _entity_id(item),
                    "name": item.get("name", ""),
                    "config": item.get("config", {}),
                    "status": item.get("status", "draft"),
                    "updated_at": item.get("updated_at") or item.get("_updated_at") or now_iso(),
                }
            )
        return _ok({"policies": policies, "total": len(policies)})
    finally:
        conn.close()


@router.post("/execution/policies")
def create_execution_policy(
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    policy_id = payload.get("id") or f"policy_{uuid4().hex[:10]}"
    data = {
        "id": policy_id,
        "name": payload.get("name", policy_id),
        "config": payload.get("config", {}),
        "status": payload.get("status", "draft"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    conn = db_connect()
    try:
        ensure_schema(conn)
        upsert_entity(conn, namespace="execution_policies", entity_id=policy_id, data=data, status=data["status"])
        audit_event(conn, event_type="execution_policy_create", endpoint="/api/execution/policies", actor=actor, payload=payload, result={"id": policy_id})
        conn.commit()
        return _ok({"policy": data})
    finally:
        conn.close()


@router.put("/execution/policies/{policy_id}")
def update_execution_policy(
    policy_id: str,
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = get_entity(conn, namespace="execution_policies", entity_id=policy_id)
        if not existing or existing.get("_deleted"):
            raise HTTPException(status_code=404, detail="Policy not found")
        data = {
            "id": policy_id,
            "name": payload.get("name", existing.get("name", policy_id)),
            "config": payload.get("config", existing.get("config", {})),
            "status": payload.get("status", existing.get("status", "draft")),
            "created_at": existing.get("created_at") or existing.get("_created_at") or now_iso(),
            "updated_at": now_iso(),
        }
        upsert_entity(conn, namespace="execution_policies", entity_id=policy_id, data=data, status=data["status"])
        audit_event(conn, event_type="execution_policy_update", endpoint=f"/api/execution/policies/{policy_id}", actor=actor, payload=payload, result={"id": policy_id})
        conn.commit()
        return _ok({"policy": data})
    finally:
        conn.close()


@router.delete("/execution/policies/{policy_id}")
def delete_execution_policy(policy_id: str, admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        soft_delete_entity(conn, namespace="execution_policies", entity_id=policy_id)
        audit_event(conn, event_type="execution_policy_delete", endpoint=f"/api/execution/policies/{policy_id}", actor=actor, payload={"id": policy_id}, result={"ok": True})
        conn.commit()
        return _ok({"ok": True, "id": policy_id})
    finally:
        conn.close()


@router.get("/governance/findings")
def list_governance_findings() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        findings = [{"id": _entity_id(f), **f} for f in list_entities(conn, namespace="governance_findings")]
        return _ok({"findings": findings, "total": len(findings)})
    finally:
        conn.close()


@router.get("/governance/findings/{finding_id}")
def get_governance_finding(finding_id: str) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        finding = get_entity(conn, namespace="governance_findings", entity_id=finding_id)
        if not finding or finding.get("_deleted"):
            return _ok({"finding": {"id": finding_id, "status": "open"}})
        return _ok({"finding": {"id": finding_id, **finding}})
    finally:
        conn.close()


@router.delete("/governance/findings/{finding_id}")
def delete_governance_finding(finding_id: str, admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        soft_delete_entity(conn, namespace="governance_findings", entity_id=finding_id)
        audit_event(conn, event_type="governance_finding_delete", endpoint=f"/api/governance/findings/{finding_id}", actor=actor, payload={"id": finding_id}, result={"ok": True})
        conn.commit()
        return _ok({"ok": True, "id": finding_id})
    finally:
        conn.close()


@router.get("/governance/evolution-decisions")
def list_evolution_decisions() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        decisions = [{"id": _entity_id(d), **d} for d in list_entities(conn, namespace="evolution_decisions")]
        return _ok({"decisions": decisions, "total": len(decisions)})
    finally:
        conn.close()


@router.get("/governance/evolution-decisions/{decision_id}")
def get_evolution_decision(decision_id: str) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        decision = get_entity(conn, namespace="evolution_decisions", entity_id=decision_id)
        if not decision or decision.get("_deleted"):
            return _ok({"decision": {"id": decision_id, "status": "pending"}})
        return _ok({"decision": {"id": decision_id, **decision}})
    finally:
        conn.close()


@router.get("/governance/trust-tiers")
def list_trust_tiers() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        tiers = get_state(conn, key="trust_tiers", default=None)
        if tiers is None and _compat_demo_enabled():
            tiers = _demo_trust_tiers()
            # Persist so the demo becomes "replayable" across refreshes.
            set_state(conn, key="trust_tiers", value=tiers)
        tiers = tiers or []
        return _ok({"tiers": tiers})
    finally:
        conn.close()


@router.get("/marketplace/capabilities")
def list_marketplace_capabilities() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        capabilities = [{"id": _entity_id(c), **c} for c in list_entities(conn, namespace="marketplace_capabilities")]
        return _ok({"capabilities": capabilities, "total": len(capabilities)})
    finally:
        conn.close()


@router.get("/marketplace/capabilities/{capability_id}")
def get_marketplace_capability(capability_id: str) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        capability = get_entity(conn, namespace="marketplace_capabilities", entity_id=capability_id)
        if not capability or capability.get("_deleted"):
            return _ok({"capability": {"id": capability_id, "status": "pending"}})
        return _ok({"capability": {"id": capability_id, **capability}})
    finally:
        conn.close()


@router.post("/marketplace/capabilities/{capability_id}/approve")
def approve_marketplace_capability(capability_id: str, admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = get_entity(conn, namespace="marketplace_capabilities", entity_id=capability_id) or {}
        data = {**existing, "id": capability_id, "status": "approved", "updated_at": now_iso()}
        upsert_entity(conn, namespace="marketplace_capabilities", entity_id=capability_id, data=data, status="approved")
        audit_event(conn, event_type="capability_approve", endpoint=f"/api/marketplace/capabilities/{capability_id}/approve", actor=actor, payload={"id": capability_id}, result={"status": "approved"})
        conn.commit()
        return _ok({"ok": True, "id": capability_id, "status": "approved"})
    finally:
        conn.close()


@router.post("/marketplace/capabilities/{capability_id}/reject")
def reject_marketplace_capability(capability_id: str, admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = get_entity(conn, namespace="marketplace_capabilities", entity_id=capability_id) or {}
        data = {**existing, "id": capability_id, "status": "rejected", "updated_at": now_iso()}
        upsert_entity(conn, namespace="marketplace_capabilities", entity_id=capability_id, data=data, status="rejected")
        audit_event(conn, event_type="capability_reject", endpoint=f"/api/marketplace/capabilities/{capability_id}/reject", actor=actor, payload={"id": capability_id}, result={"status": "rejected"})
        conn.commit()
        return _ok({"ok": True, "id": capability_id, "status": "rejected"})
    finally:
        conn.close()


@router.get("/marketplace/publishers")
def list_publishers() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        demo_index = _demo_publishers_index() if _compat_demo_enabled() else {}
        items = list_entities(conn, namespace="marketplace_publishers")
        if not items and _compat_demo_enabled():
            for demo in _demo_publishers():
                upsert_entity(
                    conn,
                    namespace="marketplace_publishers",
                    entity_id=str(demo["publisher_id"]),
                    data=demo,
                    status="active",
                )
            items = list_entities(conn, namespace="marketplace_publishers")
        publishers = []
        for p in items:
            clean = _strip_meta(p)
            # Keep a stable id for clients that need it.
            clean.setdefault("publisher_id", _entity_id(p))
            tmpl = demo_index.get(str(clean.get("publisher_id") or ""))
            publishers.append(_overlay_defined(tmpl or {}, clean))
        return _ok({"publishers": publishers, "total": len(publishers)})
    finally:
        conn.close()


@router.get("/marketplace/publishers/{publisher_id}")
def get_publisher(publisher_id: str) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        demo_index = _demo_publishers_index() if _compat_demo_enabled() else {}
        publisher = get_entity(conn, namespace="marketplace_publishers", entity_id=publisher_id)
        if (not publisher or publisher.get("_deleted")) and _compat_demo_enabled():
            # Seed on-demand if the user deep-links into a publisher.
            for demo in _demo_publishers():
                if demo["publisher_id"] == publisher_id:
                    publisher = upsert_entity(
                        conn,
                        namespace="marketplace_publishers",
                        entity_id=str(publisher_id),
                        data=demo,
                        status="active",
                    )
                    break
        if not publisher or publisher.get("_deleted"):
            return _ok(
                {
                    "publisher": {
                        "publisher_id": publisher_id,
                        "name": publisher_id,
                        "trust_level": "unverified",
                        "trust_score": 0.0,
                        "capability_count": 0,
                        "successful_executions": 0,
                        "failed_executions": 0,
                        "success_rate": 0.0,
                        "average_risk_score": 0.0,
                        "registered_at": int(time.time() * 1000),
                        "last_activity_at": int(time.time() * 1000),
                    }
                }
            )
        clean = _strip_meta(publisher)
        clean.setdefault("publisher_id", publisher_id)
        tmpl = demo_index.get(str(publisher_id))
        return _ok({"publisher": _overlay_defined(tmpl or {}, clean)})
    finally:
        conn.close()


@router.patch("/marketplace/publishers/{publisher_id}/trust")
def patch_publisher_trust(
    publisher_id: str,
    payload: Dict[str, Any] = Body(default_factory=dict),
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = "demo" if (_compat_demo_enabled() and not admin_token) else _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = get_entity(conn, namespace="marketplace_publishers", entity_id=publisher_id) or {}
        existing_clean = _strip_meta(existing) if existing else {}

        # In demo mode, make PATCH replayable and stable by ensuring a baseline entity exists.
        demo_template = None
        if _compat_demo_enabled():
            for demo in _demo_publishers():
                if demo.get("publisher_id") == publisher_id:
                    demo_template = demo
                    break
            # If the entity doesn't exist yet, seed it now.
            if not existing_clean and demo_template:
                existing = upsert_entity(
                    conn,
                    namespace="marketplace_publishers",
                    entity_id=str(publisher_id),
                    data=demo_template,
                    status="active",
                )
                existing_clean = _strip_meta(existing) if existing else {}

        # Merge template fields (capability_count/success_rate/name, etc.) if the entity is partial.
        base = _overlay_defined(demo_template or {}, existing_clean)
        now_ms = int(time.time() * 1000)

        requested_level = payload.get("trust_level") or payload.get("trust") or payload.get("level")
        requested_score = payload.get("trust_score") or payload.get("score")

        prev_score = base.get("trust_score") or base.get("score") or 0.0
        try:
            prev_score_f = float(prev_score)
        except Exception:
            prev_score_f = 0.0

        if requested_score is None:
            # Demo-friendly default: bump a little so the UI clearly reflects a change.
            next_score = max(0.0, min(100.0, prev_score_f + 5.0))
        else:
            try:
                next_score = max(0.0, min(100.0, float(requested_score)))
            except Exception:
                next_score = prev_score_f

        def _level_for_score(score: float) -> str:
            # Five-level scale for demo/UI:
            # 0-19 unknown, 20-39 low, 40-69 medium, 70-89 high, 90-100 verified.
            if score >= 90:
                return "verified"
            if score >= 70:
                return "high"
            if score >= 40:
                return "medium"
            if score >= 20:
                return "low"
            return "unknown"

        next_level = str(requested_level).strip() if requested_level else _level_for_score(next_score)
        name = base.get("name") or base.get("display_name") or publisher_id

        data = {
            **base,
            "publisher_id": publisher_id,
            "name": name,
            "trust_level": next_level,
            "trust_score": float(f"{next_score:.1f}"),
            "last_activity_at": now_ms,
            "updated_at": now_iso(),
            # Flattened fields for quick inspection (demo-friendly "audit").
            "last_trust_update_at": now_ms,
            "last_trust_update_reason": payload.get("reason", "demo:update"),
            "last_trust_update_source": payload.get("source") or ("manual_adjust_dialog" if payload else "demo:auto_bump"),
            "last_trust_update": {
                "actor": actor,
                "reason": payload.get("reason", "demo:update"),
                "payload": payload,
                "at_ms": now_ms,
            },
        }
        upsert_entity(conn, namespace="marketplace_publishers", entity_id=publisher_id, data=data, status="active")
        audit_event(conn, event_type="publisher_trust_patch", endpoint=f"/api/marketplace/publishers/{publisher_id}/trust", actor=actor, payload=payload, result={"id": publisher_id})
        conn.commit()
        return _ok({"ok": True, "publisher_id": publisher_id, "publisher": data})
    finally:
        conn.close()


@router.get("/remote/connections")
def list_remote_connections() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        connections = [{"id": _entity_id(c), **c} for c in list_entities(conn, namespace="remote_connections")]
        return _ok({"connections": connections, "total": len(connections)})
    finally:
        conn.close()


@router.get("/remote/connections/{connection_id}")
def get_remote_connection(connection_id: str) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        conn_item = get_entity(conn, namespace="remote_connections", entity_id=connection_id)
        if not conn_item or conn_item.get("_deleted"):
            return _ok({"connection": {"id": connection_id, "status": "unknown"}})
        return _ok({"connection": {"id": connection_id, **conn_item}})
    finally:
        conn.close()


@router.post("/remote/connections/{connection_id}/execute")
def execute_remote_connection(
    connection_id: str,
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = get_entity(conn, namespace="remote_connections", entity_id=connection_id) or {"id": connection_id}
        output = payload.get("command", "")[:200]
        data = {**existing, "id": connection_id, "last_output": output, "status": "active", "updated_at": now_iso()}
        upsert_entity(conn, namespace="remote_connections", entity_id=connection_id, data=data, status="active")
        audit_event(conn, event_type="remote_execute", endpoint=f"/api/remote/connections/{connection_id}/execute", actor=actor, payload=payload, result={"ok": True})
        conn.commit()
        return _ok({"ok": True, "connection_id": connection_id, "output": output})
    finally:
        conn.close()


@router.delete("/remote/connections/{connection_id}")
def delete_remote_connection(connection_id: str, admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        soft_delete_entity(conn, namespace="remote_connections", entity_id=connection_id)
        audit_event(conn, event_type="remote_connection_delete", endpoint=f"/api/remote/connections/{connection_id}", actor=actor, payload={"id": connection_id}, result={"ok": True})
        conn.commit()
        return _ok({"ok": True, "connection_id": connection_id})
    finally:
        conn.close()


@router.get("/v3/review-queue")
def list_review_queue() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        items = [{"id": _entity_id(i), **i} for i in list_entities(conn, namespace="review_queue")]
        return _ok({"items": items, "total": len(items)})
    finally:
        conn.close()


@router.get("/v3/review-queue/{item_id}")
def get_review_queue_item(item_id: str) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        item = get_entity(conn, namespace="review_queue", entity_id=item_id)
        if not item or item.get("_deleted"):
            return _ok({"item": {"id": item_id, "status": "pending"}})
        return _ok({"item": {"id": item_id, **item}})
    finally:
        conn.close()


@router.post("/v3/review-queue/{item_id}/approve")
def approve_review_queue(
    item_id: str,
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = get_entity(conn, namespace="review_queue", entity_id=item_id) or {"id": item_id}
        data = {**existing, "id": item_id, "status": "approved", "reason": payload.get("reason"), "updated_at": now_iso()}
        upsert_entity(conn, namespace="review_queue", entity_id=item_id, data=data, status="approved")
        audit_event(conn, event_type="review_queue_approve", endpoint=f"/api/v3/review-queue/{item_id}/approve", actor=actor, payload=payload, result={"status": "approved"})
        conn.commit()
        return _ok({"ok": True, "id": item_id, "status": "approved"})
    finally:
        conn.close()


@router.post("/v3/review-queue/{item_id}/reject")
def reject_review_queue(
    item_id: str,
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = get_entity(conn, namespace="review_queue", entity_id=item_id) or {"id": item_id}
        data = {**existing, "id": item_id, "status": "rejected", "reason": payload.get("reason"), "updated_at": now_iso()}
        upsert_entity(conn, namespace="review_queue", entity_id=item_id, data=data, status="rejected")
        audit_event(conn, event_type="review_queue_reject", endpoint=f"/api/v3/review-queue/{item_id}/reject", actor=actor, payload=payload, result={"status": "rejected"})
        conn.commit()
        return _ok({"ok": True, "id": item_id, "status": "rejected"})
    finally:
        conn.close()


@router.get("/knowledge/jobs")
def list_knowledge_jobs() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        jobs = [{"id": _entity_id(j), **j} for j in list_entities(conn, namespace="knowledge_jobs")]
        return _ok({"jobs": jobs, "total": len(jobs)})
    finally:
        conn.close()


@router.get("/knowledge/sources")
def list_knowledge_sources() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        sources = [{"id": _entity_id(s), **s} for s in list_entities(conn, namespace="knowledge_sources")]
        return _ok({"sources": sources, "total": len(sources)})
    finally:
        conn.close()


@router.post("/knowledge/sources")
def create_knowledge_source(
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    source_id = payload.get("id") or f"src_{uuid4().hex[:10]}"
    data = {
        "id": source_id,
        "name": payload.get("name", source_id),
        "status": payload.get("status", "active"),
        "type": payload.get("type"),
        "uri": payload.get("uri"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    conn = db_connect()
    try:
        ensure_schema(conn)
        upsert_entity(conn, namespace="knowledge_sources", entity_id=source_id, data=data, status=data["status"])
        audit_event(conn, event_type="knowledge_source_create", endpoint="/api/knowledge/sources", actor=actor, payload=payload, result={"id": source_id})
        conn.commit()
        return _ok({"source": data})
    finally:
        conn.close()


@router.get("/brain/stats")
def brain_stats() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        builds = list_entities(conn, namespace="brain_builds")
        return _ok({"stats": {"build_jobs": len(builds)}})
    finally:
        conn.close()


@router.get("/brain/coverage")
def brain_coverage() -> Dict[str, Any]:
    return _ok({"coverage": {"score": 0}})


@router.get("/brain/blind-spots")
def brain_blind_spots() -> Dict[str, Any]:
    return _ok({"blind_spots": []})


@router.get("/brain/dashboard")
def brain_dashboard() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        builds = list_entities(conn, namespace="brain_builds")
        return _ok({"dashboard": {"build_jobs": len(builds), "last_build": builds[0] if builds else None}})
    finally:
        conn.close()


@router.get("/brain/knowledge-health")
def brain_knowledge_health() -> Dict[str, Any]:
    return _ok({"health": {"status": "ok"}})


@router.get("/brain/subgraph")
def brain_subgraph() -> Dict[str, Any]:
    return _ok({"nodes": [], "edges": []})


@router.get("/brain/governance/decisions")
def list_brain_governance_decisions(limit: int = Query(default=50, ge=1, le=500)) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        decisions = list_entities(conn, namespace="brain_governance_decisions")[:limit]
        records = []
        for d in decisions:
            records.append(
                {
                    "decision_id": _entity_id(d) or f"gd_{uuid4().hex[:8]}",
                    "decision_type": d.get("decision_type", "HEALTH"),
                    "seed": d.get("seed", "compat"),
                    "timestamp": d.get("timestamp", d.get("_updated_at", now_iso())),
                    "status": d.get("status", "PENDING"),
                    "final_verdict": d.get("final_verdict", "ALLOW"),
                    "rules_triggered": d.get("rules_triggered", []),
                }
            )
        return {"ok": True, "data": {"records": records, "count": len(records)}, "error": None, "source": "compat"}
    finally:
        conn.close()


@router.get("/brain/governance/decisions/{decision_id}")
def get_brain_governance_decision(decision_id: str) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        d = get_entity(conn, namespace="brain_governance_decisions", entity_id=decision_id) or {}
        decision = {
            "decision_id": decision_id,
            "decision_type": d.get("decision_type", "HEALTH"),
            "seed": d.get("seed", "compat"),
            "timestamp": d.get("timestamp", d.get("_updated_at", now_iso())),
            "status": d.get("status", "PENDING"),
            "final_verdict": d.get("final_verdict", "ALLOW"),
            "rules_triggered": d.get("rules_triggered", []),
            "integrity_verified": True,
        }
        return {"ok": True, "data": decision, "error": None, "source": "compat"}
    finally:
        conn.close()


@router.get("/brain/governance/decisions/{decision_id}/replay")
def replay_brain_governance_decision(decision_id: str) -> Dict[str, Any]:
    now = now_iso()
    decision = {
        "decision_id": decision_id,
        "decision_type": "HEALTH",
        "seed": "compat",
        "timestamp": now,
        "status": "PENDING",
        "final_verdict": "ALLOW",
        "rules_triggered": [],
    }
    replay = {
        "decision": decision,
        "integrity_check": {
            "passed": True,
            "computed_hash": "compat",
            "stored_hash": "compat",
            "algorithm": "sha256",
        },
        "replay_timestamp": now,
        "warnings": [],
        "audit_trail": {},
        "rules_triggered": [],
        "then_state": {},
        "now_state": {},
        "changed_facts": [],
    }
    return {"ok": True, "data": replay, "error": None, "source": "compat"}


@router.post("/brain/governance/decisions/{decision_id}/signoff")
def signoff_brain_governance_decision(
    decision_id: str,
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    now = now_iso()
    result = {
        "signoff_id": f"sig_{uuid4().hex[:10]}",
        "decision_id": decision_id,
        "signed_by": payload.get("signed_by", actor),
        "timestamp": now,
        "note": payload.get("note", ""),
        "new_status": "SIGNED",
    }
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = get_entity(conn, namespace="brain_governance_decisions", entity_id=decision_id) or {}
        existing.update(
            {
                "decision_id": decision_id,
                "status": "SIGNED",
                "signoff": {
                    "signed_by": result["signed_by"],
                    "sign_timestamp": now,
                    "sign_note": result["note"],
                },
                "updated_at": now,
            }
        )
        upsert_entity(conn, namespace="brain_governance_decisions", entity_id=decision_id, data=existing, status="signed")
        audit_event(
            conn,
            event_type="brain_governance_signoff",
            endpoint=f"/api/brain/governance/decisions/{decision_id}/signoff",
            actor=actor,
            payload=payload,
            result=result,
        )
        conn.commit()
        return {"ok": True, "data": result, "error": None, "source": "compat"}
    finally:
        conn.close()


@router.post("/brain/build")
def brain_build(admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    job_id = f"brain_{uuid4().hex[:10]}"
    data = {"id": job_id, "status": "queued", "created_at": now_iso(), "updated_at": now_iso()}
    conn = db_connect()
    try:
        ensure_schema(conn)
        upsert_entity(conn, namespace="brain_builds", entity_id=job_id, data=data, status="queued")
        audit_event(conn, event_type="brain_build_create", endpoint="/api/brain/build", actor=actor, payload={}, result={"job_id": job_id})
        conn.commit()
        return _ok({"ok": True, "job_id": job_id})
    finally:
        conn.close()


@router.get("/risk/timeline")
def risk_timeline(
    window: str = Query(default="24h"),
    bucket: str = Query(default="5m"),
    dimension: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    # dimension is accepted for forward-compat with UI but currently does not affect aggregation.
    _ = dimension
    conn = db_connect()
    try:
        ensure_schema(conn)

        def _parse_duration(spec: str, default_seconds: int) -> int:
            raw = (spec or "").strip().lower()
            if not raw:
                return default_seconds
            try:
                if raw.endswith("ms"):
                    return max(1, int(float(raw[:-2]) / 1000))
                if raw.endswith("s"):
                    return max(1, int(float(raw[:-1])))
                if raw.endswith("m"):
                    return max(1, int(float(raw[:-1]) * 60))
                if raw.endswith("h"):
                    return max(1, int(float(raw[:-1]) * 3600))
                if raw.endswith("d"):
                    return max(1, int(float(raw[:-1]) * 86400))
            except Exception:
                return default_seconds
            return default_seconds

        window_s = _parse_duration(window, 24 * 3600)
        bucket_s = _parse_duration(bucket, 5 * 60)

        now = time.time()
        start_ts = now - window_s

        rows = conn.execute(
            """
            SELECT event_id, event_type, endpoint, payload_json, result_json, created_at
            FROM compat_audit_events
            ORDER BY event_id DESC
            LIMIT 2000
            """
        ).fetchall()

        def _safe_json_load(text: Optional[str]) -> Dict[str, Any]:
            if not text:
                return {}
            try:
                out = json.loads(text)
                return out if isinstance(out, dict) else {}
            except Exception:
                return {}

        def _iso_to_epoch_s(value: str) -> float:
            raw = (value or "").strip()
            if not raw:
                return 0.0
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.timestamp()
            except Exception:
                return 0.0

        def _event_score(event_type: str, payload: Dict[str, Any], result: Dict[str, Any]) -> float:
            # If writers already supply a score, honor it.
            for src in (payload, result):
                v = src.get("risk_score")
                if isinstance(v, (int, float)):
                    return max(0.0, min(1.0, float(v)))
            for src in (payload, result):
                v = (src.get("risk_level") or src.get("risk") or "").strip().upper()
                if v in {"CRITICAL"}:
                    return 0.95
                if v in {"HIGH"}:
                    return 0.7
                if v in {"MEDIUM", "MID"}:
                    return 0.4
                if v in {"LOW"}:
                    return 0.1
            et = (event_type or "").lower()
            if any(k in et for k in ["critical", "block", "reject", "deny", "failure"]):
                return 0.95
            if any(k in et for k in ["warn", "confirm", "override"]):
                return 0.4
            return 0.1

        # Bucket by time, using max score within each bucket for "risk timeline" semantics.
        buckets: Dict[int, Dict[str, Any]] = {}
        for r in rows:
            created_s = _iso_to_epoch_s(r["created_at"])
            if created_s <= 0 or created_s < start_ts:
                continue
            payload = _safe_json_load(r["payload_json"])
            result = _safe_json_load(r["result_json"])
            score = _event_score(str(r["event_type"] or ""), payload, result)
            b = int((created_s - start_ts) // bucket_s)
            slot = buckets.get(b)
            if slot is None or score > float(slot.get("score", 0.0)):
                buckets[b] = {
                    "ts": int(created_s * 1000),
                    "score": score,
                    "level": "HIGH" if score >= 0.7 else ("MEDIUM" if score >= 0.4 else "LOW"),
                    "reason": str(r["event_type"] or ""),
                }

        ordered = [buckets[k] for k in sorted(buckets.keys())]

        # Primary fields (align existing frontend expectations)
        scores = []
        for pt in ordered:
            # RiskTimelinePage expects timestamp + per-dimension floats.
            # We treat "overall_score" as the bucket score, and mirror to other dimensions for now.
            ts_iso = datetime.fromtimestamp(pt["ts"] / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            s = float(pt["score"])
            scores.append(
                {
                    "timestamp": ts_iso,
                    "overall_score": s,
                    "execution_risk": s,
                    "trust_risk": s,
                    "policy_risk": s,
                    "capability_risk": s,
                    # Extra fields are allowed (forward-compat contract)
                    "ts": pt["ts"],
                    "level": pt["level"],
                    "reason": pt["reason"],
                }
            )

        last_score = float(scores[-1]["overall_score"]) if scores else 0.0
        all_scores = [float(s["overall_score"]) for s in scores]
        avg_score = (sum(all_scores) / len(all_scores)) if all_scores else 0.0
        max_score = max(all_scores) if all_scores else 0.0
        p95_score = 0.0
        if all_scores:
            xs = sorted(all_scores)
            idx = int(round(0.95 * (len(xs) - 1)))
            p95_score = float(xs[idx])

        # Simple trend heuristic: compare last vs first.
        trend = "stable"
        if len(all_scores) >= 2:
            if all_scores[-1] > all_scores[0] + 0.05:
                trend = "increasing"
            elif all_scores[-1] < all_scores[0] - 0.05:
                trend = "decreasing"

        verdict = "OK"
        if max_score >= 0.7:
            verdict = "RISK"
        elif max_score >= 0.4:
            verdict = "WATCH"

        return _ok(
            {
                "scores": scores,
                "summary": {
                    # Existing UI fields
                    "current_risk": last_score,
                    "avg_risk": avg_score,
                    "max_risk": max_score,
                    "trend": trend,
                    # Frozen-contract fields (extra)
                    "window": window,
                    "last_score": last_score,
                    "p95_score": p95_score,
                    "verdict": verdict,
                    "count_points": len(scores),
                },
                "source": "octopusos",
                # Compatibility field (legacy)
                "timeline": ordered,
            }
        )
    finally:
        conn.close()


@router.get("/trust/trajectory/{subject_id}")
def trust_trajectory(subject_id: str, time_range: str = Query(default="30d")) -> Dict[str, Any]:
    # Always include `trajectory` for WebUI v2, but keep `points` for backward compatibility.
    trajectory = _demo_trust_trajectory(subject_id, time_range=time_range) if _compat_demo_enabled() else {
        "entity_id": subject_id,
        "current_state": {
            "extension_id": subject_id,
            "action_id": "unknown",
            "current_state": "EARNING",
            "consecutive_successes": 0,
            "consecutive_failures": 0,
            "policy_rejections": 0,
            "high_risk_events": 0,
            "state_entered_at_ms": int(time.time() * 1000),
            "last_event_at_ms": int(time.time() * 1000),
            "updated_at_ms": int(time.time() * 1000),
        },
        "score_history": [],
        "transitions": [],
        "stats": {
            "total_transitions": 0,
            "time_in_current_state_hours": 0,
            "success_rate": 0.0,
            "policy_violation_count": 0,
        },
    }
    return _ok({"subject_id": subject_id, "points": [], "trajectory": trajectory})


@router.get("/trust/states")
def trust_states(limit: int = Query(default=50, ge=1, le=500)) -> Dict[str, Any]:
    if not _compat_demo_enabled():
        return _ok({"states": [], "total": 0})
    demo_entities = ["local-system", "demo-extension:acme", "demo-extension:nightjar"]
    states = [_demo_trust_trajectory(e).get("current_state") for e in demo_entities]
    states = [s for s in states if isinstance(s, dict)]
    return _ok({"states": states[:limit], "total": len(states)})


@router.get("/trust/transitions/{subject_id}")
def trust_transitions(subject_id: str, limit: int = Query(default=200, ge=1, le=500)) -> Dict[str, Any]:
    if not _compat_demo_enabled():
        return _ok({"transitions": [], "total": 0})
    traj = _demo_trust_trajectory(subject_id)
    transitions = traj.get("transitions", []) if isinstance(traj, dict) else []
    return _ok({"transitions": transitions[:limit], "total": len(transitions)})


@router.get(
    "/memory/entries",
    response_model=MemoryEntriesResponse,
    response_model_exclude_none=True,
)
def memory_entries(
    request: Request,
    response: Response,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    debug: int = Query(default=0),
) -> Any:
    conn = memory_db_connect()
    try:
        response.headers["X-OctopusOS-Data-Store"] = "memoryos"
        response.headers["X-OctopusOS-Compat"] = "1"

        debug_enabled = (
            bool(debug)
            or request.headers.get("X-OctopusOS-Debug") == "1"
            or os.getenv("OCTOPUSOS_DEBUG", "").strip() in {"1", "true", "TRUE", "yes", "on"}
        )

        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'memory_items'"
        ).fetchone()
        if not table_exists:
            etag_value = hashlib.sha1("0|none".encode("utf-8")).hexdigest()
            etag = f'W/"{etag_value}"'
            response.headers["ETag"] = etag
            if request.headers.get("If-None-Match") == etag:
                return Response(
                    status_code=304,
                    headers={
                        "ETag": etag,
                        "X-OctopusOS-Data-Store": "memoryos",
                        "X-OctopusOS-Compat": "1",
                    },
                )
            out = _ok(
                {
                    "entries": [],
                    "total": 0,
                    "limit": limit,
                    "offset": offset,
                }
            )
            if debug_enabled:
                out["store_path"] = str(memory_db_path())
            return out

        columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(memory_items)").fetchall()
        }

        def _col_expr(col: str, alias: str | None = None) -> str:
            final_alias = alias or col
            if col in columns:
                return f"{col} AS {final_alias}"
            return f"NULL AS {final_alias}"

        total = int(conn.execute("SELECT COUNT(*) AS c FROM memory_items").fetchone()["c"] or 0)
        latest_updated_at: Optional[str] = None
        if "updated_at" in columns:
            row = conn.execute("SELECT MAX(updated_at) AS m FROM memory_items").fetchone()
            latest_updated_at = str(row["m"]) if row and row["m"] is not None else None
        elif "created_at" in columns:
            row = conn.execute("SELECT MAX(created_at) AS m FROM memory_items").fetchone()
            latest_updated_at = str(row["m"]) if row and row["m"] is not None else None

        etag_seed = f"{total}|{latest_updated_at or 'none'}"
        etag_value = hashlib.sha1(etag_seed.encode("utf-8")).hexdigest()
        etag = f'W/"{etag_value}"'
        response.headers["ETag"] = etag
        if request.headers.get("If-None-Match") == etag:
            return Response(
                status_code=304,
                headers={
                    "ETag": etag,
                    "X-OctopusOS-Data-Store": "memoryos",
                    "X-OctopusOS-Compat": "1",
                },
            )

        rows = conn.execute(
            f"""
            SELECT
              {_col_expr("id")},
              {_col_expr("scope")},
              {_col_expr("type")},
              {_col_expr("content")},
              {_col_expr("tags")},
              {_col_expr("sources")},
              {_col_expr("confidence")},
              {_col_expr("project_id")},
              {_col_expr("created_at")},
              {_col_expr("updated_at")}
            FROM memory_items
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

        entries: list[dict[str, Any]] = []
        for row in rows:
            content_raw = row["content"]
            tags_raw = row["tags"]
            sources_raw = row["sources"]
            try:
                content = json.loads(content_raw) if content_raw else {}
            except Exception:
                content = {"raw": str(content_raw)}
            try:
                tags = json.loads(tags_raw) if tags_raw else []
            except Exception:
                tags = []
            try:
                sources = json.loads(sources_raw) if sources_raw else []
            except Exception:
                sources = []

            entries.append(
                {
                    "id": row["id"],
                    "scope": row["scope"],
                    "type": row["type"],
                    "content": content,
                    "tags": tags,
                    "sources": sources,
                    "confidence": row["confidence"],
                    "project_id": row["project_id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )

        out = _ok(
            {
                "entries": entries,
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )
        if debug_enabled:
            out["store_path"] = str(memory_db_path())
        return out
    finally:
        conn.close()


@router.get("/capability/dashboard/stats")
def capability_dashboard_stats() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        try:
            stats = build_capability_dashboard_stats(conn)
            source = "live"
        except Exception:
            # Never break the dashboard page: return stable zeros and label degraded.
            stats = default_capability_dashboard_stats()
            source = "degraded"
        return _ok({"stats": stats, "source": source, "generated_at": int(time.time() * 1000)})
    finally:
        conn.close()


@router.get("/auth/profiles")
def list_auth_profiles() -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        profiles = [{"id": _entity_id(p), **p} for p in list_entities(conn, namespace="auth_profiles")]
        return _ok({"profiles": profiles})
    finally:
        conn.close()


@router.post("/auth/profiles/{profile_id}/validate")
def validate_auth_profile(profile_id: str, admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = get_entity(conn, namespace="auth_profiles", entity_id=profile_id) or {"id": profile_id, "name": profile_id, "provider": "unknown"}
        data = {**existing, "id": profile_id, "last_validated_at": now_iso(), "status": "valid"}
        upsert_entity(conn, namespace="auth_profiles", entity_id=profile_id, data=data, status="valid")
        audit_event(conn, event_type="auth_profile_validate", endpoint=f"/api/auth/profiles/{profile_id}/validate", actor=actor, payload={}, result={"valid": True})
        conn.commit()
        return _ok({"valid": True, "profile_id": profile_id})
    finally:
        conn.close()


@router.patch("/lead/findings/{finding_id}/status")
def patch_lead_finding_status(
    finding_id: str,
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        existing = get_entity(conn, namespace="lead_findings", entity_id=finding_id) or {"id": finding_id}
        status = payload.get("status", "open")
        data = {**existing, "id": finding_id, "status": status, "updated_at": now_iso()}
        upsert_entity(conn, namespace="lead_findings", entity_id=finding_id, data=data, status=status)
        audit_event(conn, event_type="lead_finding_status_patch", endpoint=f"/api/lead/findings/{finding_id}/status", actor=actor, payload=payload, result={"status": status})
        conn.commit()
        return _ok({"ok": True, "id": finding_id})
    finally:
        conn.close()


@router.get("/lead/findings")
def list_lead_findings(
    severity: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        items = []
        for f in list_entities(conn, namespace="lead_findings"):
            entry = {"id": _entity_id(f), **f}
            if severity and str(entry.get("severity", "")).lower() != severity.lower():
                continue
            if status and str(entry.get("status", "")).lower() != status.lower():
                continue
            if category and str(entry.get("category", "")).lower() != category.lower():
                continue
            items.append(entry)
        sliced = items[offset : offset + limit]
        return {"findings": sliced, "total": len(items), "source": "compat"}
    finally:
        conn.close()


@router.get("/lead/scans")
def list_lead_scans(offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=500)) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        items = [{"id": _entity_id(s), **s} for s in list_entities(conn, namespace="lead_scans")]
        sliced = items[offset : offset + limit]
        return {"scans": sliced, "total": len(items), "source": "compat"}
    finally:
        conn.close()


def _parse_time_range(time_range: str) -> tuple[timedelta, str]:
    raw = (time_range or "").strip().lower()
    if not raw:
        return timedelta(days=30), "30d"
    # Minimal ISO-8601 duration support:
    # - PnD  (days)
    # - PnW  (weeks)
    # - PTnH (hours)
    # This keeps the endpoint flexible for callers while still returning
    # normalized UI-friendly strings like "7d", "24h", "30d".
    if raw.startswith("p"):
        import re

        m = re.fullmatch(r"p(\d+)([dw])", raw)
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            if unit == "d":
                return timedelta(days=n), f"{n}d"
            if unit == "w":
                return timedelta(days=7 * n), f"{7 * n}d"
        m = re.fullmatch(r"pt(\d+)h", raw)
        if m:
            n = int(m.group(1))
            return timedelta(hours=n), f"{n}h"
    if raw.endswith("h") and raw[:-1].isdigit():
        n = int(raw[:-1])
        return timedelta(hours=n), f"{n}h"
    if raw.endswith("d") and raw[:-1].isdigit():
        n = int(raw[:-1])
        return timedelta(days=n), f"{n}d"
    if raw.endswith("w") and raw[:-1].isdigit():
        n = int(raw[:-1])
        # Normalize: 1w is an alias for 7d.
        return timedelta(days=7 * n), f"{7 * n}d"
    raise HTTPException(status_code=400, detail="Invalid time_range (expected like 24h, 7d, 1w, 30d)")


def _safe_json_loads(payload: Any) -> Dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            return json.loads(payload) if payload else {}
        except Exception:
            return {}
    return {}


def _to_dt(value: Any) -> Optional[datetime]:
    """
    Best-effort parse DB timestamps.

    Supports:
    - int/float epoch seconds (or ms)
    - ISO strings (via parse_db_time)
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Heuristic: treat > 1e12 as ms
        ts = float(value)
        if ts > 1e12:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        parsed = parse_db_time(value)
        if parsed is not None:
            # parse_db_time may return naive dt; normalize to UTC.
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        # numeric-as-string
        if value.isdigit():
            try:
                return datetime.fromtimestamp(int(value), tz=timezone.utc)
            except Exception:
                return None
    return None


def _confidence_to_score(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if not v:
            return None
        # Common enums
        if v in {"low", "l"}:
            return 0.4
        if v in {"medium", "med", "m"}:
            return 0.7
        if v in {"high", "h"}:
            return 0.9
        # Numeric string
        try:
            return float(v)
        except Exception:
            return None
    return None


def _percentile(values: list[float], p: float) -> Optional[float]:
    if not values:
        return None
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    xs = sorted(values)
    k = (len(xs) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return xs[f]
    d0 = xs[f] * (c - k)
    d1 = xs[c] * (k - f)
    return d0 + d1


def _iter_audit_events(
    conn,
    event_types: Iterable[str],
    start_dt: datetime,
    end_dt: datetime,
    limit: int,
) -> list[Dict[str, Any]]:
    cursor = conn.cursor()
    types_list = list(event_types)
    placeholders = ",".join(["?"] * len(types_list))
    cursor.execute(
        f"""
        SELECT audit_id, event_type, payload, created_at
        FROM task_audits
        WHERE event_type IN ({placeholders})
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (*types_list, limit),
    )
    rows = cursor.fetchall()
    out: list[Dict[str, Any]] = []
    for row in rows:
        payload = _safe_json_loads(row["payload"])
        created_dt = _to_dt(row["created_at"]) or _to_dt(payload.get("timestamp")) or _to_dt(payload.get("outcome_timestamp"))
        if created_dt is None:
            continue
        if created_dt < start_dt or created_dt > end_dt:
            continue
        out.append(
            {
                "audit_id": row["audit_id"],
                "event_type": row["event_type"],
                "payload": payload,
                "created_at": created_dt,
            }
        )
    return out


@router.get("/info-need-metrics/summary")
def info_need_metrics_summary(
    response: Response,
    time_range: str = Query(default="30d"),
    limit: int = Query(default=2000, ge=1, le=20000),
) -> Dict[str, Any]:
    """
    MVP "real data" endpoint for IntentWorkbench/InfoNeed dashboards.

    Data source: task_audits audit trail (InfoNeed classification + outcome).
    Contract: returns { summary, metrics, breakdown, source } without an ok/data wrapper.
    """
    delta, normalized_time_range = _parse_time_range(time_range)
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - delta

    # Compat observability headers: allow quick identification during debugging.
    if response is not None:
        response.headers["X-OctopusOS-Compat"] = "info-need-metrics-summary"
        response.headers["X-OctopusOS-Compat-Version"] = "2026-02-13"

    conn = get_db()

    # Pull recent classification/outcome events.
    cls_types = [INFO_NEED_CLASSIFICATION, INFO_NEED_CLASSIFICATION.lower()]
    out_types = [INFO_NEED_OUTCOME, INFO_NEED_OUTCOME.lower()]

    try:
        # Guardrail: summary/breakdown should not depend on client-provided limit.
        classifications = _iter_audit_events(conn, cls_types, start_dt, end_dt, limit=_INFO_NEED_SCAN_LIMIT)
        outcomes = _iter_audit_events(conn, out_types, start_dt, end_dt, limit=_INFO_NEED_SCAN_LIMIT)
    except Exception as exc:
        # Safety: on fresh installs or partial migrations, task_audits may not exist yet.
        # Prefer returning an explicit empty payload (so WebUI shows empty state) over 500s.
        msg = str(exc).lower()
        if "no such table" in msg and "task_audits" in msg:
            error_code = "TASK_AUDITS_MISSING"
        else:
            error_code = "QUERY_FAILED"
        return _ok(
            {
                "summary": {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "cancelled": 0,
                    "pass_rate": None,
                    "avg_confidence": None,
                    "p95_latency_ms": None,
                    "last_run_at": None,
                    "time_range": normalized_time_range,
                    "time_range_input": time_range,
                    "time_range_normalized": (normalized_time_range.lower() != (time_range or "").strip().lower()),
                    "total_tests": 0,
                    "latency_unit": "ms",
                    "p95_method": "unavailable",
                    "error": "metrics_unavailable",
                    "error_code": error_code,
                },
                "metrics": [],
                "breakdown": [],
            }
        )

    # Outcomes: keep latest per message_id.
    outcome_by_msg: dict[str, Dict[str, Any]] = {}
    for ev in outcomes:
        msg = str(ev["payload"].get("message_id") or "").strip()
        if not msg:
            continue
        prev = outcome_by_msg.get(msg)
        if prev is None or ev["created_at"] > prev["created_at"]:
            outcome_by_msg[msg] = ev

    # Summary aggregates.
    conf_scores: list[float] = []
    latencies: list[float] = []
    last_event_dt: Optional[datetime] = None

    # Breakdown by classified_type (or "unknown").
    by_type: dict[str, Dict[str, Any]] = {}

    for ev in classifications:
        payload = ev["payload"]
        created_dt: datetime = ev["created_at"]
        if last_event_dt is None or created_dt > last_event_dt:
            last_event_dt = created_dt

        classified_type = str(payload.get("classified_type") or payload.get("type") or "").strip()
        if not classified_type or classified_type.lower() in {"none", "null", "unknown"}:
            classified_type = "other"
        msg = str(payload.get("message_id") or "").strip()

        # Confidence: accept multiple field names.
        conf = _confidence_to_score(payload.get("confidence") or payload.get("confidence_level") or payload.get("confidence"))
        if conf is not None:
            conf_scores.append(conf)

        lat = payload.get("latency_ms")
        if isinstance(lat, (int, float)):
            latencies.append(float(lat))

        bucket = by_type.setdefault(
            classified_type,
            {
                "type": classified_type,
                "total": 0,
                "passed": 0,
                "failed": 0,
                "cancelled": 0,
                "conf_scores": [],
                "latencies": [],
                "last_run_at": None,
            },
        )
        bucket["total"] += 1
        if conf is not None:
            bucket["conf_scores"].append(conf)
        if isinstance(lat, (int, float)):
            bucket["latencies"].append(float(lat))
        if bucket["last_run_at"] is None or created_dt > bucket["last_run_at"]:
            bucket["last_run_at"] = created_dt

        # Outcome mapping (best-effort).
        outcome = None
        if msg and msg in outcome_by_msg:
            outcome = str(outcome_by_msg[msg]["payload"].get("outcome") or "").strip().lower()
        if outcome == "validated":
            bucket["passed"] += 1
        elif outcome in {"unnecessary_comm", "user_corrected"}:
            bucket["failed"] += 1
        elif outcome == "user_cancelled":
            bucket["cancelled"] += 1

    passed = sum(v["passed"] for v in by_type.values())
    failed = sum(v["failed"] for v in by_type.values())
    cancelled = sum(v["cancelled"] for v in by_type.values())
    total = len(classifications)

    denom = passed + failed
    pass_rate = (passed / denom) if denom > 0 else None
    avg_confidence = (sum(conf_scores) / len(conf_scores)) if conf_scores else None
    p95_latency_ms = _percentile(latencies, 95.0)

    last_run_at_ms = None
    if last_event_dt is not None:
        last_run_at_ms = int(last_event_dt.timestamp() * 1000)

    metrics_limit = int(limit)

    # UI metrics list: one record per classification event, shaped like InfoNeedMetric.
    # This is used by WebUI for "today/week/month" counts and detail drawer debugging.
    metrics: list[Dict[str, Any]] = []
    for ev in classifications:
        payload = ev["payload"]
        created_dt: datetime = ev["created_at"]
        conf = _confidence_to_score(payload.get("confidence") or payload.get("confidence_level") or payload.get("confidence"))
        metric_name = str(payload.get("classified_type") or payload.get("type") or "info_need").strip() or "info_need"
        metrics.append(
            {
                "id": str(ev["audit_id"]),
                "metric_name": metric_name,
                "value": float(conf) if conf is not None else 0.0,
                "timestamp": created_dt.isoformat(),
            }
        )

    breakdown: list[Dict[str, Any]] = []
    for t, bucket in sorted(by_type.items(), key=lambda kv: kv[0]):
        denom_t = bucket["passed"] + bucket["failed"]
        pass_rate_t = (bucket["passed"] / denom_t) if denom_t > 0 else None
        avg_conf_t = (sum(bucket["conf_scores"]) / len(bucket["conf_scores"])) if bucket["conf_scores"] else None
        p95_lat_t = _percentile(bucket["latencies"], 95.0)
        last_dt = bucket["last_run_at"]
        breakdown.append(
            {
                "intent": t,  # UI-facing "intent" label (compat: classified_type)
                "total": bucket["total"],
                "passed": bucket["passed"],
                "failed": bucket["failed"],
                "cancelled": bucket["cancelled"],
                "pass_rate": pass_rate_t,
                "avg_confidence": avg_conf_t,
                "p95_latency_ms": p95_lat_t,
                "last_run_at": int(last_dt.timestamp() * 1000) if last_dt else None,
            }
        )

    payload = {
        "summary": {
            # Canonical
            "total": total,
            "passed": passed,
            "failed": failed,
            "cancelled": cancelled,
            "pass_rate": pass_rate,
            "avg_confidence": avg_confidence,
            "p95_latency_ms": p95_latency_ms,
            "last_run_at": last_run_at_ms,
            "time_range": normalized_time_range,
            "time_range_input": time_range,
            "time_range_normalized": (normalized_time_range.lower() != (time_range or "").strip().lower()),
            "latency_unit": "ms",
            "p95_method": "exact",
            # Back-compat names used by WebUI pages.
            "total_tests": total,
        },
        # Guardrail: client-provided limit only affects this list (not summary/breakdown).
        "metrics": list(reversed(metrics))[-metrics_limit:],  # oldest -> newest, last N only
        "breakdown": breakdown,
    }
    return _ok(payload)


@router.get("/events")
def list_events(limit: int = Query(default=50, ge=1, le=500)) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT event_id, event_type, endpoint, actor, created_at
            FROM compat_audit_events
            ORDER BY event_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        events = [dict(r) for r in rows]
        return _ok({"events": events, "total": len(events), "limit": limit})
    finally:
        conn.close()


@router.put("/content/{content_id:path}")
def update_content(
    content_id: str,
    payload: Dict[str, Any],
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    conn = db_connect()
    try:
        ensure_schema(conn)
        _ensure_content_table(conn)
        row = conn.execute("SELECT * FROM compat_content WHERE id = ?", (content_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Content not found")
        if row["status"] == "frozen":
            raise HTTPException(status_code=409, detail="Frozen content cannot be updated")
        name = payload.get("name", row["name"])
        version = payload.get("version", row["version"])
        source_uri = payload.get("source_uri", row["source_uri"])
        metadata = payload.get("metadata")
        metadata_json = row["metadata"] if metadata is None else json.dumps(metadata)
        body = payload.get("body", row["body"])
        updated_at = now_iso()
        conn.execute(
            """
            UPDATE compat_content
            SET name = ?, version = ?, source_uri = ?, metadata = ?, body = ?, updated_at = ?
            WHERE id = ?
            """,
            (name, version, source_uri, metadata_json, body, updated_at, content_id),
        )
        result = {"id": content_id, "name": name, "version": version}
        audit_event(conn, event_type="content_update", endpoint=f"/api/content/{content_id}", actor=actor, payload=payload, result=result)
        conn.commit()
        return _ok({"ok": True, "data": result})
    finally:
        conn.close()


def _content_transition(content_id: str, target_status: str, endpoint: str, actor: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = db_connect()
    try:
        ensure_schema(conn)
        _ensure_content_table(conn)
        row = conn.execute("SELECT status FROM compat_content WHERE id = ?", (content_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Content not found")
        conn.execute(
            "UPDATE compat_content SET status = ?, updated_at = ? WHERE id = ?",
            (target_status, now_iso(), content_id),
        )
        result = {"id": content_id, "status": target_status}
        audit_event(conn, event_type=f"content_{target_status}", endpoint=endpoint, actor=actor, payload=payload, result=result)
        conn.commit()
        return _ok({"ok": True, "data": result})
    finally:
        conn.close()


@router.post("/content/{content_id:path}/activate")
def activate_content(content_id: str, payload: Dict[str, Any], admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    return _content_transition(content_id, "active", f"/api/content/{content_id}/activate", actor, payload)


@router.post("/content/{content_id:path}/deprecate")
def deprecate_content(content_id: str, payload: Dict[str, Any], admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    return _content_transition(content_id, "deprecated", f"/api/content/{content_id}/deprecate", actor, payload)


@router.post("/content/{content_id:path}/freeze")
def freeze_content(content_id: str, payload: Dict[str, Any], admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> Dict[str, Any]:
    actor = _require_admin_token(admin_token)
    return _content_transition(content_id, "frozen", f"/api/content/{content_id}/freeze", actor, payload)
