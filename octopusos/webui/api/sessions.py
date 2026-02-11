"""Persistent Sessions API backed by ChatService."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from octopusos.core.chat.service import ChatService, validate_message_role
from octopusos.core.chat.xss_sanitizer import (
    sanitize_message_content,
    sanitize_metadata,
    sanitize_session_title,
)
from octopusos.util.ulid import ulid
from octopusos.webui.api.validation import (
    validate_content_length,
    validate_title_length,
)
from octopusos.webui.websocket import chat as ws_chat
from octopusos.core.db import registry_db
from octopusos.store.timestamp_utils import now_ms

router = APIRouter()


def _service() -> ChatService:
    return ChatService()


def _ensure_csrf_cookie(response: JSONResponse) -> None:
    if response and "set-cookie" not in response.headers:
        response.set_cookie("csrf_token", uuid4().hex)


def _message_to_api(message: Any) -> Dict[str, Any]:
    return {
        "id": message.message_id,
        "message_id": message.message_id,
        "session_id": message.session_id,
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at.isoformat().replace("+00:00", "Z"),
        "timestamp": message.created_at.isoformat().replace("+00:00", "Z"),
        "metadata": message.metadata or {},
    }


def _session_to_api(chat_service: ChatService, session: Any, include_last_message: bool = False) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": session.session_id,
        "session_id": session.session_id,
        "title": session.title,
        "metadata": session.metadata or {},
        "created_at": session.created_at.isoformat().replace("+00:00", "Z"),
        "updated_at": session.updated_at.isoformat().replace("+00:00", "Z"),
        "unread_count": 0,
        "message_count": chat_service.count_messages(session.session_id),
    }

    if include_last_message:
        recent = chat_service.get_recent_messages(session.session_id, count=1)
        payload["last_message"] = recent[0].content if recent else ""

    return payload


def _isoformat_from_unix(ts: int | float | None) -> str:
    safe_ts = int(ts or 0)
    dt = datetime.fromtimestamp(max(0, safe_ts), tz=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _typed_session_state(session_id: str) -> Dict[str, Any]:
    state = ws_chat.recovery_store.get_state(session_id)
    if not state:
        return {
            "state": "active",
            "current_run_id": None,
            "last_seq": 0,
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "resume": {
                "supported": True,
                "status": "ok",
                "reason": None,
            },
        }

    current_run_id = str(state.get("run_id") or "").strip() or None
    state_value = str(state.get("status") or "active")
    last_seq = max(0, int(state.get("last_seq") or 0))
    reason = state.get("reason")

    resume_status = "ok"
    resume_reason = None
    if state_value == "interrupted" and current_run_id:
        replay_probe = ws_chat.recovery_store.list_events_after(
            session_id=session_id,
            run_id=current_run_id,
            after_seq=max(0, last_seq - 1),
            limit=1,
        )
        if not replay_probe:
            resume_status = "required_retry"
            resume_reason = str(reason or "no_replay_events")

    return {
        "state": state_value,
        "current_run_id": current_run_id,
        "last_seq": last_seq,
        "updated_at": _isoformat_from_unix(state.get("updated_at")),
        "resume": {
            "supported": True,
            "status": resume_status,
            "reason": resume_reason,
        },
    }


@router.get("/api/sessions")
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> JSONResponse:
    chat_service = _service()
    sessions = chat_service.list_sessions(limit=limit, offset=offset)
    data = [_session_to_api(chat_service, session, include_last_message=True) for session in sessions]
    response = JSONResponse(status_code=200, content=data)
    _ensure_csrf_cookie(response)
    return response


@router.post("/api/sessions")
async def create_session(request: Request) -> JSONResponse:
    if not request:
        payload = {}
    else:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Invalid payload")

    raw_title = payload.get("title")
    metadata = payload.get("metadata") or {}

    if raw_title is not None and not isinstance(raw_title, str):
        raise HTTPException(status_code=422, detail="title must be a string")

    title = raw_title or "New Chat"
    validate_title_length(title)

    safe_title = sanitize_session_title(title)
    safe_metadata = sanitize_metadata(metadata)

    chat_service = _service()
    session = chat_service.create_session(title=safe_title, metadata=safe_metadata)
    return JSONResponse(status_code=200, content=_session_to_api(chat_service, session))


@router.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> JSONResponse:
    chat_service = _service()
    try:
        session = chat_service.get_session(session_id)
    except ValueError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Session not found"})
    payload = _session_to_api(chat_service, session, include_last_message=True)
    payload.update(_typed_session_state(session_id))
    return JSONResponse(status_code=200, content=payload)


@router.put("/api/sessions/{session_id}")
async def update_session(session_id: str, request: Request) -> JSONResponse:
    if not request:
        payload = {}
    else:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Invalid payload")

    chat_service = _service()
    try:
        chat_service.get_session(session_id)
    except ValueError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Session not found"})

    title = payload.get("title")
    metadata = payload.get("metadata")

    if title is not None:
        if not isinstance(title, str):
            raise HTTPException(status_code=422, detail="title must be a string")
        validate_title_length(title)
        chat_service.update_session_title(session_id=session_id, title=sanitize_session_title(title))

    if metadata is not None:
        if not isinstance(metadata, dict):
            raise HTTPException(status_code=422, detail="metadata must be an object")
        chat_service.update_session_metadata(session_id=session_id, metadata=sanitize_metadata(metadata))

    session = chat_service.get_session(session_id)
    return JSONResponse(status_code=200, content=_session_to_api(chat_service, session, include_last_message=True))


@router.delete("/api/sessions")
async def delete_all_sessions() -> JSONResponse:
    chat_service = _service()
    sessions = chat_service.list_sessions(limit=5000, offset=0)
    deleted = 0
    for session in sessions:
        try:
            chat_service.delete_session(session.session_id)
            deleted += 1
        except Exception:
            continue
    return JSONResponse(status_code=200, content={"ok": True, "deleted": deleted})


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str) -> JSONResponse:
    chat_service = _service()
    try:
        chat_service.delete_session(session_id)
    except Exception:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Session not found"})
    return JSONResponse(status_code=200, content={"ok": True})


@router.get("/api/sessions/{session_id}/messages")
async def list_messages(
    session_id: str,
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    include_tool: bool = Query(default=False),
) -> JSONResponse:
    chat_service = _service()
    try:
        chat_service.get_session(session_id)
    except ValueError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Session not found"})
    messages = chat_service.get_messages(session_id=session_id, limit=limit, offset=offset)
    include_tool_enabled = include_tool is True
    if not include_tool_enabled:
        messages = [item for item in messages if getattr(item, "role", None) != "tool"]
    return JSONResponse(status_code=200, content=[_message_to_api(item) for item in messages])


@router.post("/api/sessions/{session_id}/messages")
async def add_message(session_id: str, request: Request) -> JSONResponse:
    chat_service = _service()
    try:
        chat_service.get_session(session_id)
    except ValueError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Session not found"})

    if not request:
        payload = {}
    else:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Invalid payload")

    role = payload.get("role")
    content = payload.get("content", "")
    metadata = payload.get("metadata") or {}

    role = validate_message_role(role)
    if not isinstance(content, str):
        raise HTTPException(status_code=422, detail="content must be a string")
    validate_content_length(content)

    safe_content = sanitize_message_content(content)
    safe_metadata = sanitize_metadata(metadata)

    raw_idempotency = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
    body_idempotency = payload.get("idempotency_key")
    idempotency_key: Optional[str]
    if isinstance(raw_idempotency, str) and raw_idempotency.strip():
        idempotency_key = raw_idempotency.strip()
    elif isinstance(body_idempotency, str) and body_idempotency.strip():
        idempotency_key = body_idempotency.strip()
    else:
        idempotency_key = ulid()

    request_id = request.headers.get("X-Request-ID") or request.headers.get("x-request-id")
    trace_id = (
        request.headers.get("X-Trace-ID")
        or request.headers.get("x-trace-id")
        or request.headers.get("traceparent")
    )
    if isinstance(request_id, str) and request_id.strip() and "request_id" not in safe_metadata:
        safe_metadata["request_id"] = request_id.strip()
    if isinstance(trace_id, str) and trace_id.strip() and "trace_id" not in safe_metadata:
        safe_metadata["trace_id"] = trace_id.strip()
    if role == "user" and "turn_id" not in safe_metadata:
        safe_metadata["turn_id"] = idempotency_key

    message = chat_service.add_message(
        session_id=session_id,
        role=role,
        content=safe_content,
        metadata=safe_metadata,
        idempotency_key=idempotency_key if role == "user" else None,
    )
    return JSONResponse(status_code=200, content=_message_to_api(message))


@router.delete("/api/sessions/{session_id}/messages/{message_id}")
async def delete_message(session_id: str, message_id: str) -> JSONResponse:
    chat_service = _service()
    try:
        chat_service.get_session(session_id)
    except ValueError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Session not found"})

    try:
        chat_service.delete_message(message_id)
    except ValueError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Message not found"})
    return JSONResponse(status_code=200, content={"ok": True})


@router.post("/api/sessions/{session_id}/presence/touch")
async def touch_session_presence(session_id: str) -> JSONResponse:
    # Best-effort presence update; used by chat injection guard to ensure the user is on this session.
    conn = registry_db.get_db()
    ts = int(now_ms())
    conn.execute(
        """
        INSERT INTO session_presence (session_id, last_seen_ms)
        VALUES (?, ?)
        ON CONFLICT(session_id) DO UPDATE SET last_seen_ms = excluded.last_seen_ms
        """,
        (session_id, ts),
    )
    conn.commit()
    return JSONResponse(status_code=200, content={"ok": True, "session_id": session_id, "last_seen_ms": ts})


__all__ = ["router"]
