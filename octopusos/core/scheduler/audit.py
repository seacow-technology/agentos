"""Scheduler audit events and data structures."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class TaskNode:
    """Task node for task graph."""

    task_id: str
    task_type: str = "default"
    policy_mode: str = "semi_auto"
    parallelism_group: Optional[str] = None
    priority: int = 0
    depends_on: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SchedulerEvent:
    """Scheduler audit event (v0.3 standard)."""

    ts: float
    scheduler_mode: str  # sequential/parallel/cron/mixed
    trigger: str  # cron/manual/dependency_ready/retry
    selected_tasks: list[str]
    reason: dict  # {"priority": ..., "budget": ..., "locks": ...}
    run_id: Optional[str] = None
    batch_id: Optional[str] = None
    decision: str = "schedule_now"  # schedule_now/defer_to_next_batch/rejected
    constraints_checked: Optional[dict] = None

    @classmethod
    def create(
        cls,
        scheduler_mode: str,
        trigger: str,
        selected_tasks: list[str],
        reason: dict,
        run_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        decision: str = "schedule_now",
    ) -> SchedulerEvent:
        """
        Create scheduler event with automatic timestamp.

        Args:
            scheduler_mode: Scheduler mode
            trigger: Trigger reason
            selected_tasks: Selected task IDs
            reason: Decision reason dict
            run_id: Optional run ID
            batch_id: Optional batch ID
            decision: Decision outcome

        Returns:
            SchedulerEvent instance
        """
        return cls(
            ts=time.time(),
            scheduler_mode=scheduler_mode,
            trigger=trigger,
            selected_tasks=selected_tasks,
            reason=reason,
            run_id=run_id,
            batch_id=batch_id,
            decision=decision,
        )

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "timestamp": self.ts,
            "scheduler_mode": self.scheduler_mode,
            "trigger": self.trigger,
            "selected_tasks": self.selected_tasks,
            "reason": self.reason,
            "run_id": self.run_id,
            "batch_id": self.batch_id,
            "decision": self.decision,
            "constraints_checked": self.constraints_checked,
        }


class SchedulerAuditSink:
    """Sink for scheduler audit events."""

    def __init__(self):
        """Initialize audit sink."""
        self.events: list[SchedulerEvent] = []

    def write(self, event: SchedulerEvent) -> None:
        """
        Write event to sink.

        Args:
            event: Scheduler event to write
        """
        self.events.append(event)

    def get_events(self) -> list[SchedulerEvent]:
        """Get all recorded events."""
        return self.events.copy()

    def clear(self) -> None:
        """Clear all events."""
        self.events.clear()
