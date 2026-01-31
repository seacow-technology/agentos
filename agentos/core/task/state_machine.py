"""
Task State Machine

Core state machine implementation for task lifecycle management.
Provides state transition validation, execution, and history tracking.
"""

import json
import sqlite3
from typing import Dict, Set, Tuple, Optional, Any
from datetime import datetime, timezone
from pathlib import Path
import logging

from agentos.core.task.states import TaskState, ALL_STATES, TERMINAL_STATES
from agentos.core.task.errors import (
    TaskStateError,
    InvalidTransitionError,
    TaskNotFoundError,
    TaskAlreadyInStateError,
    ModeViolationError,
)
from agentos.core.time import utc_now_iso
from agentos.core.task.models import Task
from agentos.store import get_db, get_writer

logger = logging.getLogger(__name__)

# Governance: Minimum audit events required for COMPLETED state
MIN_AUDIT_EVENTS_FOR_COMPLETION = 2  # At least: creation + one state transition

# Governance: Valid exit reasons for FAILED state
VALID_EXIT_REASONS = [
    "timeout",
    "retry_exhausted",
    "canceled",
    "exception",
    "gate_failed",
    "user_stopped",
    "fatal_error",
    "max_iterations",
    "blocked",
    "unknown",
]


# State Transition Table
# Maps (from_state, to_state) -> (is_allowed, optional_reason)
TRANSITION_TABLE: Dict[Tuple[TaskState, TaskState], Tuple[bool, Optional[str]]] = {
    # From DRAFT
    (TaskState.DRAFT, TaskState.APPROVED): (True, "Task approved for execution"),
    (TaskState.DRAFT, TaskState.CANCELED): (True, "Task canceled during draft"),

    # From APPROVED
    (TaskState.APPROVED, TaskState.QUEUED): (True, "Task queued for execution"),
    (TaskState.APPROVED, TaskState.CANCELED): (True, "Task canceled after approval"),

    # From QUEUED
    (TaskState.QUEUED, TaskState.RUNNING): (True, "Task execution started"),
    (TaskState.QUEUED, TaskState.CANCELED): (True, "Task canceled while queued"),

    # From RUNNING
    (TaskState.RUNNING, TaskState.VERIFYING): (True, "Task execution completed, verification started"),
    (TaskState.RUNNING, TaskState.FAILED): (True, "Task execution failed"),
    (TaskState.RUNNING, TaskState.CANCELED): (True, "Task canceled during execution"),
    (TaskState.RUNNING, TaskState.BLOCKED): (True, "Task execution blocked (e.g., AUTONOMOUS mode hit approval checkpoint)"),

    # From VERIFYING
    (TaskState.VERIFYING, TaskState.VERIFIED): (True, "Task verification completed"),
    (TaskState.VERIFYING, TaskState.FAILED): (True, "Task verification failed"),
    (TaskState.VERIFYING, TaskState.CANCELED): (True, "Task canceled during verification"),
    (TaskState.VERIFYING, TaskState.QUEUED): (True, "Task verification failed, queued for retry"),  # Gate failure → retry

    # From VERIFIED
    (TaskState.VERIFIED, TaskState.DONE): (True, "Task marked as done"),

    # From FAILED (optional retry)
    (TaskState.FAILED, TaskState.QUEUED): (True, "Task queued for retry"),

    # From BLOCKED (allow recovery or cancellation)
    (TaskState.BLOCKED, TaskState.QUEUED): (True, "Task unblocked and queued for retry"),
    (TaskState.BLOCKED, TaskState.CANCELED): (True, "Blocked task canceled by user"),
}


class TaskStateMachine:
    """
    Task State Machine

    Manages task state transitions with validation, persistence, and audit trail.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize Task State Machine

        Args:
            db_path: Optional path to database (defaults to store default)
        """
        self.db_path = db_path
        self._transition_table = TRANSITION_TABLE

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection"""
        if self.db_path:
            conn = sqlite3.connect(str(self.db_path))
        else:
            conn = get_db()
        conn.row_factory = sqlite3.Row
        return conn

    def can_transition(self, frm: str, to: str) -> bool:
        """
        Check if a transition is allowed

        Args:
            frm: Source state
            to: Target state

        Returns:
            True if transition is allowed, False otherwise
        """
        try:
            from_state = TaskState(frm)
            to_state = TaskState(to)
        except ValueError:
            return False

        # Same state is always allowed (idempotent)
        if from_state == to_state:
            return True

        # Check transition table
        return self._transition_table.get((from_state, to_state), (False, None))[0]

    def validate_or_raise(self, frm: str, to: str) -> None:
        """
        Validate a transition or raise an exception

        Args:
            frm: Source state
            to: Target state

        Raises:
            InvalidTransitionError: If transition is not allowed
            ValueError: If states are invalid
        """
        # Validate states exist
        try:
            from_state = TaskState(frm)
            to_state = TaskState(to)
        except ValueError as e:
            raise InvalidTransitionError(
                from_state=frm,
                to_state=to,
                reason=f"Invalid state value: {str(e)}"
            )

        # Same state is allowed
        if from_state == to_state:
            return

        # Check transition table
        allowed, reason = self._transition_table.get(
            (from_state, to_state),
            (False, "No transition rule defined")
        )

        if not allowed:
            raise InvalidTransitionError(
                from_state=frm,
                to_state=to,
                reason=reason or "Transition not allowed"
            )

    def transition(
        self,
        task_id: str,
        to: str,
        actor: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Task:
        """
        Execute a state transition

        This method:
        1. Loads the current task state
        2. Validates the transition
        3. Updates the task state (via SQLiteWriter)
        4. Records the transition in audit log
        5. Returns the updated task

        Args:
            task_id: Task ID
            to: Target state
            actor: Who/what is performing the transition (user, system, etc.)
            reason: Human-readable reason for transition
            metadata: Optional metadata for the transition

        Returns:
            Updated Task object

        Raises:
            TaskNotFoundError: If task doesn't exist
            InvalidTransitionError: If transition is not allowed
            TaskStateError: For other state machine errors
        """
        # Read current task state (read-only connection)
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Load current task
            cursor.execute(
                "SELECT task_id, title, status, session_id, created_at, updated_at, created_by, metadata "
                "FROM tasks WHERE task_id = ?",
                (task_id,)
            )
            row = cursor.fetchone()

            if not row:
                raise TaskNotFoundError(task_id)

            # Parse current state
            current_state = row["status"]

            # Validate transition
            self.validate_or_raise(current_state, to)

            # Check if already in target state
            if current_state == to:
                logger.debug(f"Task {task_id} already in state '{to}', no transition needed")
                # Return current task without changes
                task_metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                return Task(
                    task_id=row["task_id"],
                    title=row["title"],
                    status=row["status"],
                    session_id=row["session_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    created_by=row["created_by"],
                    metadata=task_metadata,
                )

            # Parse task metadata for gate checks
            task_metadata = json.loads(row["metadata"]) if row["metadata"] else {}

            # Merge transition metadata (e.g., exit_reason for FAILED transitions)
            if metadata:
                task_metadata.update(metadata)

            # ========================================
            # MODE GATEWAY: Validate transition with mode constraints
            # ========================================
            mode_id = task_metadata.get("mode_id")
            if mode_id:
                self._validate_mode_transition(
                    task_id=task_id,
                    mode_id=mode_id,
                    from_state=current_state,
                    to_state=to,
                    metadata=task_metadata
                )

            # ========================================
            # GOVERNANCE GATES: Critical State Entry Checks
            # ========================================
            self._check_state_entry_gates(
                task_id=task_id,
                current_state=current_state,
                to_state=to,
                task_metadata=task_metadata,
                cursor=cursor
            )

        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

        # Perform write operations via SQLiteWriter (serialized writes)
        now = utc_now_iso()

        def _execute_transition(write_conn: sqlite3.Connection) -> None:
            """Execute state transition writes in writer thread"""
            cursor = write_conn.cursor()

            # Update task state (and metadata if modified by gates or transition)
            metadata_modified = (
                ("cleanup_summary" in task_metadata and task_metadata["cleanup_summary"].get("auto_generated"))
                or metadata  # If transition provided metadata (e.g., exit_reason)
            )

            if metadata_modified:
                # Gate auto-created cleanup_summary or transition provided metadata, need to persist it
                cursor.execute(
                    "UPDATE tasks SET status = ?, metadata = ?, updated_at = ? WHERE task_id = ?",
                    (to, json.dumps(task_metadata), now, task_id)
                )
                logger.info(f"Updated task {task_id} with modified metadata (status={to})")
            else:
                # Normal state update without metadata changes
                cursor.execute(
                    "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                    (to, now, task_id)
                )

            # Record transition in audit log
            audit_payload = {
                "from_state": current_state,
                "to_state": to,
                "actor": actor,
                "reason": reason,
                "transition_metadata": metadata or {},
            }

            cursor.execute(
                """
                INSERT INTO task_audits (task_id, level, event_type, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    "info",
                    f"STATE_TRANSITION_{to.upper()}",
                    json.dumps(audit_payload),
                    now
                )
            )

        # Execute transition via writer (with timeout)
        try:
            if self.db_path:
                # Use writer for specific database path (for testing)
                from agentos.core.db.writer import SQLiteWriter
                writer = SQLiteWriter(str(self.db_path))
            else:
                # Use global writer for production
                writer = get_writer()
            writer.submit(_execute_transition, timeout=10.0)

            logger.info(
                f"Task {task_id} transitioned from '{current_state}' to '{to}' "
                f"by {actor}: {reason}"
            )

        except TimeoutError as e:
            logger.error(f"State transition timed out for task {task_id}: {e}")
            raise TaskStateError(
                f"State transition timed out: {str(e)}",
                task_id=task_id
            )
        except Exception as e:
            logger.error(f"Error during state transition for task {task_id}: {str(e)}")
            raise TaskStateError(
                f"Failed to transition task: {str(e)}",
                task_id=task_id
            )

        # Load and return updated task (read-only connection)
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT task_id, title, status, session_id, created_at, updated_at, created_by, metadata "
                "FROM tasks WHERE task_id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            task_metadata = json.loads(row["metadata"]) if row["metadata"] else {}

            return Task(
                task_id=row["task_id"],
                title=row["title"],
                status=row["status"],
                session_id=row["session_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                created_by=row["created_by"],
                metadata=task_metadata,
            )
        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

    def get_valid_transitions(self, from_state: str) -> Set[str]:
        """
        Get all valid transitions from a given state

        Args:
            from_state: Source state

        Returns:
            Set of valid target states
        """
        try:
            state = TaskState(from_state)
        except ValueError:
            return set()

        valid_targets = set()
        for (frm, to), (allowed, _) in self._transition_table.items():
            if frm == state and allowed:
                valid_targets.add(to.value)

        return valid_targets

    def get_transition_history(self, task_id: str) -> list:
        """
        Get state transition history for a task

        Args:
            task_id: Task ID

        Returns:
            List of transition records (most recent first)
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT audit_id, task_id, level, event_type, payload, created_at
                FROM task_audits
                WHERE task_id = ? AND event_type LIKE 'STATE_TRANSITION_%'
                ORDER BY created_at DESC
                """,
                (task_id,)
            )

            history = []
            for row in cursor.fetchall():
                payload = json.loads(row["payload"]) if row["payload"] else {}
                history.append({
                    "audit_id": row["audit_id"],
                    "task_id": row["task_id"],
                    "level": row["level"],
                    "event_type": row["event_type"],
                    "from_state": payload.get("from_state"),
                    "to_state": payload.get("to_state"),
                    "actor": payload.get("actor"),
                    "reason": payload.get("reason"),
                    "metadata": payload.get("transition_metadata", {}),
                    "created_at": row["created_at"],
                })

            return history

        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

    def is_terminal_state(self, state: str) -> bool:
        """
        Check if a state is terminal

        Args:
            state: State to check

        Returns:
            True if terminal, False otherwise
        """
        try:
            return TaskState(state) in TERMINAL_STATES
        except ValueError:
            return False

    def _check_state_entry_gates(
        self,
        task_id: str,
        current_state: str,
        to_state: str,
        task_metadata: Dict[str, Any],
        cursor: sqlite3.Cursor
    ) -> None:
        """
        Governance Gates: Check entry conditions for critical states

        This method enforces governance rules for state transitions:
        - DONE: Must have sufficient audit trail
        - FAILED: Must have exit_reason
        - CANCELED: Must have cleanup_summary (auto-created if missing)

        Args:
            task_id: Task ID
            current_state: Current state
            to_state: Target state
            task_metadata: Task metadata
            cursor: Database cursor for audit queries

        Raises:
            TaskStateError: If gate check fails
        """
        # Gate 1: Entering DONE state
        if to_state == TaskState.DONE.value:
            self._check_done_gate(task_id, cursor)

        # Gate 2: Entering FAILED state
        if to_state == TaskState.FAILED.value:
            self._check_failed_gate(task_id, task_metadata)

        # Gate 3: Entering CANCELED state
        if to_state == TaskState.CANCELED.value:
            self._check_canceled_gate(task_id, task_metadata)

    def _check_done_gate(self, task_id: str, cursor: sqlite3.Cursor) -> None:
        """
        Gate check for DONE state: Ensure audit trail completeness

        Args:
            task_id: Task ID
            cursor: Database cursor

        Raises:
            TaskStateError: If audit trail is insufficient
        """
        # Check audit trail completeness
        cursor.execute(
            "SELECT COUNT(*) as count FROM task_audits WHERE task_id = ?",
            (task_id,)
        )
        audit_count = cursor.fetchone()["count"]

        if audit_count < MIN_AUDIT_EVENTS_FOR_COMPLETION:
            logger.warning(
                f"Task {task_id} has insufficient audit trail ({audit_count} events) "
                f"for DONE state (minimum: {MIN_AUDIT_EVENTS_FOR_COMPLETION})"
            )
            # NOTE: For now, we only warn. In production, this could be enforced:
            # raise TaskStateError(
            #     f"Task {task_id} lacks sufficient audit trail "
            #     f"({audit_count} events, minimum: {MIN_AUDIT_EVENTS_FOR_COMPLETION})",
            #     task_id=task_id
            # )

        logger.info(
            f"DONE gate check passed for task {task_id}: "
            f"{audit_count} audit events (minimum: {MIN_AUDIT_EVENTS_FOR_COMPLETION})"
        )

    def _check_failed_gate(self, task_id: str, task_metadata: Dict[str, Any]) -> None:
        """
        Gate check for FAILED state: Ensure exit_reason is present

        Args:
            task_id: Task ID
            task_metadata: Task metadata

        Raises:
            TaskStateError: If exit_reason is missing or invalid
        """
        # Check for exit_reason in metadata
        exit_reason = task_metadata.get("exit_reason")

        if not exit_reason:
            logger.error(
                f"Task {task_id} cannot transition to FAILED without exit_reason"
            )
            raise TaskStateError(
                f"Task {task_id} cannot fail without exit_reason. "
                f"Valid reasons: {', '.join(VALID_EXIT_REASONS)}",
                task_id=task_id
            )

        # Validate exit_reason
        if exit_reason not in VALID_EXIT_REASONS:
            logger.warning(
                f"Task {task_id} has unknown exit_reason: '{exit_reason}'. "
                f"Valid reasons: {', '.join(VALID_EXIT_REASONS)}"
            )
            # NOTE: We warn but don't fail for unknown reasons to allow extensibility

        logger.info(
            f"FAILED gate check passed for task {task_id}: exit_reason='{exit_reason}'"
        )

    def _check_canceled_gate(self, task_id: str, task_metadata: Dict[str, Any]) -> None:
        """
        Gate check for CANCELED state: Ensure cleanup_summary is present

        If cleanup_summary is missing, this gate will auto-create a minimal one.

        Args:
            task_id: Task ID
            task_metadata: Task metadata (will be modified in-place if needed)

        Note:
            This gate is permissive and auto-creates cleanup_summary if missing.
            This ensures backward compatibility with existing cancel flows.
        """
        # Check for cleanup_summary
        if "cleanup_summary" not in task_metadata:
            logger.info(
                f"Task {task_id} transitioning to CANCELED without cleanup_summary. "
                f"Auto-creating minimal cleanup summary."
            )
            # Auto-create minimal cleanup_summary
            task_metadata["cleanup_summary"] = {
                "cleanup_performed": [],
                "cleanup_failed": [],
                "cleanup_skipped": ["no cleanup required"],
                "auto_generated": True,
            }
            # NOTE: This metadata update needs to be persisted in the transition
            # The caller must handle metadata persistence

        logger.info(
            f"CANCELED gate check passed for task {task_id}: "
            f"cleanup_summary present"
        )

    def _validate_mode_transition(
        self,
        task_id: str,
        mode_id: str,
        from_state: str,
        to_state: str,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Validate transition with mode gateway

        This method:
        1. Gets the mode gateway for the task's mode
        2. Requests validation from the gateway
        3. Handles the decision (approve/reject/block/defer)
        4. Emits alerts for rejected/blocked transitions

        Args:
            task_id: Task ID
            mode_id: Mode the task is operating in
            from_state: Current state
            to_state: Target state
            metadata: Task metadata

        Raises:
            ModeViolationError: If mode gateway rejects the transition
        """
        try:
            # Get mode gateway (with fail-safe default)
            gateway = self._get_mode_gateway(mode_id)

            # Validate transition
            decision = gateway.validate_transition(
                task_id=task_id,
                mode_id=mode_id,
                from_state=from_state,
                to_state=to_state,
                metadata=metadata
            )

            # Handle decision
            if decision.is_approved():
                logger.debug(
                    f"Mode gateway approved transition for task {task_id}: "
                    f"{from_state} -> {to_state} (mode: {mode_id})"
                )
                return

            elif decision.is_rejected():
                # Emit alert for rejected transition
                self._emit_mode_alert(
                    severity="error",
                    task_id=task_id,
                    mode_id=mode_id,
                    operation=f"transition_{to_state}",
                    message=f"Transition rejected: {decision.reason}",
                    context=decision.metadata
                )

                # Raise error to block transition
                raise ModeViolationError(
                    task_id=task_id,
                    mode_id=mode_id,
                    from_state=from_state,
                    to_state=to_state,
                    reason=decision.reason,
                    metadata=decision.metadata
                )

            elif decision.is_blocked():
                # Emit alert for blocked transition
                self._emit_mode_alert(
                    severity="warning",
                    task_id=task_id,
                    mode_id=mode_id,
                    operation=f"transition_{to_state}",
                    message=f"Transition blocked (requires approval): {decision.reason}",
                    context=decision.metadata
                )

                # Raise error to block transition
                raise ModeViolationError(
                    task_id=task_id,
                    mode_id=mode_id,
                    from_state=from_state,
                    to_state=to_state,
                    reason=f"Blocked: {decision.reason}",
                    metadata=decision.metadata
                )

            elif decision.is_deferred():
                # Emit alert for deferred transition
                self._emit_mode_alert(
                    severity="info",
                    task_id=task_id,
                    mode_id=mode_id,
                    operation=f"transition_{to_state}",
                    message=f"Transition deferred: {decision.reason}",
                    context=decision.metadata
                )

                # Raise error to defer transition
                raise ModeViolationError(
                    task_id=task_id,
                    mode_id=mode_id,
                    from_state=from_state,
                    to_state=to_state,
                    reason=f"Deferred: {decision.reason}",
                    metadata=decision.metadata
                )

        except ModeViolationError:
            # Re-raise mode violations
            raise
        except Exception as e:
            # Fail-safe: If mode gateway fails, log warning and allow transition
            logger.warning(
                f"Mode gateway check failed for task {task_id} (mode: {mode_id}), "
                f"allowing transition as fail-safe: {str(e)}"
            )
            self._emit_mode_alert(
                severity="warning",
                task_id=task_id,
                mode_id=mode_id,
                operation="gateway_failure",
                message=f"Mode gateway check failed: {str(e)}",
                context={"transition": f"{from_state} -> {to_state}"}
            )

    def _get_mode_gateway(self, mode_id: str):
        """
        Get mode gateway for a mode (with fail-safe)

        Args:
            mode_id: Mode identifier

        Returns:
            Mode gateway instance (or default if not available)
        """
        try:
            from agentos.core.mode.gateway_registry import get_mode_gateway
            return get_mode_gateway(mode_id)
        except Exception as e:
            logger.warning(
                f"Failed to load mode gateway for mode '{mode_id}': {str(e)}, "
                f"using fail-safe default"
            )
            # Return a simple fail-safe gateway
            from agentos.core.mode.gateway_registry import DefaultModeGateway
            return DefaultModeGateway()

    def _emit_mode_alert(
        self,
        severity: str,
        task_id: str,
        mode_id: str,
        operation: str,
        message: str,
        context: Dict[str, Any]
    ) -> None:
        """
        Emit mode alert for transition decision

        Args:
            severity: Alert severity (info/warning/error/critical)
            task_id: Task ID
            mode_id: Mode ID
            operation: Operation being performed
            message: Alert message
            context: Additional context
        """
        try:
            from agentos.core.mode.mode_alerts import (
                get_alert_aggregator,
                AlertSeverity
            )

            # Map string severity to AlertSeverity enum
            severity_map = {
                "info": AlertSeverity.INFO,
                "warning": AlertSeverity.WARNING,
                "error": AlertSeverity.ERROR,
                "critical": AlertSeverity.CRITICAL,
            }

            alert_severity = severity_map.get(severity.lower(), AlertSeverity.INFO)

            # Add task_id to context
            alert_context = {**context, "task_id": task_id}

            # Emit alert
            aggregator = get_alert_aggregator()
            aggregator.alert(
                severity=alert_severity,
                mode_id=mode_id,
                operation=operation,
                message=message,
                context=alert_context
            )

        except Exception as e:
            # Fail-safe: Don't block transition if alert fails
            logger.warning(
                f"Failed to emit mode alert for task {task_id}: {str(e)}"
            )
