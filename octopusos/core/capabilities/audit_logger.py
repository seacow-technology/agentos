"""
Extension Audit Logger

Logs extension execution events to the database for audit trail.
Integrates with existing task_audits table.

Part of PR-E3: Permissions + Deny/Audit System
"""

import logging
from typing import List, Dict, Any, Optional

from agentos.core.capabilities.audit_events import (
    ExtensionAuditEvent,
    ExtensionAuditEventType,
    EXT_CMD_ROUTED,
    EXT_RUN_STARTED,
    EXT_RUN_FINISHED,
    EXT_RUN_DENIED,
    EXT_PERMISSION_CHECK
)
from agentos.core.audit import log_audit_event, get_audit_events, VALID_EVENT_TYPES

logger = logging.getLogger(__name__)


# ============================================
# Register Extension Event Types
# ============================================

# Add extension events to valid event types
EXTENSION_EVENT_TYPES = {
    EXT_CMD_ROUTED,
    EXT_RUN_STARTED,
    EXT_RUN_FINISHED,
    EXT_RUN_DENIED,
    EXT_PERMISSION_CHECK
}

# Monkey-patch the VALID_EVENT_TYPES set to include extension events
VALID_EVENT_TYPES.update(EXTENSION_EVENT_TYPES)


# ============================================
# Audit Logger
# ============================================

class AuditLogger:
    """
    Logger for extension audit events

    Writes extension execution events to the task_audits table
    for comprehensive audit trail.

    Example:
        >>> logger = AuditLogger()
        >>> event = ExtensionAuditEvent.create_started(
        ...     ext_id="tools.postman",
        ...     action="/postman get",
        ...     permissions_requested=["exec_shell"],
        ...     run_id="run_123"
        ... )
        >>> audit_id = logger.log_extension_event(event)
    """

    def log_extension_event(
        self,
        event: ExtensionAuditEvent,
        task_id: Optional[str] = None
    ) -> int:
        """
        Log extension audit event to database

        Args:
            event: Extension audit event
            task_id: Optional task ID to associate with event

        Returns:
            Audit record ID

        Example:
            >>> logger = AuditLogger()
            >>> event = ExtensionAuditEvent.create_denied(
            ...     ext_id="tools.postman",
            ...     action="/postman exec",
            ...     permissions_requested=["exec_shell"],
            ...     reason_code="PERMISSION_DENIED_REMOTE_MODE"
            ... )
            >>> audit_id = logger.log_extension_event(event)
            >>> assert audit_id > 0
        """
        # Determine log level based on event type and decision
        if event.decision.value == "deny":
            level = "warn"
        elif event.event_type == ExtensionAuditEventType.EXT_RUN_FINISHED:
            if event.exit_code and event.exit_code != 0:
                level = "error"
            else:
                level = "info"
        else:
            level = "info"

        # Build metadata
        metadata = {
            "ext_id": event.ext_id,
            "action": event.action,
            "permissions_requested": event.permissions_requested,
            "decision": event.decision.value,
            "user_id": event.user_id
        }

        # Add optional fields
        if event.args_hash:
            metadata["args_hash"] = event.args_hash
        if event.reason_code:
            metadata["reason_code"] = event.reason_code
        if event.stdout_hash:
            metadata["stdout_hash"] = event.stdout_hash
        if event.stderr_hash:
            metadata["stderr_hash"] = event.stderr_hash
        if event.exit_code is not None:
            metadata["exit_code"] = event.exit_code
        if event.duration_ms is not None:
            metadata["duration_ms"] = event.duration_ms
        if event.session_id:
            metadata["session_id"] = event.session_id
        if event.project_id:
            metadata["project_id"] = event.project_id
        if event.run_id:
            metadata["run_id"] = event.run_id

        # Merge additional metadata
        if event.metadata:
            metadata.update(event.metadata)

        # Log to audit system
        try:
            audit_id = log_audit_event(
                event_type=event.event_type.value,
                task_id=task_id,
                level=level,
                metadata=metadata
            )
            logger.debug(
                f"Logged extension audit event: {event.event_type.value} "
                f"for {event.ext_id} (audit_id={audit_id})"
            )
            return audit_id

        except Exception as e:
            logger.error(f"Failed to log extension audit event: {e}", exc_info=True)
            # Don't propagate - auditing should not break execution
            return -1

    def get_extension_events(
        self,
        ext_id: Optional[str] = None,
        event_type: Optional[str] = None,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query extension audit events

        Args:
            ext_id: Filter by extension ID
            event_type: Filter by event type
            session_id: Filter by session ID
            project_id: Filter by project ID
            run_id: Filter by run ID
            limit: Maximum number of results

        Returns:
            List of audit events

        Example:
            >>> logger = AuditLogger()
            >>> events = logger.get_extension_events(
            ...     ext_id="tools.postman",
            ...     event_type="EXT_RUN_DENIED",
            ...     limit=10
            ... )
        """
        # Get base events filtered by event type
        if event_type:
            events = get_audit_events(event_type=event_type, limit=limit * 2)
        else:
            # Get all extension events
            all_events = []
            for ext_event_type in EXTENSION_EVENT_TYPES:
                events_batch = get_audit_events(event_type=ext_event_type, limit=limit * 2)
                all_events.extend(events_batch)
            events = all_events

        # Apply additional filters
        filtered = []
        for event in events:
            payload = event.get("payload", {})

            # Check ext_id filter
            if ext_id and payload.get("ext_id") != ext_id:
                continue

            # Check session_id filter
            if session_id and payload.get("session_id") != session_id:
                continue

            # Check project_id filter
            if project_id and payload.get("project_id") != project_id:
                continue

            # Check run_id filter
            if run_id and payload.get("run_id") != run_id:
                continue

            filtered.append(event)

        # Sort by timestamp (newest first) and limit
        filtered.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return filtered[:limit]

    def get_denied_events(
        self,
        ext_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all denied execution events

        Args:
            ext_id: Optional filter by extension ID
            limit: Maximum number of results

        Returns:
            List of denied events

        Example:
            >>> logger = AuditLogger()
            >>> denied = logger.get_denied_events(ext_id="tools.postman", limit=10)
        """
        return self.get_extension_events(
            ext_id=ext_id,
            event_type=EXT_RUN_DENIED,
            limit=limit
        )

    def get_execution_trail(
        self,
        run_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get complete execution trail for a run

        Returns all events (started, finished, denied) for a specific run.

        Args:
            run_id: Run ID

        Returns:
            List of events ordered by timestamp

        Example:
            >>> logger = AuditLogger()
            >>> trail = logger.get_execution_trail(run_id="run_123")
        """
        return self.get_extension_events(run_id=run_id, limit=50)

    def get_session_activity(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all extension activity for a session

        Args:
            session_id: Session ID
            limit: Maximum number of results

        Returns:
            List of extension events for the session

        Example:
            >>> logger = AuditLogger()
            >>> activity = logger.get_session_activity(session_id="session_123")
        """
        return self.get_extension_events(session_id=session_id, limit=limit)


# ============================================
# Global Audit Logger Instance
# ============================================

_global_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """
    Get global audit logger instance

    Returns:
        Shared AuditLogger instance
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = AuditLogger()
    return _global_logger


def reset_audit_logger():
    """Reset global audit logger (for testing)"""
    global _global_logger
    _global_logger = None
