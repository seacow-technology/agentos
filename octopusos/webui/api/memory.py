"""Memory API endpoints (timeline + proposals)."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from octopusos.core.memory.capabilities import PermissionDenied
from octopusos.core.memory.proposals import get_proposal_service
from octopusos.core.time import utc_now_ms
from octopusos.webui.db.memory_db import memory_db_connect


router = APIRouter(prefix="/api/memory", tags=["memory"])


DEFAULT_PROPOSER = "chat_agent"
DEFAULT_REVIEWER = "user:admin"
MS_PER_SECOND = 1000
MAX_TIMELINE_KEY_LEN = 2048
MAX_TIMELINE_VALUE_LEN = 8192


class ProposeMemoryRequest(BaseModel):
    agent_id: Optional[str] = None
    memory_item: Dict[str, Any]
    reason: Optional[str] = None


class ApproveProposalRequest(BaseModel):
    reviewer_id: Optional[str] = None
    reason: Optional[str] = None


class RejectProposalRequest(BaseModel):
    reviewer_id: Optional[str] = None
    reason: str


class MemoryTimelineItem(BaseModel):
    id: str
    timestamp: str
    key: str
    value: str
    type: str
    source: str
    confidence: float
    is_active: bool
    version: int
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    scope: str
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryTimelineResponse(BaseModel):
    events: list[MemoryTimelineItem]
    total: int
    limit: int
    offset: int


def _to_iso_from_ms(timestamp_ms: Optional[int]) -> str:
    if not timestamp_ms:
        timestamp_ms = utc_now_ms()
    from datetime import datetime, timezone

    return datetime.fromtimestamp(timestamp_ms / MS_PER_SECOND, tz=timezone.utc).isoformat()


def _coerce_content(memory_item: Dict[str, Any]) -> Dict[str, Any]:
    content = memory_item.get("content")
    if isinstance(content, dict):
        return content
    return {
        "key": memory_item.get("key"),
        "value": memory_item.get("value"),
    }


def _proposal_to_response_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    memory_item = raw.get("memory_item") or {}
    content = _coerce_content(memory_item)
    metadata = dict(memory_item.get("metadata") or {})
    metadata.setdefault("proposed_by", raw.get("proposed_by"))

    return {
        "id": raw.get("proposal_id"),
        "proposal_type": memory_item.get("type", "memory_update"),
        "content": metadata,
        "status": raw.get("status", "pending"),
        "created_at": _to_iso_from_ms(raw.get("proposed_at_ms")),
        "updated_at": _to_iso_from_ms(raw.get("reviewed_at_ms") or raw.get("proposed_at_ms")),
        "memory_item": {
            **memory_item,
            "content": content,
        },
    }


def _safe_json_loads(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _truncate_text(value: Any, max_len: int) -> str:
    text = str(value or "")
    if len(text) <= max_len:
        return text
    return text[:max_len]


def _timeline_source(sources: list[Any]) -> str:
    # Prefer explicit source type first, then fallback to legacy chat markers.
    for src in sources:
        if not isinstance(src, dict):
            continue
        source_type = str(src.get("type") or "").strip().lower()
        if source_type == "chat" and (src.get("message_id") or src.get("session_id")):
            return "rule_extraction"
    for src in sources:
        if isinstance(src, dict) and (src.get("message_id") or src.get("session_id")):
            return "rule_extraction"
    return "system"


@router.get("/timeline", response_model=MemoryTimelineResponse)
def memory_timeline(
    request: Request,
    response: Response,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    project_id: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    conn = memory_db_connect()
    try:
        response.headers["X-OctopusOS-Data-Store"] = "memoryos"
        response.headers["X-OctopusOS-Trace"] = "memory_items"
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'memory_items'"
        ).fetchone()
        if not table_exists:
            return {"events": [], "total": 0, "limit": limit, "offset": offset}

        columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(memory_items)").fetchall()}

        where: list[str] = []
        params: list[Any] = []

        if project_id and "project_id" in columns:
            where.append("project_id = ?")
            params.append(project_id)
        if event_type and "type" in columns:
            where.append("type = ?")
            params.append(event_type)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        total_row = conn.execute(
            f"SELECT COUNT(*) AS c FROM memory_items {where_sql}",
            params,
        ).fetchone()
        total = int((total_row["c"] if total_row else 0) or 0)

        # Stable ordering for pagination and deterministic e2e expectations.
        order_primary = "created_at" if "created_at" in columns else ("updated_at" if "updated_at" in columns else "id")
        order_secondary = ", id DESC" if "id" in columns else ""
        select_cols = [
            "id",
            "scope",
            "type",
            "content",
            "sources",
            "confidence",
            "project_id",
            "created_at",
            "updated_at",
            "version",
            "is_active",
            "supersedes",
            "superseded_by",
        ]
        actual_cols = [c for c in select_cols if c in columns]
        sql = f"""
            SELECT {", ".join(actual_cols)}
            FROM memory_items
            {where_sql}
            ORDER BY {order_primary} DESC{order_secondary}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(sql, [*params, limit, offset]).fetchall()

        events: list[dict[str, Any]] = []
        for row in rows:
            row_map = dict(row)
            content_raw = row_map.get("content")
            content = _safe_json_loads(content_raw, {})
            sources = _safe_json_loads(row_map.get("sources"), [])
            key_value = content.get("key") if isinstance(content, dict) else ""
            value_value = content.get("value") if isinstance(content, dict) else ""
            metadata = {
                "sources": sources,
                "request_path": str(request.url.path),
            }
            if not isinstance(content, dict):
                metadata["raw_content"] = _truncate_text(content_raw, MAX_TIMELINE_VALUE_LEN)
            timestamp = str(row_map.get("updated_at") or row_map.get("created_at") or "")
            events.append(
                {
                    "id": str(row_map.get("id") or ""),
                    "timestamp": timestamp,
                    "key": _truncate_text(key_value, MAX_TIMELINE_KEY_LEN),
                    "value": _truncate_text(value_value, MAX_TIMELINE_VALUE_LEN),
                    "type": str(row_map.get("type") or "-"),
                    "source": _timeline_source(sources),
                    "confidence": float(row_map.get("confidence") or 0.0),
                    "is_active": bool(row_map.get("is_active") if "is_active" in row_map else True),
                    "version": int(row_map.get("version") or 1),
                    "supersedes": row_map.get("supersedes"),
                    "superseded_by": row_map.get("superseded_by"),
                    "scope": str(row_map.get("scope") or "global"),
                    "project_id": row_map.get("project_id"),
                    "task_id": None,
                    "metadata": metadata,
                }
            )

        return {"events": events, "total": total, "limit": limit, "offset": offset}
    finally:
        conn.close()


@router.post("/propose")
def propose_memory(req: ProposeMemoryRequest) -> Dict[str, Any]:
    proposal_service = get_proposal_service()
    agent_id = req.agent_id or DEFAULT_PROPOSER
    try:
        proposal_id = proposal_service.propose_memory(
            agent_id=agent_id,
            memory_item=req.memory_item,
            reason=req.reason,
        )
        return {"proposal_id": proposal_id, "status": "pending"}
    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to propose memory: {e}") from e


@router.get("/proposals")
def list_proposals(
    status: Optional[str] = Query(default=None),
    proposed_by: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
) -> Dict[str, Any]:
    proposal_service = get_proposal_service()
    offset = (page - 1) * limit
    try:
        rows = proposal_service.list_proposals(
            agent_id=DEFAULT_REVIEWER,
            status=status,
            proposed_by=proposed_by,
            limit=limit,
            offset=offset,
        )
        proposals = [_proposal_to_response_row(row) for row in rows]
        return {"proposals": proposals, "total": len(proposals)}
    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list memory proposals: {e}") from e


@router.get("/proposals/stats")
def proposal_stats() -> Dict[str, Any]:
    proposal_service = get_proposal_service()
    try:
        return proposal_service.get_proposal_stats(DEFAULT_REVIEWER)
    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read proposal stats: {e}") from e


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: str) -> Dict[str, Any]:
    proposal_service = get_proposal_service()
    try:
        proposal = proposal_service.get_proposal(DEFAULT_REVIEWER, proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        return {"proposal": _proposal_to_response_row(proposal)}
    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get proposal: {e}") from e


@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: str, req: ApproveProposalRequest) -> Dict[str, Any]:
    proposal_service = get_proposal_service()
    reviewer_id = req.reviewer_id or DEFAULT_REVIEWER
    try:
        proposal_service.approve_proposal(
            reviewer_id=reviewer_id,
            proposal_id=proposal_id,
            reason=req.reason,
        )
        proposal = proposal_service.get_proposal(reviewer_id, proposal_id)
        return {"proposal": _proposal_to_response_row(proposal or {})}
    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve proposal: {e}") from e


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: str, req: RejectProposalRequest) -> Dict[str, Any]:
    proposal_service = get_proposal_service()
    reviewer_id = req.reviewer_id or DEFAULT_REVIEWER
    reason = (req.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")
    try:
        proposal_service.reject_proposal(
            reviewer_id=reviewer_id,
            proposal_id=proposal_id,
            reason=reason,
        )
        proposal = proposal_service.get_proposal(reviewer_id, proposal_id)
        return {"proposal": _proposal_to_response_row(proposal or {})}
    except PermissionDenied as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reject proposal: {e}") from e
