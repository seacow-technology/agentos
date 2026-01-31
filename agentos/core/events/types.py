"""
Event Types - Unified event envelope protocol v1

Sprint B Task #4: Event type definitions

Protocol:
{
  "type": "task.progress",
  "ts": "2026-01-27T10:21:33.123Z",
  "source": "core",
  "entity": {
    "kind": "task",
    "id": "task_abc123"
  },
  "payload": {
    "progress": 42,
    "message": "Indexing documents"
  }
}
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Literal
from datetime import datetime, timezone
from enum import Enum
from agentos.core.time import utc_now_iso



class EventType(str, Enum):
    """Event type enum (domain.action format)"""

    # Task events
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"

    # Task routing events (PR-1: Router Core)
    TASK_ROUTED = "task.routed"
    TASK_ROUTE_VERIFIED = "task.route_verified"
    TASK_REROUTED = "task.rerouted"
    TASK_ROUTE_OVERRIDDEN = "task.route_overridden"

    # Provider events
    PROVIDER_STATUS_CHANGED = "provider.status_changed"

    # Self-check events
    SELFCHECK_STARTED = "selfcheck.started"
    SELFCHECK_PROGRESS = "selfcheck.progress"
    SELFCHECK_COMPLETED = "selfcheck.completed"
    SELFCHECK_FAILED = "selfcheck.failed"

    # Mode events
    MODE_VIOLATION = "mode.violation"


@dataclass
class EventEntity:
    """Event entity (what the event is about)"""

    kind: Literal["task", "provider", "selfcheck"]
    id: str

    def to_dict(self) -> Dict[str, str]:
        """Convert to dict"""
        return {"kind": self.kind, "id": self.id}


@dataclass
class Event:
    """
    Unified event envelope (protocol v1)

    All events use this structure for consistency.
    """

    type: EventType
    source: Literal["core", "webui"] = "core"
    entity: EventEntity = None
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: utc_now_iso())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization"""
        return {
            "type": self.type.value,
            "ts": self.ts,
            "source": self.source,
            "entity": self.entity.to_dict() if self.entity else None,
            "payload": self.payload,
        }

    @classmethod
    def task_started(cls, task_id: str, payload: Dict[str, Any] = None) -> "Event":
        """Create task.started event"""
        return cls(
            type=EventType.TASK_STARTED,
            entity=EventEntity(kind="task", id=task_id),
            payload=payload or {},
        )

    @classmethod
    def task_progress(cls, task_id: str, progress: int, message: str = "") -> "Event":
        """Create task.progress event"""
        return cls(
            type=EventType.TASK_PROGRESS,
            entity=EventEntity(kind="task", id=task_id),
            payload={"progress": progress, "message": message},
        )

    @classmethod
    def task_completed(cls, task_id: str, payload: Dict[str, Any] = None) -> "Event":
        """Create task.completed event"""
        return cls(
            type=EventType.TASK_COMPLETED,
            entity=EventEntity(kind="task", id=task_id),
            payload=payload or {},
        )

    @classmethod
    def task_failed(cls, task_id: str, error: str) -> "Event":
        """Create task.failed event"""
        return cls(
            type=EventType.TASK_FAILED,
            entity=EventEntity(kind="task", id=task_id),
            payload={"error": error},
        )

    @classmethod
    def provider_status_changed(
        cls, provider_id: str, state: str, details: Dict[str, Any] = None
    ) -> "Event":
        """Create provider.status_changed event"""
        return cls(
            type=EventType.PROVIDER_STATUS_CHANGED,
            entity=EventEntity(kind="provider", id=provider_id),
            payload={"state": state, **(details or {})},
        )

    @classmethod
    def selfcheck_started(cls, check_id: str, payload: Dict[str, Any] = None) -> "Event":
        """Create selfcheck.started event"""
        return cls(
            type=EventType.SELFCHECK_STARTED,
            entity=EventEntity(kind="selfcheck", id=check_id),
            payload=payload or {},
        )

    @classmethod
    def selfcheck_progress(cls, check_id: str, progress: int, message: str = "") -> "Event":
        """Create selfcheck.progress event"""
        return cls(
            type=EventType.SELFCHECK_PROGRESS,
            entity=EventEntity(kind="selfcheck", id=check_id),
            payload={"progress": progress, "message": message},
        )

    @classmethod
    def selfcheck_completed(cls, check_id: str, payload: Dict[str, Any] = None) -> "Event":
        """Create selfcheck.completed event"""
        return cls(
            type=EventType.SELFCHECK_COMPLETED,
            entity=EventEntity(kind="selfcheck", id=check_id),
            payload=payload or {},
        )

    @classmethod
    def selfcheck_failed(cls, check_id: str, error: str) -> "Event":
        """Create selfcheck.failed event"""
        return cls(
            type=EventType.SELFCHECK_FAILED,
            entity=EventEntity(kind="selfcheck", id=check_id),
            payload={"error": error},
        )

    # Task routing event factory methods (PR-1: Router Core)

    @classmethod
    def task_routed(
        cls,
        task_id: str,
        selected: str,
        fallback: list,
        scores: dict,
        reasons: list,
        requirements: dict = None,
    ) -> "Event":
        """Create task.routed event"""
        return cls(
            type=EventType.TASK_ROUTED,
            entity=EventEntity(kind="task", id=task_id),
            payload={
                "selected": selected,
                "fallback": fallback,
                "scores": scores,
                "reasons": reasons,
                "requirements": requirements,
            },
        )

    @classmethod
    def task_route_verified(
        cls,
        task_id: str,
        instance_id: str,
        state: str,
    ) -> "Event":
        """Create task.route_verified event"""
        return cls(
            type=EventType.TASK_ROUTE_VERIFIED,
            entity=EventEntity(kind="task", id=task_id),
            payload={
                "instance_id": instance_id,
                "state": state,
            },
        )

    @classmethod
    def task_rerouted(
        cls,
        task_id: str,
        from_instance: str,
        to_instance: str,
        reason_code: str,
        reason_detail: str,
        fallback_chain: list = None,
    ) -> "Event":
        """Create task.rerouted event"""
        return cls(
            type=EventType.TASK_REROUTED,
            entity=EventEntity(kind="task", id=task_id),
            payload={
                "from_instance": from_instance,
                "to_instance": to_instance,
                "reason_code": reason_code,
                "reason_detail": reason_detail,
                "fallback_chain": fallback_chain or [],
            },
        )

    @classmethod
    def task_route_overridden(
        cls,
        task_id: str,
        from_instance: str,
        to_instance: str,
        user: str = None,
    ) -> "Event":
        """Create task.route_overridden event"""
        return cls(
            type=EventType.TASK_ROUTE_OVERRIDDEN,
            entity=EventEntity(kind="task", id=task_id),
            payload={
                "from_instance": from_instance,
                "to_instance": to_instance,
                "user": user,
            },
        )
