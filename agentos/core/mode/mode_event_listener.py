"""
Mode Event Listener - Converts Mode alerts to EventBus events

This module bridges the Mode alert system with the EventBus, converting
Mode violations into structured events that can be consumed by the Supervisor.

Task 27: Mode Event Listener Implementation
Date: 2026-01-30
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from agentos.core.events.bus import get_event_bus
from agentos.core.events.types import Event, EventType, EventEntity
from agentos.core.time import utc_now_iso
from agentos.core.mode.mode_alerts import (
    ModeAlertAggregator,
    get_alert_aggregator,
    AlertSeverity,
    ModeAlert,
)

logger = logging.getLogger(__name__)


class ModeEventListener:
    """
    Mode Event Listener

    Listens to Mode alerts and converts them into EventBus events.
    This enables the Supervisor to process Mode violations through
    the standard event processing pipeline.

    Architecture:
        Mode Alert → ModeEventListener → EventBus → Supervisor Inbox
    """

    def __init__(
        self,
        event_bus: Optional[Any] = None,
        alert_aggregator: Optional[ModeAlertAggregator] = None,
    ):
        """
        Initialize Mode Event Listener

        Args:
            event_bus: EventBus instance (defaults to global)
            alert_aggregator: AlertAggregator instance (defaults to global)
        """
        self.event_bus = event_bus or get_event_bus()
        self.alert_aggregator = alert_aggregator or get_alert_aggregator()
        self._event_count = 0

        logger.info("ModeEventListener initialized")

    def on_mode_violation(
        self,
        mode_id: str,
        operation: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        severity: Optional[AlertSeverity] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """
        Handle Mode violation and emit event

        This is the primary entry point for Mode violations. It:
        1. Records the alert in the AlertAggregator
        2. Creates a MODE_VIOLATION event
        3. Publishes to EventBus

        Args:
            mode_id: The mode that detected the violation
            operation: The operation that violated constraints (e.g., "apply_diff")
            message: Human-readable violation message
            context: Additional context data
            severity: Alert severity (defaults to ERROR)
            task_id: Optional task ID (extracted from context if not provided)
        """
        # Default severity
        if severity is None:
            severity = AlertSeverity.ERROR

        # Ensure context dict
        context = context or {}

        # Extract task_id from context if not provided
        if task_id is None:
            task_id = context.get("task_id", "unknown")

        # Record alert in aggregator
        self.alert_aggregator.alert(
            severity=severity,
            mode_id=mode_id,
            operation=operation,
            message=message,
            context=context,
        )

        # Create and emit MODE_VIOLATION event
        event = self._create_mode_violation_event(
            mode_id=mode_id,
            operation=operation,
            message=message,
            severity=severity,
            context=context,
            task_id=task_id,
        )

        # Publish to EventBus
        self.event_bus.emit(event)
        self._event_count += 1

        logger.info(
            f"MODE_VIOLATION event emitted: {mode_id}/{operation} "
            f"(severity={severity.value}, task={task_id})"
        )

    def _create_mode_violation_event(
        self,
        mode_id: str,
        operation: str,
        message: str,
        severity: AlertSeverity,
        context: Dict[str, Any],
        task_id: str,
    ) -> Event:
        """
        Create a MODE_VIOLATION event

        Event structure:
        {
          "type": "mode.violation",
          "ts": "2026-01-30T...",
          "source": "core",
          "entity": {"kind": "task", "id": "task_abc123"},
          "payload": {
            "mode_id": "design",
            "operation": "apply_diff",
            "severity": "error",
            "message": "...",
            "context": {...}
          }
        }

        Args:
            mode_id: Mode identifier
            operation: Operation name
            message: Violation message
            severity: Alert severity
            context: Additional context
            task_id: Task identifier

        Returns:
            Event object
        """
        return Event(
            type=EventType.MODE_VIOLATION,
            source="core",
            entity=EventEntity(kind="task", id=task_id),
            payload={
                "mode_id": mode_id,
                "operation": operation,
                "severity": severity.value,
                "message": message,
                "context": context,
            },
            ts=utc_now_iso(),
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get listener statistics

        Returns:
            Statistics dictionary
        """
        return {
            "events_emitted": self._event_count,
            "alert_stats": self.alert_aggregator.get_stats(),
        }


# Global instance
_global_listener: Optional[ModeEventListener] = None


def get_mode_event_listener() -> ModeEventListener:
    """
    Get global ModeEventListener instance

    Automatically initializes on first call.

    Returns:
        Global ModeEventListener instance
    """
    global _global_listener
    if _global_listener is None:
        _global_listener = ModeEventListener()
        logger.info("Global ModeEventListener created")
    return _global_listener


def emit_mode_violation(
    mode_id: str,
    operation: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    severity: Optional[AlertSeverity] = None,
    task_id: Optional[str] = None,
) -> None:
    """
    Convenience function to emit a mode violation event

    This is the recommended entry point for Mode violation reporting.
    It automatically uses the global listener instance.

    Args:
        mode_id: The mode that detected the violation
        operation: The operation that violated constraints
        message: Human-readable violation message
        context: Additional context data
        severity: Alert severity (defaults to ERROR)
        task_id: Optional task ID (extracted from context if not provided)

    Example:
        emit_mode_violation(
            mode_id="design",
            operation="apply_diff",
            message="Design mode cannot apply diffs",
            context={"audit_context": "executor_engine"},
            task_id="task_abc123"
        )
    """
    listener = get_mode_event_listener()
    listener.on_mode_violation(
        mode_id=mode_id,
        operation=operation,
        message=message,
        context=context,
        severity=severity,
        task_id=task_id,
    )


def reset_global_listener():
    """
    Reset global listener instance

    Warning: This will lose all statistics. Use only for testing.
    """
    global _global_listener
    _global_listener = None


__all__ = [
    "ModeEventListener",
    "get_mode_event_listener",
    "emit_mode_violation",
    "reset_global_listener",
]
