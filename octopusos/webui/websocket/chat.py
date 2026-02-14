"""WebSocket chat handlers."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import WebSocket

from octopusos.core.chat.engine import ChatEngine
from octopusos.core.chat.service import ChatService
from octopusos.core.runner.launcher import launch_task_async
from octopusos.core.task.service import TaskService
from octopusos.store import get_db

logger = logging.getLogger(__name__)

CANCEL_TIMEOUT_SECONDS = 5.0


@dataclass
class ChatRuntimeConfig:
    model_type: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None

    def validate(self) -> Tuple[bool, Optional[str]]:
        if self.model_type is not None and self.model_type not in {"local", "cloud", "auto"}:
            return False, f"Invalid model_type: {self.model_type}"
        if self.temperature is not None:
            if not isinstance(self.temperature, (int, float)):
                return False, "temperature must be a number"
            if self.temperature < 0 or self.temperature > 2:
                return False, "temperature out of range"
        if self.top_p is not None:
            if not isinstance(self.top_p, (int, float)):
                return False, "top_p must be a number"
            if self.top_p <= 0 or self.top_p > 1:
                return False, "top_p out of range"
        if self.max_tokens is not None:
            if not isinstance(self.max_tokens, int):
                return False, "max_tokens must be an integer"
            if self.max_tokens <= 0:
                return False, "max_tokens must be positive"
        return True, None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "model_type": self.model_type,
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }
        return {k: v for k, v in data.items() if v is not None}


def extract_runtime_config(metadata: Dict[str, Any]) -> Tuple[ChatRuntimeConfig, Optional[str]]:
    if not isinstance(metadata, dict):
        return ChatRuntimeConfig(), "metadata must be a dict"

    def _get(key: str, camel: str):
        return metadata.get(key) if key in metadata else metadata.get(camel)

    config = ChatRuntimeConfig(
        model_type=_get("model_type", "modelType"),
        provider=_get("provider", "provider"),
        model=_get("model", "model"),
        temperature=_get("temperature", "temperature"),
        top_p=_get("top_p", "topP"),
        max_tokens=_get("max_tokens", "maxTokens"),
    )
    ok, error = config.validate()
    if not ok:
        return ChatRuntimeConfig(), error
    return config, None


def extract_session_control(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Extract session control fields that must persist in session metadata."""
    if not isinstance(metadata, dict):
        return {}

    control: Dict[str, Any] = {}

    phase = metadata.get("execution_phase", metadata.get("executionPhase"))
    if isinstance(phase, str) and phase in {"planning", "execution"}:
        control["execution_phase"] = phase

    auto_comm = metadata.get("auto_comm_enabled", metadata.get("autoCommEnabled"))
    if isinstance(auto_comm, bool):
        control["auto_comm_enabled"] = auto_comm

    return control


def extract_work_context(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Extract work-mode fields from request metadata."""
    if not isinstance(metadata, dict):
        return {}

    work_mode = metadata.get("work_mode", metadata.get("workMode"))
    if not isinstance(work_mode, bool) or not work_mode:
        return {}

    context: Dict[str, Any] = {"work_mode": True}

    work_session_id = metadata.get("work_session_id", metadata.get("workSessionId"))
    if isinstance(work_session_id, str) and work_session_id.strip():
        context["work_session_id"] = work_session_id.strip()

    active_artifact_id = metadata.get("active_artifact_id", metadata.get("activeArtifactId"))
    if isinstance(active_artifact_id, str) and active_artifact_id.strip():
        context["active_artifact_id"] = active_artifact_id.strip()

    selection = metadata.get("selection")
    if isinstance(selection, dict):
        context["selection"] = selection

    return context


def _apply_work_patch_if_needed(
    *,
    chat_service: ChatService,
    session_id: str,
    metadata: Dict[str, Any],
    assistant_content: str,
) -> Optional[Dict[str, Any]]:
    if not bool(metadata.get("work_mode")):
        return None

    try:
        session = chat_service.get_session(session_id)
    except Exception:
        return None

    session_metadata = session.metadata if isinstance(session.metadata, dict) else {}
    raw_work_state = session_metadata.get("work_state")
    work_state = raw_work_state if isinstance(raw_work_state, dict) else {}

    raw_artifacts = work_state.get("artifacts")
    artifacts = raw_artifacts if isinstance(raw_artifacts, list) else []
    normalized_artifacts: list[Dict[str, Any]] = []
    for idx, raw_item in enumerate(artifacts):
        item = raw_item if isinstance(raw_item, dict) else {}
        normalized_artifacts.append(
            {
                "artifact_id": str(item.get("artifact_id") or f"artifact-md-{idx + 1}"),
                "type": str(item.get("type") or "markdown"),
                "title": str(item.get("title") or "Work Draft"),
                "content": str(item.get("content") or ""),
                "version": int(item.get("version") or 1),
                "history": item.get("history") if isinstance(item.get("history"), list) else [],
            }
        )

    if not normalized_artifacts:
        normalized_artifacts = [
            {
                "artifact_id": "artifact-md-1",
                "type": "markdown",
                "title": "Work Draft",
                "content": "",
                "version": 1,
                "history": [],
            }
        ]

    preferred_artifact_id = str(
        metadata.get("active_artifact_id")
        or work_state.get("active_artifact_id")
        or normalized_artifacts[0]["artifact_id"]
    )

    selected_index = next(
        (idx for idx, item in enumerate(normalized_artifacts) if item["artifact_id"] == preferred_artifact_id),
        0,
    )
    artifact = normalized_artifacts[selected_index]
    next_version = max(1, int(artifact.get("version") or 1)) + 1
    artifact["content"] = assistant_content
    artifact["version"] = next_version

    history = artifact.get("history") if isinstance(artifact.get("history"), list) else []
    history.append(
        {
            "id": f"edit-{uuid.uuid4().hex[:8]}",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "actor": "assistant",
            "summary": "Applied assistant patch",
            "operation": "replace",
            "version": next_version,
        }
    )
    artifact["history"] = history
    normalized_artifacts[selected_index] = artifact

    ui_state = work_state.get("ui_state")
    normalized_ui_state = ui_state if isinstance(ui_state, dict) else {"right_tab": "preview"}

    chat_service.update_session_metadata(
        session_id=session_id,
        metadata={
            "work_mode": True,
            "work_state": {
                "artifacts": normalized_artifacts,
                "active_artifact_id": artifact["artifact_id"],
                "ui_state": normalized_ui_state,
            },
        },
    )

    return {
        "operation": "replace",
        "artifact_id": artifact["artifact_id"],
        "type": artifact["type"],
        "title": artifact["title"],
        "content": artifact["content"],
        "version": artifact["version"],
        "history_entry": history[-1],
    }


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str) -> None:
        self.active_connections.pop(session_id, None)

    async def send_message(self, session_id: str, message: Dict[str, Any]) -> None:
        run_id = str(message.get("run_id") or "").strip()
        seq_raw = message.get("seq")
        seq = int(seq_raw) if isinstance(seq_raw, int) or (isinstance(seq_raw, str) and seq_raw.isdigit()) else 0
        if run_id and seq > 0:
            try:
                recovery_store.append_event(
                    session_id=session_id,
                    run_id=run_id,
                    seq=seq,
                    event=message,
                )
                recovery_store.update_last_seq(session_id=session_id, run_id=run_id, seq=seq)
            except Exception:
                logger.debug("Failed to persist stream event %s/%s#%s", session_id, run_id, seq, exc_info=True)
        websocket = self.active_connections.get(session_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception:
                logger.warning("Failed to send websocket json message, disconnect stale session: %s", session_id, exc_info=True)
                self.disconnect(session_id)

    async def send_text(self, session_id: str, text: str) -> None:
        websocket = self.active_connections.get(session_id)
        if websocket:
            try:
                await websocket.send_text(text)
            except Exception:
                logger.warning("Failed to send websocket text message, disconnect stale session: %s", session_id, exc_info=True)
                self.disconnect(session_id)


manager = ConnectionManager()


@dataclass
class RunContext:
    run_id: str
    message_id: str
    session_id: str
    command_id: Optional[str] = None  # Idempotency key for the triggering user message (if provided)
    seq: int = 0
    state: str = "running"
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    task: Optional[asyncio.Task] = None
    cancelled_emitted: bool = False
    cancel_finalizer_started: bool = False

    def increment_seq(self) -> int:
        self.seq += 1
        return self.seq


_session_runs: Dict[str, RunContext] = {}
_run_lock = asyncio.Lock()
_chat_engine: Optional[ChatEngine] = None
_chat_service: Optional[ChatService] = None


class CommandStore:
    """SQLite-backed idempotency + audit storage for chat control commands."""

    def __init__(self) -> None:
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS command_dedup (
                session_id TEXT NOT NULL,
                command_id TEXT NOT NULL,
                command_type TEXT NOT NULL,
                payload_json TEXT,
                result_json TEXT,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (session_id, command_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                session_id TEXT,
                actor TEXT,
                event_type TEXT NOT NULL,
                run_id TEXT,
                target_message_id TEXT,
                old_content_hash TEXT,
                new_content_hash TEXT,
                reason TEXT,
                payload_json TEXT
            )
            """
        )
        conn.commit()
        self._schema_ready = True

    def get_command_result(self, session_id: str, command_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_schema()
        conn = get_db()
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT result_json FROM command_dedup WHERE session_id = ? AND command_id = ?",
            (session_id, command_id),
        ).fetchone()
        if not row:
            return None
        raw = row[0]
        if not raw:
            return None
        try:
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None

    def save_command(self, session_id: str, command_id: str, command_type: str, payload: Dict[str, Any]) -> None:
        self._ensure_schema()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO command_dedup
            (session_id, command_id, command_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, strftime('%s','now'))
            """,
            (session_id, command_id, command_type, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()

    def save_result(self, session_id: str, command_id: str, result: Dict[str, Any]) -> None:
        self._ensure_schema()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE command_dedup SET result_json = ? WHERE session_id = ? AND command_id = ?",
            (json.dumps(result, ensure_ascii=False), session_id, command_id),
        )
        conn.commit()

    def append_audit(
        self,
        *,
        session_id: str,
        actor: str,
        event_type: str,
        run_id: Optional[str] = None,
        target_message_id: Optional[str] = None,
        old_content_hash: Optional[str] = None,
        new_content_hash: Optional[str] = None,
        reason: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._ensure_schema()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_events
            (ts, session_id, actor, event_type, run_id, target_message_id, old_content_hash, new_content_hash, reason, payload_json)
            VALUES (strftime('%s','now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                actor,
                event_type,
                run_id,
                target_message_id,
                old_content_hash,
                new_content_hash,
                reason,
                json.dumps(payload or {}, ensure_ascii=False),
            ),
        )
        conn.commit()


command_store = CommandStore()


class SessionRecoveryStore:
    """Persistent run/session recovery state for WebSocket chat streaming."""

    def __init__(self) -> None:
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS session_run_state (
                session_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                message_id TEXT,
                status TEXT NOT NULL,
                last_seq INTEGER NOT NULL DEFAULT 0,
                reason TEXT,
                metadata_json TEXT,
                updated_at INTEGER NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS session_run_events (
                session_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                event_json TEXT NOT NULL,
                PRIMARY KEY (session_id, run_id, seq)
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_session_run_events_lookup
            ON session_run_events(session_id, run_id, seq)
            """
        )
        conn.commit()
        self._schema_ready = True

    def upsert_state(
        self,
        *,
        session_id: str,
        run_id: str,
        status: str,
        message_id: Optional[str] = None,
        last_seq: Optional[int] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._ensure_schema()
        conn = get_db()
        cursor = conn.cursor()
        current = cursor.execute(
            "SELECT last_seq FROM session_run_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        merged_last_seq = int(last_seq) if last_seq is not None else int(current[0] if current else 0)
        cursor.execute(
            """
            INSERT INTO session_run_state (session_id, run_id, message_id, status, last_seq, reason, metadata_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, strftime('%s','now'))
            ON CONFLICT(session_id) DO UPDATE SET
                run_id = excluded.run_id,
                message_id = excluded.message_id,
                status = excluded.status,
                last_seq = excluded.last_seq,
                reason = excluded.reason,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                session_id,
                run_id,
                message_id,
                status,
                max(0, merged_last_seq),
                reason,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
        conn.commit()

    def update_last_seq(self, *, session_id: str, run_id: str, seq: int) -> None:
        self._ensure_schema()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE session_run_state
            SET last_seq = CASE
                WHEN run_id = ? AND ? > last_seq THEN ?
                WHEN run_id = ? THEN last_seq
                ELSE last_seq
            END,
                updated_at = strftime('%s','now')
            WHERE session_id = ?
            """,
            (run_id, int(seq), int(seq), run_id, session_id),
        )
        conn.commit()

    def append_event(
        self,
        *,
        session_id: str,
        run_id: str,
        seq: int,
        event: Dict[str, Any],
    ) -> None:
        self._ensure_schema()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO session_run_events (session_id, run_id, seq, created_at, event_json)
            VALUES (?, ?, ?, strftime('%s','now'), ?)
            """,
            (session_id, run_id, int(seq), json.dumps(event, ensure_ascii=False)),
        )
        conn.commit()

    def get_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_schema()
        conn = get_db()
        cursor = conn.cursor()
        row = cursor.execute(
            """
            SELECT session_id, run_id, message_id, status, last_seq, reason, metadata_json, updated_at
            FROM session_run_state
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        if not row:
            return None
        raw_metadata = row[6]
        metadata: Dict[str, Any] = {}
        if raw_metadata:
            try:
                parsed = json.loads(raw_metadata)
                if isinstance(parsed, dict):
                    metadata = parsed
            except Exception:
                metadata = {}
        return {
            "session_id": row[0],
            "run_id": row[1],
            "message_id": row[2],
            "status": row[3],
            "last_seq": int(row[4] or 0),
            "reason": row[5],
            "metadata": metadata,
            "updated_at": int(row[7] or 0),
        }

    def list_events_after(
        self,
        *,
        session_id: str,
        run_id: str,
        after_seq: int = 0,
        limit: int = 2000,
    ) -> List[Dict[str, Any]]:
        self._ensure_schema()
        conn = get_db()
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            SELECT event_json
            FROM session_run_events
            WHERE session_id = ? AND run_id = ? AND seq > ?
            ORDER BY seq ASC
            LIMIT ?
            """,
            (session_id, run_id, max(0, int(after_seq)), max(1, min(int(limit), 5000))),
        ).fetchall()
        events: List[Dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row[0])
                if isinstance(payload, dict):
                    events.append(payload)
            except Exception:
                continue
        return events

    def mark_inflight_as_interrupted(self, *, reason: str) -> List[Dict[str, Any]]:
        """Mark persisted inflight states as interrupted (typically after process restart)."""
        self._ensure_schema()
        conn = get_db()
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            SELECT session_id, run_id, message_id, last_seq
            FROM session_run_state
            WHERE status IN ('active', 'streaming')
            """
        ).fetchall()
        cursor.execute(
            """
            UPDATE session_run_state
            SET status = 'interrupted',
                reason = ?,
                updated_at = strftime('%s','now')
            WHERE status IN ('active', 'streaming')
            """,
            (reason,),
        )
        conn.commit()
        return [
            {
                "session_id": row[0],
                "run_id": row[1],
                "message_id": row[2],
                "last_seq": int(row[3] or 0),
            }
            for row in rows
        ]


recovery_store = SessionRecoveryStore()


def get_session_store():
    """Compatibility accessor for legacy callers."""
    return get_chat_service()


def get_chat_engine():
    global _chat_engine
    if _chat_engine is None:
        _chat_engine = ChatEngine()
    return _chat_engine


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


def _persist_session_metadata_state(
    *,
    session_id: str,
    status: str,
    run_id: Optional[str],
    message_id: Optional[str],
    last_seq: int,
    reason: Optional[str] = None,
) -> None:
    try:
        get_chat_service().update_session_metadata(
            session_id=session_id,
            metadata={
                "session_state": status,
                "active_run_id": run_id,
                "active_run_message_id": message_id,
                "active_run_last_seq": max(0, int(last_seq)),
                "active_run_reason": reason,
                "active_run_updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )
    except Exception:
        logger.debug("Failed to persist session metadata state for %s", session_id, exc_info=True)


def _persist_run_state(
    *,
    session_id: str,
    status: str,
    run_id: str,
    message_id: str,
    last_seq: int,
    reason: Optional[str] = None,
) -> None:
    recovery_store.upsert_state(
        session_id=session_id,
        run_id=run_id,
        message_id=message_id,
        status=status,
        last_seq=last_seq,
        reason=reason,
    )
    _persist_session_metadata_state(
        session_id=session_id,
        status=status,
        run_id=run_id,
        message_id=message_id,
        last_seq=last_seq,
        reason=reason,
    )


def _bootstrap_interrupted_states() -> None:
    try:
        affected = recovery_store.mark_inflight_as_interrupted(reason="process_restarted")
    except Exception:
        logger.debug("Session recovery bootstrap skipped", exc_info=True)
        return
    for item in affected:
        _persist_session_metadata_state(
            session_id=item["session_id"],
            status="interrupted",
            run_id=item.get("run_id"),
            message_id=item.get("message_id"),
            last_seq=int(item.get("last_seq") or 0),
            reason="process_restarted",
        )


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _make_ack(
    *,
    session_id: str,
    command_id: str,
    status: str,
    run_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "type": "control.ack",
        "session_id": session_id,
        "command_id": command_id,
        "status": status,
    }
    if run_id:
        payload["run_id"] = run_id
    if reason:
        payload["reason"] = reason
    return payload


async def _emit_cancelled(
    run: RunContext,
    *,
    by_command_id: Optional[str],
    reason: str,
    hard_kill: bool,
) -> None:
    if run.cancelled_emitted:
        return

    run.cancelled_emitted = True
    run.state = "cancelled"
    seq = run.increment_seq()
    _persist_run_state(
        session_id=run.session_id,
        status="cancelled",
        run_id=run.run_id,
        message_id=run.message_id,
        last_seq=seq,
        reason=reason,
    )
    await manager.send_message(
        run.session_id,
        {
            "type": "message.cancelled",
            "session_id": run.session_id,
            "run_id": run.run_id,
            "message_id": run.message_id,
            "seq": seq,
            "by_command_id": by_command_id,
            "cancel_reason": reason,
            "hard_kill": hard_kill,
            "metadata": {"source": "real"},
        },
    )
    command_store.append_audit(
        session_id=run.session_id,
        actor="ws",
        event_type="stop_effective",
        run_id=run.run_id,
        reason=reason,
        payload={"by_command_id": by_command_id, "hard_kill": hard_kill},
    )


def _update_message_metadata(message_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    row = cursor.execute("SELECT metadata FROM chat_messages WHERE message_id = ?", (message_id,)).fetchone()
    if not row:
        raise ValueError(f"Message not found: {message_id}")

    current: Dict[str, Any] = {}
    raw = row[0]
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                current = parsed
        except Exception:
            current = {}

    merged = {**current, **updates}
    cursor.execute(
        "UPDATE chat_messages SET metadata = ? WHERE message_id = ?",
        (json.dumps(merged, ensure_ascii=False), message_id),
    )
    conn.commit()
    return merged


async def _finalize_cancel(
    *,
    session_id: str,
    run: RunContext,
    command_id: Optional[str],
    reason: str,
) -> None:
    if run.cancel_finalizer_started:
        return
    run.cancel_finalizer_started = True

    hard_kill = False
    if run.task:
        try:
            await asyncio.wait_for(asyncio.shield(run.task), timeout=CANCEL_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            hard_kill = True
            run.task.cancel()
            with contextlib.suppress(BaseException):
                await run.task
        except Exception:
            pass

    if not run.cancelled_emitted:
        await _emit_cancelled(
            run,
            by_command_id=command_id,
            reason=reason,
            hard_kill=hard_kill,
        )


async def _get_active_run(session_id: str) -> Optional[RunContext]:
    async with _run_lock:
        run = _session_runs.get(session_id)
        if not run:
            return None
        if run.state in {"completed", "cancelled", "failed"}:
            return None
        return run


async def start_user_message_stream(
    session_id: str,
    content: str,
    metadata: Dict[str, Any],
    *,
    trigger_message_id: Optional[str] = None,
    command_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not isinstance(content, str) or not content.strip():
        return {"ok": False, "reason": "invalid_content"}

    incoming_metadata = metadata if isinstance(metadata, dict) else {}
    runtime_config, config_error = extract_runtime_config(incoming_metadata)
    if config_error:
        return {"ok": False, "reason": f"invalid_config:{config_error}"}
    session_control = extract_session_control(incoming_metadata)
    work_context = extract_work_context(incoming_metadata)
    effective_metadata = {
        **runtime_config.to_dict(),
        **session_control,
        **work_context,
    }

    async with _run_lock:
        active = _session_runs.get(session_id)
        if active and active.state in {"running", "cancelling"}:
            return {"ok": False, "reason": "concurrent_stream", "run_id": active.run_id}

        run_id = f"run_{uuid.uuid4().hex}"
        message_id = f"msg_{uuid.uuid4().hex}"
        run = RunContext(run_id=run_id, message_id=message_id, session_id=session_id, command_id=command_id)
        _session_runs[session_id] = run

    run.task = asyncio.create_task(
        handle_user_message(
            run=run,
            content=content,
            metadata=effective_metadata,
            trigger_message_id=trigger_message_id,
        )
    )

    _persist_run_state(
        session_id=session_id,
        status="active",
        run_id=run_id,
        message_id=message_id,
        last_seq=0,
        reason=None,
    )

    await manager.send_message(
        session_id,
        {
            "type": "run.started",
            "session_id": session_id,
            "run_id": run_id,
            "trigger_message_id": trigger_message_id,
            "message_id": message_id,
            "metadata": {"source": "real"},
        },
    )
    _persist_run_state(
        session_id=session_id,
        status="streaming",
        run_id=run.run_id,
        message_id=run.message_id,
        last_seq=run.seq,
        reason=None,
    )

    return {"ok": True, "run_id": run_id, "message_id": message_id}


async def request_stop(
    *,
    session_id: str,
    run_id: Optional[str],
    command_id: str,
    reason: str,
    actor: str = "ws",
    scope: str = "run_and_hold",
) -> Dict[str, Any]:
    existing = command_store.get_command_result(session_id, command_id)
    if existing:
        return existing

    payload = {
        "run_id": run_id,
        "reason": reason,
        "scope": scope,
    }
    command_store.save_command(session_id, command_id, "stop", payload)

    run = await _get_active_run(session_id)
    if run_id and run and run_id != run.run_id:
        ack = _make_ack(
            session_id=session_id,
            command_id=command_id,
            status="rejected",
            run_id=run.run_id,
            reason="run_id_mismatch",
        )
        command_store.save_result(session_id, command_id, ack)
        return ack

    def _cancel_run() -> Dict[str, Any]:
        active_run = run
        if not active_run:
            return {"ok": False, "status": "rejected", "reason": "no_active_run", "scope": "run"}

        active_run.state = "cancelling"
        active_run.cancel_event.set()
        command_store.append_audit(
            session_id=session_id,
            actor=actor,
            event_type="stop_requested",
            run_id=active_run.run_id,
            reason=reason,
            payload={"command_id": command_id, "scope": scope},
        )
        asyncio.create_task(
            _finalize_cancel(
                session_id=session_id,
                run=active_run,
                command_id=command_id,
                reason=reason,
            )
        )
        return {"ok": True, "status": "accepted", "scope": "run", "run_id": active_run.run_id}

    def _cancel_hold() -> Dict[str, Any]:
        chat_engine = get_chat_engine()
        return chat_engine.cancel_active_hold(
            session_id=session_id,
            command_id=command_id,
            reason=reason,
            by="external_stop",
        )

    cancel_result = get_chat_service().cancel_session_run(
        session_id=session_id,
        command_id=command_id,
        reason=reason,
        scope=scope,
        run_id=run_id,
        actor=actor,
        cancel_run=_cancel_run,
        cancel_hold=_cancel_hold,
    )

    run_status = (cancel_result.get("run_result") or {}).get("status")
    hold_status = (cancel_result.get("hold_result") or {}).get("status")
    accepted = run_status == "accepted" or hold_status == "accepted"
    ack = _make_ack(
        session_id=session_id,
        command_id=command_id,
        status="accepted" if accepted else "rejected",
        run_id=(cancel_result.get("run_result") or {}).get("run_id") or run_id,
        reason=None if accepted else "no_active_run_or_hold",
    )
    ack["scope"] = scope
    ack["cancel"] = cancel_result
    command_store.save_result(session_id, command_id, ack)

    if accepted:
        await manager.send_message(
            session_id,
            {
                "type": "stream.cancelled",
                "session_id": session_id,
                "command_id": command_id,
                "reason": reason,
                "scope": scope,
                "metadata": {"source": "real"},
            },
        )

    return ack


async def handle_edit_resend(
    *,
    session_id: str,
    target_message_id: str,
    new_content: str,
    command_id: str,
    reason: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    existing = command_store.get_command_result(session_id, command_id)
    if existing:
        return existing

    command_store.save_command(
        session_id,
        command_id,
        "edit_resend",
        {
            "target_message_id": target_message_id,
            "new_content_hash": _hash_text(new_content or ""),
            "reason": reason,
        },
    )

    if not isinstance(new_content, str) or not new_content.strip():
        ack = _make_ack(
            session_id=session_id,
            command_id=command_id,
            status="rejected",
            reason="invalid_new_content",
        )
        command_store.save_result(session_id, command_id, ack)
        return ack

    chat_service = get_chat_service()
    try:
        target = chat_service.get_message(target_message_id)
    except Exception:
        ack = _make_ack(
            session_id=session_id,
            command_id=command_id,
            status="rejected",
            reason="target_message_not_found",
        )
        command_store.save_result(session_id, command_id, ack)
        return ack

    if target.session_id != session_id:
        ack = _make_ack(
            session_id=session_id,
            command_id=command_id,
            status="rejected",
            reason="target_message_out_of_session",
        )
        command_store.save_result(session_id, command_id, ack)
        return ack

    if target.role != "user":
        ack = _make_ack(
            session_id=session_id,
            command_id=command_id,
            status="rejected",
            reason="target_message_not_user",
        )
        command_store.save_result(session_id, command_id, ack)
        return ack

    active_run = await _get_active_run(session_id)
    if active_run:
        active_run.state = "cancelling"
        active_run.cancel_event.set()
        asyncio.create_task(
            _finalize_cancel(
                session_id=session_id,
                run=active_run,
                command_id=command_id,
                reason="edit_resend_preempt",
            )
        )
        with contextlib.suppress(Exception):
            await asyncio.wait_for(asyncio.shield(active_run.task), timeout=CANCEL_TIMEOUT_SECONDS)

    old_metadata = target.metadata if isinstance(target.metadata, dict) else {}
    revision = int(old_metadata.get("revision") or 1) + 1

    _update_message_metadata(
        target_message_id,
        {
            "status": "superseded",
            "superseded_by_command_id": command_id,
        },
    )

    new_message = chat_service.add_message(
        session_id=session_id,
        role="user",
        content=new_content,
        metadata={
            "status": "active",
            "revision": revision,
            "parent_message_id": target_message_id,
            "edit_reason": reason,
        },
        idempotency_key=command_id,
        correlation_id=None,
        causation_id=target_message_id,
        source="ws_edit_resend",
    )

    await manager.send_message(
        session_id,
        {
            "type": "message.superseded",
            "session_id": session_id,
            "target_message_id": target_message_id,
            "new_message_id": new_message.message_id,
            "revision": revision,
            "parent_message_id": target_message_id,
            "by_command_id": command_id,
            "metadata": {"source": "real"},
        },
    )

    command_store.append_audit(
        session_id=session_id,
        actor="ws",
        event_type="message_superseded",
        target_message_id=target_message_id,
        old_content_hash=_hash_text(target.content),
        new_content_hash=_hash_text(new_content),
        reason=reason,
        payload={"new_message_id": new_message.message_id, "command_id": command_id},
    )

    start_result = await start_user_message_stream(
        session_id=session_id,
        content=new_content,
        metadata=metadata or {},
        trigger_message_id=new_message.message_id,
    )
    if not start_result.get("ok"):
        ack = _make_ack(
            session_id=session_id,
            command_id=command_id,
            status="rejected",
            reason=f"resend_failed:{start_result.get('reason', 'unknown')}",
        )
        command_store.save_result(session_id, command_id, ack)
        return ack

    ack = _make_ack(
        session_id=session_id,
        command_id=command_id,
        status="accepted",
        run_id=start_result.get("run_id"),
    )
    command_store.save_result(session_id, command_id, ack)
    return ack


async def handle_user_message(
    *,
    run: RunContext,
    content: str,
    metadata: Dict[str, Any],
    trigger_message_id: Optional[str] = None,
) -> None:
    session_id = run.session_id

    chat_service = get_chat_service()
    chat_engine = get_chat_engine()

    try:
        try:
            chat_service.get_session(session_id)
            if metadata:
                chat_service.update_session_metadata(session_id=session_id, metadata=metadata)
        except Exception:
            chat_service.create_session(
                title=f"WebUI Session {session_id[:8]}",
                metadata={"source": "webui", **metadata},
                session_id=session_id,
            )
    except Exception as exc:
        logger.warning("Failed to ensure core chat session %s: %s", session_id, exc)

    run.increment_seq()
    await manager.send_message(
        session_id,
        {
            "type": "message.start",
            "session_id": session_id,
            "run_id": run.run_id,
            "message_id": run.message_id,
            "trigger_message_id": trigger_message_id,
            "seq": run.seq,
            "role": "assistant",
            "metadata": {"source": "real"},
        },
    )

    response_buffer: list[str] = []
    response_metadata: Dict[str, Any] = {}
    tool_result: Optional[Dict[str, Any]] = None

    try:
        loop = asyncio.get_running_loop()
        stream_generator = await loop.run_in_executor(
            None,
            lambda: chat_engine.send_message(
                session_id=session_id,
                user_input=content,
                stream=True,
                idempotency_key=run.command_id,
            ),
        )

        if isinstance(stream_generator, dict):
            if run.cancel_event.is_set():
                await _emit_cancelled(run, by_command_id=None, reason="cancelled_before_emit", hard_kill=False)
                return

            final_text = str(stream_generator.get("content") or "").strip() or "No response generated."
            response_metadata = dict(stream_generator.get("metadata") or {})
            candidate_tool_result = stream_generator.get("tool_result")
            if isinstance(candidate_tool_result, dict):
                tool_result = candidate_tool_result

            run.increment_seq()
            await manager.send_message(
                session_id,
                {
                    "type": "message.delta",
                    "session_id": session_id,
                    "run_id": run.run_id,
                    "message_id": run.message_id,
                    "seq": run.seq,
                    "delta": final_text,
                    "content": final_text,
                    "metadata": {"source": "real", **response_metadata},
                },
            )
            if tool_result:
                run.increment_seq()
                await manager.send_message(
                    session_id,
                    {
                        "type": "message.tool_result",
                        "session_id": session_id,
                        "run_id": run.run_id,
                        "message_id": run.message_id,
                        "seq": run.seq,
                        **tool_result,
                    },
                )
            run.state = "completed"
            artifact_patch = _apply_work_patch_if_needed(
                chat_service=chat_service,
                session_id=session_id,
                metadata=metadata,
                assistant_content=final_text,
            )
            run.increment_seq()
            await manager.send_message(
                session_id,
                {
                    "type": "message.end",
                    "session_id": session_id,
                    "run_id": run.run_id,
                    "message_id": run.message_id,
                    "seq": run.seq,
                    "content": final_text,
                    "metadata": {"total_seq": run.seq, "source": "real", **response_metadata},
                    "artifact_patch": artifact_patch,
                },
            )
            _persist_run_state(
                session_id=session_id,
                status="completed",
                run_id=run.run_id,
                message_id=run.message_id,
                last_seq=run.seq,
                reason=None,
            )
            return

        chunk_queue: asyncio.Queue[Tuple[str, Optional[str]]] = asyncio.Queue()

        def sync_iterate() -> None:
            try:
                for chunk in stream_generator:
                    if run.cancel_event.is_set():
                        close_fn = getattr(stream_generator, "close", None)
                        if callable(close_fn):
                            close_fn()
                        break
                    asyncio.run_coroutine_threadsafe(
                        chunk_queue.put(("chunk", str(chunk))),
                        loop,
                    )
            except Exception as exc:
                asyncio.run_coroutine_threadsafe(
                    chunk_queue.put(("error", str(exc))),
                    loop,
                )
            finally:
                asyncio.run_coroutine_threadsafe(
                    chunk_queue.put(("done", None)),
                    loop,
                )

        producer_future = loop.run_in_executor(None, sync_iterate)
        try:
            while True:
                chunk_type, chunk_data = await chunk_queue.get()

                if run.cancel_event.is_set():
                    break

                if chunk_type == "chunk":
                    if chunk_data:
                        response_buffer.append(chunk_data)
                        run.increment_seq()
                        await manager.send_message(
                            session_id,
                            {
                                "type": "message.delta",
                                "session_id": session_id,
                                "run_id": run.run_id,
                                "message_id": run.message_id,
                                "seq": run.seq,
                                "delta": chunk_data,
                                "content": chunk_data,
                                "metadata": {"source": "real"},
                            },
                        )
                    continue

                if chunk_type == "error":
                    raise RuntimeError(chunk_data or "Unknown streaming error")

                if chunk_type == "done":
                    break
        finally:
            if not producer_future.done():
                producer_future.cancel()

        if run.cancel_event.is_set():
            await _emit_cancelled(run, by_command_id=None, reason="user_cancelled", hard_kill=False)
            return

        final_response = "".join(response_buffer).strip() or "No response generated."
        if not response_buffer:
            run.increment_seq()
            await manager.send_message(
                session_id,
                {
                    "type": "message.delta",
                    "session_id": session_id,
                    "run_id": run.run_id,
                    "message_id": run.message_id,
                    "seq": run.seq,
                    "delta": final_response,
                    "content": final_response,
                    "metadata": {"source": "real"},
                },
            )

        run.state = "completed"
        artifact_patch = _apply_work_patch_if_needed(
            chat_service=chat_service,
            session_id=session_id,
            metadata=metadata,
            assistant_content=final_response,
        )
        run.increment_seq()
        await manager.send_message(
            session_id,
            {
                "type": "message.end",
                "session_id": session_id,
                "run_id": run.run_id,
                "message_id": run.message_id,
                "seq": run.seq,
                "content": final_response,
                "metadata": {"total_seq": run.seq, "source": "real", **response_metadata},
                "artifact_patch": artifact_patch,
            },
        )
        _persist_run_state(
            session_id=session_id,
            status="completed",
            run_id=run.run_id,
            message_id=run.message_id,
            last_seq=run.seq,
            reason=None,
        )
    except asyncio.CancelledError:
        run.state = "cancelled"
        if not run.cancelled_emitted:
            await _emit_cancelled(run, by_command_id=None, reason="hard_cancel", hard_kill=True)
        raise
    except Exception as exc:
        run.state = "failed"
        logger.error("Chat streaming failed for session %s: %s", session_id, exc, exc_info=True)
        await manager.send_message(
            session_id,
            {
                "type": "message.error",
                "session_id": session_id,
                "run_id": run.run_id,
                "message_id": run.message_id,
                "content": f"Chat engine error: {exc}",
                "metadata": {"error_type": "engine_failure", "source": "real"},
            },
        )
        _persist_run_state(
            session_id=session_id,
            status="failed",
            run_id=run.run_id,
            message_id=run.message_id,
            last_seq=run.seq,
            reason=str(exc),
        )
    finally:
        async with _run_lock:
            current = _session_runs.get(session_id)
            if current and current.run_id == run.run_id:
                if run.state in {"running", "cancelling"}:
                    run.state = "completed"
                _session_runs.pop(session_id, None)


async def handle_task_command(session_id: str, content: str, metadata: Dict[str, Any]) -> None:
    text = content.strip()
    if not text.startswith("/task"):
        return

    title = text[len("/task"):].strip()
    if not title:
        await manager.send_message(
            session_id,
            {
                "type": "message.error",
                "content": "Task title is required",
                "metadata": {"error_type": "invalid_command", "source": "real"},
            },
        )
        return

    # WebUI/Chat unified semantics: create -> planning -> awaiting_approval (default).
    # Chat should not auto-execute.
    from octopusos.core.task import TaskManager
    from octopusos.core.runner.task_runner import TaskRunner
    import threading
    from pathlib import Path
    import os

    tm = TaskManager()
    task = tm.create_task(
        title=title,
        session_id=session_id,
        created_by="chat",
        metadata={"source": "chat", "nl_request": title, "run_mode": "assisted"},
    )

    def _run_planning():
        runner = TaskRunner(
            task_manager=tm,
            repo_path=Path(os.getenv("OCTOPUSOS_REPO_ROOT") or ".").resolve(),
            policy_path=Path(os.getenv("OCTOPUSOS_POLICY_PATH")).resolve() if os.getenv("OCTOPUSOS_POLICY_PATH") else None,
            use_real_pipeline=False,
        )
        runner.run_task(task.task_id)

    thread = threading.Thread(target=_run_planning, name=f"chat-task-planner-{task.task_id[:12]}", daemon=True)
    thread.start()
    launched = True

    await manager.send_message(
        session_id,
        {
            "type": "message.system",
            "content": "Task created (planning). Approve to execute." if launched else "Task created",
            "metadata": {"task_id": task.task_id, "auto_launched": launched, "source": "real"},
        },
    )
    store = get_session_store()
    if store:
        try:
            store.add_message(
                session_id=session_id,
                role="system",
                content="task_created",
                metadata={"task_id": task.task_id},
            )
        except Exception:
            logger.warning("Failed to persist task system message for session %s", session_id)


async def get_active_run_id(session_id: str) -> Optional[str]:
    run = await _get_active_run(session_id)
    return run.run_id if run else None


async def resume_stream(
    *,
    session_id: str,
    run_id: Optional[str],
    last_seq: int,
) -> Dict[str, Any]:
    state = recovery_store.get_state(session_id)
    if not state:
        return {
            "status": "not_found",
            "session_id": session_id,
            "run_id": run_id,
            "from_seq": max(0, int(last_seq)),
            "to_seq": max(0, int(last_seq)),
            "events": [],
        }

    target_run_id = str(run_id or state.get("run_id") or "").strip()
    state_run_id = str(state.get("run_id") or "").strip()
    if not target_run_id or target_run_id != state_run_id:
        return {
            "status": "required_retry",
            "reason": "run_id_mismatch_or_missing",
            "session_id": session_id,
            "run_id": target_run_id or state_run_id,
            "from_seq": max(0, int(last_seq)),
            "to_seq": int(state.get("last_seq") or 0),
            "events": [],
            "session_state": state.get("status"),
        }

    safe_last_seq = max(0, int(last_seq))
    events = recovery_store.list_events_after(
        session_id=session_id,
        run_id=target_run_id,
        after_seq=safe_last_seq,
        limit=5000,
    )
    if events:
        to_seq = int(events[-1].get("seq") or safe_last_seq)
        return {
            "status": "replayed",
            "session_id": session_id,
            "run_id": target_run_id,
            "from_seq": safe_last_seq,
            "to_seq": to_seq,
            "events": events,
            "session_state": state.get("status"),
        }

    state_status = str(state.get("status") or "")
    if state_status in {"active", "streaming"}:
        recovery_store.upsert_state(
            session_id=session_id,
            run_id=target_run_id,
            message_id=state.get("message_id"),
            status="interrupted",
            last_seq=int(state.get("last_seq") or safe_last_seq),
            reason="resume_no_buffer",
            metadata=state.get("metadata") if isinstance(state.get("metadata"), dict) else {},
        )
        _persist_session_metadata_state(
            session_id=session_id,
            status="interrupted",
            run_id=target_run_id,
            message_id=state.get("message_id"),
            last_seq=int(state.get("last_seq") or safe_last_seq),
            reason="resume_no_buffer",
        )
        state_status = "interrupted"

    return {
        "status": "required_retry" if state_status in {"interrupted", "streaming", "active"} else "noop",
        "reason": "no_replay_events",
        "session_id": session_id,
        "run_id": target_run_id,
        "from_seq": safe_last_seq,
        "to_seq": int(state.get("last_seq") or safe_last_seq),
        "events": [],
        "session_state": state_status,
    }


_bootstrap_interrupted_states()
