"""
Task Rollback and Undo Operations

Provides minimal viable rollback/undo capabilities with safety-first approach.
Created for Task #6: S6 - Implement minimal rollback/undo strategy.

KEY PRINCIPLES (Safety-First):
1. No arbitrary rollback (prevents history tampering)
2. Only allow safe cancellation operations:
   - APPROVED -> CANCELED (regular undo)
   - DRAFT -> CANCELED (discard draft)
   - QUEUED -> CANCELED (cancel before execution)
3. "Return to DRAFT" creates NEW draft (new task_id) to avoid history tampering
4. All operations have complete audit trail

WHAT IS NOT ALLOWED:
- Modifying completed tasks (DONE, VERIFIED)
- Reverting failed tasks without explicit retry
- Any operation that would tamper with historical records
- Direct state rollback (use state machine instead)
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from agentos.core.time import utc_now, utc_now_iso


try:
    from ulid import ULID
except ImportError:
    import uuid
    class ULID:
        @staticmethod
        def from_datetime(dt):
            return str(uuid.uuid4())

from agentos.core.task.models import Task
from agentos.core.task.states import TaskState, TERMINAL_STATES
from agentos.core.task.errors import (
    TaskStateError,
    InvalidTransitionError,
    TaskNotFoundError,
)
from agentos.core.task.state_machine import TaskStateMachine
from agentos.core.task.manager import TaskManager

logger = logging.getLogger(__name__)


class RollbackNotAllowedError(TaskStateError):
    """
    Exception raised when a rollback operation is not allowed

    This is raised when attempting operations that would violate
    the safety principles of the rollback system.
    """

    def __init__(self, task_id: str, current_state: str, reason: str):
        """
        Initialize RollbackNotAllowedError

        Args:
            task_id: Task ID
            current_state: Current task state
            reason: Reason why rollback is not allowed
        """
        message = f"Rollback not allowed from state '{current_state}': {reason}"
        super().__init__(
            message=message,
            task_id=task_id,
            current_state=current_state,
            reason=reason
        )


class TaskRollbackService:
    """
    Task Rollback Service

    Provides minimal viable rollback/undo operations with safety-first approach.
    All operations are audited and follow strict safety rules.

    Allowed Operations:
    1. Cancel draft task (DRAFT -> CANCELED)
    2. Cancel approved task (APPROVED -> CANCELED)
    3. Cancel queued task (QUEUED -> CANCELED)
    4. Create new draft from existing task (restart as new task)

    NOT Allowed:
    - Rollback completed tasks (DONE, VERIFIED)
    - Modify historical records
    - Arbitrary state changes
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize Task Rollback Service

        Args:
            db_path: Optional path to database (defaults to store default)
        """
        self.db_path = db_path
        self.task_manager = TaskManager(db_path=db_path)
        self.state_machine = TaskStateMachine(db_path=db_path)

    # =========================================================================
    # CANCELLATION OPERATIONS (Safe Rollback)
    # =========================================================================

    def cancel_draft(
        self,
        task_id: str,
        actor: str,
        reason: str = "Draft discarded",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Task:
        """
        Cancel a draft task (DRAFT -> CANCELED)

        This is the safest rollback operation - discarding a draft that
        was never approved or executed.

        Args:
            task_id: Task ID
            actor: Who is canceling the task
            reason: Reason for cancellation
            metadata: Optional metadata for the operation

        Returns:
            Updated task in CANCELED state

        Raises:
            TaskNotFoundError: If task doesn't exist
            InvalidTransitionError: If task is not in DRAFT state
            RollbackNotAllowedError: If cancellation violates safety rules
        """
        # Validate task exists and is in correct state
        task = self.task_manager.get_task(task_id)
        if not task:
            raise TaskNotFoundError(task_id)

        if task.status != TaskState.DRAFT.value:
            raise RollbackNotAllowedError(
                task_id=task_id,
                current_state=task.status,
                reason="Can only cancel tasks in DRAFT state. Use cancel_approved() for approved tasks."
            )

        # Record audit before transition
        self._record_rollback_audit(
            task_id=task_id,
            operation="cancel_draft",
            actor=actor,
            reason=reason,
            metadata=metadata
        )

        # Perform state transition
        return self.state_machine.transition(
            task_id=task_id,
            to=TaskState.CANCELED.value,
            actor=actor,
            reason=f"Draft canceled: {reason}",
            metadata=metadata
        )

    def cancel_approved(
        self,
        task_id: str,
        actor: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Task:
        """
        Cancel an approved task (APPROVED -> CANCELED)

        This cancels a task that was approved but not yet executed.
        This is safe because no execution has started.

        Args:
            task_id: Task ID
            actor: Who is canceling the task
            reason: Reason for cancellation (REQUIRED)
            metadata: Optional metadata for the operation

        Returns:
            Updated task in CANCELED state

        Raises:
            TaskNotFoundError: If task doesn't exist
            InvalidTransitionError: If task is not in APPROVED state
            RollbackNotAllowedError: If cancellation violates safety rules
        """
        # Validate task exists and is in correct state
        task = self.task_manager.get_task(task_id)
        if not task:
            raise TaskNotFoundError(task_id)

        if task.status != TaskState.APPROVED.value:
            raise RollbackNotAllowedError(
                task_id=task_id,
                current_state=task.status,
                reason="Can only cancel tasks in APPROVED state. Use cancel_queued() for queued tasks."
            )

        # Record audit before transition
        self._record_rollback_audit(
            task_id=task_id,
            operation="cancel_approved",
            actor=actor,
            reason=reason,
            metadata=metadata
        )

        # Perform state transition
        return self.state_machine.transition(
            task_id=task_id,
            to=TaskState.CANCELED.value,
            actor=actor,
            reason=f"Approved task canceled: {reason}",
            metadata=metadata
        )

    def cancel_queued(
        self,
        task_id: str,
        actor: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Task:
        """
        Cancel a queued task (QUEUED -> CANCELED)

        This cancels a task before execution starts. This is safe
        because no work has been performed yet.

        Args:
            task_id: Task ID
            actor: Who is canceling the task
            reason: Reason for cancellation (REQUIRED)
            metadata: Optional metadata for the operation

        Returns:
            Updated task in CANCELED state

        Raises:
            TaskNotFoundError: If task doesn't exist
            InvalidTransitionError: If task is not in QUEUED state
            RollbackNotAllowedError: If cancellation violates safety rules
        """
        # Validate task exists and is in correct state
        task = self.task_manager.get_task(task_id)
        if not task:
            raise TaskNotFoundError(task_id)

        if task.status != TaskState.QUEUED.value:
            raise RollbackNotAllowedError(
                task_id=task_id,
                current_state=task.status,
                reason="Can only cancel tasks in QUEUED state."
            )

        # Record audit before transition
        self._record_rollback_audit(
            task_id=task_id,
            operation="cancel_queued",
            actor=actor,
            reason=reason,
            metadata=metadata
        )

        # Perform state transition
        return self.state_machine.transition(
            task_id=task_id,
            to=TaskState.CANCELED.value,
            actor=actor,
            reason=f"Queued task canceled: {reason}",
            metadata=metadata
        )

    # =========================================================================
    # RESTART OPERATIONS (Creates New Task)
    # =========================================================================

    def create_new_draft_from_task(
        self,
        source_task_id: str,
        actor: str,
        reason: str,
        title_override: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Task:
        """
        Create a new draft task based on an existing task

        This is the ONLY way to "restart" a task. It creates a completely
        new task with a new task_id, preserving the original task's history.

        This avoids history tampering while allowing users to retry/restart work.

        Args:
            source_task_id: ID of the task to base the new draft on
            actor: Who is creating the new draft
            reason: Reason for creating new draft (REQUIRED)
            title_override: Optional new title (defaults to source task title)
            metadata: Optional metadata for the new task

        Returns:
            New task in DRAFT state

        Raises:
            TaskNotFoundError: If source task doesn't exist
        """
        # Load source task
        source_task = self.task_manager.get_task(source_task_id)
        if not source_task:
            raise TaskNotFoundError(source_task_id)

        # Create new task metadata
        new_metadata = metadata or {}
        new_metadata["source_task"] = {
            "task_id": source_task_id,
            "title": source_task.title,
            "original_status": source_task.status,
            "restart_reason": reason,
            "restarted_by": actor,
            "restarted_at": utc_now_iso(),
        }

        # Preserve original metadata if present
        if source_task.metadata:
            new_metadata["source_metadata"] = source_task.metadata

        # Create new draft task
        new_title = title_override or source_task.title
        new_task_id = str(ULID.from_datetime(utc_now()))

        # Use TaskManager to create the new draft
        # Note: This creates with status="created" (legacy) but we'll transition to DRAFT
        new_task = self.task_manager.create_task(
            title=new_title,
            session_id=source_task.session_id,
            created_by=actor,
            metadata=new_metadata,
            route_plan_json=source_task.route_plan_json,
            requirements_json=source_task.requirements_json,
            selected_instance_id=source_task.selected_instance_id,
            router_version=source_task.router_version,
        )

        # Record audit for restart operation
        self._record_rollback_audit(
            task_id=source_task_id,
            operation="restart_as_new_draft",
            actor=actor,
            reason=reason,
            metadata={
                "new_task_id": new_task.task_id,
                "new_title": new_title,
            }
        )

        # Record lineage linking to source task
        self.task_manager.add_lineage(
            task_id=new_task.task_id,
            kind="restart_source",
            ref_id=source_task_id,
            phase="creation",
            metadata={
                "restart_reason": reason,
                "restarted_by": actor,
            }
        )

        logger.info(
            f"Created new draft task {new_task.task_id} from source task {source_task_id} "
            f"by {actor}: {reason}"
        )

        return new_task

    # =========================================================================
    # VALIDATION AND QUERY OPERATIONS
    # =========================================================================

    def can_cancel(self, task_id: str) -> bool:
        """
        Check if a task can be canceled

        Args:
            task_id: Task ID

        Returns:
            True if task can be canceled, False otherwise
        """
        task = self.task_manager.get_task(task_id)
        if not task:
            return False

        # Can cancel if in DRAFT, APPROVED, or QUEUED state
        return task.status in [
            TaskState.DRAFT.value,
            TaskState.APPROVED.value,
            TaskState.QUEUED.value,
        ]

    def can_restart(self, task_id: str) -> bool:
        """
        Check if a task can be restarted (as new draft)

        Args:
            task_id: Task ID

        Returns:
            True if task can be restarted (always True if task exists)
        """
        task = self.task_manager.get_task(task_id)
        return task is not None

    def get_rollback_options(self, task_id: str) -> Dict[str, Any]:
        """
        Get available rollback options for a task

        Args:
            task_id: Task ID

        Returns:
            Dictionary with available rollback options

        Raises:
            TaskNotFoundError: If task doesn't exist
        """
        task = self.task_manager.get_task(task_id)
        if not task:
            raise TaskNotFoundError(task_id)

        options = {
            "task_id": task_id,
            "current_state": task.status,
            "can_cancel": self.can_cancel(task_id),
            "can_restart_as_new_draft": True,  # Always allowed
            "allowed_operations": [],
            "reasoning": "",
        }

        # Determine allowed operations based on state
        if task.status == TaskState.DRAFT.value:
            options["allowed_operations"] = ["cancel_draft", "restart_as_new_draft"]
            options["reasoning"] = "Draft can be canceled or restarted as new draft"
        elif task.status == TaskState.APPROVED.value:
            options["allowed_operations"] = ["cancel_approved", "restart_as_new_draft"]
            options["reasoning"] = "Approved task can be canceled or restarted as new draft"
        elif task.status == TaskState.QUEUED.value:
            options["allowed_operations"] = ["cancel_queued", "restart_as_new_draft"]
            options["reasoning"] = "Queued task can be canceled or restarted as new draft"
        elif task.status in [s.value for s in TERMINAL_STATES]:
            options["allowed_operations"] = ["restart_as_new_draft"]
            options["reasoning"] = "Terminal state - can only restart as new draft (no cancellation)"
        else:
            # RUNNING, VERIFYING, VERIFIED states
            options["allowed_operations"] = ["restart_as_new_draft"]
            options["reasoning"] = "Active/verified task - can only restart as new draft (use state_machine.cancel_task() for cancellation)"

        return options

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _record_rollback_audit(
        self,
        task_id: str,
        operation: str,
        actor: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record rollback operation in audit log

        Args:
            task_id: Task ID
            operation: Rollback operation name
            actor: Who performed the operation
            reason: Reason for the operation
            metadata: Optional metadata
        """
        audit_payload = {
            "operation": operation,
            "actor": actor,
            "reason": reason,
            "rollback_metadata": metadata or {},
            "timestamp": utc_now_iso(),
        }

        self.task_manager.add_audit(
            task_id=task_id,
            event_type=f"ROLLBACK_{operation.upper()}",
            level="info",
            payload=audit_payload
        )

        logger.info(f"Rollback audit recorded for task {task_id}: {operation} by {actor}")
