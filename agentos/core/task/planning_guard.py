"""
Planning Guard - v0.6 Soul: Planning = Pure Reasoning, Zero Side Effects

This module enforces the fundamental principle that planning phase must be
a pure reasoning phase with absolutely zero side effects.

Task #3: Planning Phase Side-Effect Prevention Mechanism

Architecture:
    - Planning phase (DRAFT state / planning mode): FORBID all side effects
    - Implementation phase (RUNNING state / implementation mode): ALLOW side effects

Phase Detection:
    1. TaskState.DRAFT → planning phase
    2. TaskState.RUNNING → implementation phase
    3. metadata.current_stage == "planning" → planning phase
    4. mode_id == "planning" → planning phase

Forbidden Operations:
    - shell: subprocess.run, os.system, os.popen, subprocess.Popen
    - file_write: open(mode='w'), Path.write_text, Path.mkdir, shutil operations
    - git: git commit, git push, git branch, git merge, git rebase
    - network: requests.*, urllib.*, socket operations, HTTP calls

Created for v0.6 validation sprint
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

from agentos.core.task.states import TaskState
from agentos.core.task.errors import PlanningSideEffectForbiddenError
from agentos.core.task.models import Task

logger = logging.getLogger(__name__)


class PlanningGuard:
    """
    Planning Guard - Enforces zero side effects in planning phase

    This is the gatekeeper that ensures planning remains a pure reasoning phase.
    """

    # Operation type categories
    SIDE_EFFECT_OPERATIONS = {
        "shell": [
            "subprocess.run",
            "subprocess.Popen",
            "subprocess.call",
            "subprocess.check_output",
            "os.system",
            "os.popen",
            "os.spawnl",
            "os.execv",
        ],
        "file_write": [
            "file.write",
            "file.open_w",
            "file.open_a",
            "Path.write_text",
            "Path.write_bytes",
            "Path.mkdir",
            "Path.touch",
            "shutil.copy",
            "shutil.move",
            "shutil.rmtree",
            "os.remove",
            "os.unlink",
            "os.rmdir",
        ],
        "git": [
            "git.commit",
            "git.push",
            "git.pull",
            "git.branch",
            "git.checkout",
            "git.merge",
            "git.rebase",
            "git.tag",
            "git.add",
            "git.rm",
        ],
        "network": [
            "http.request",
            "http.get",
            "http.post",
            "http.put",
            "http.delete",
            "requests.get",
            "requests.post",
            "socket.connect",
            "urllib.request",
            "api.call",
        ],
    }

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize Planning Guard

        Args:
            db_path: Optional database path (for potential task lookups)
        """
        self.db_path = db_path

    def is_planning_phase(
        self,
        task: Optional[Task] = None,
        task_state: Optional[str] = None,
        current_stage: Optional[str] = None,
        mode_id: Optional[str] = None,
    ) -> bool:
        """
        Determine if current context is in planning phase

        Planning phase is detected by:
        1. TaskState.DRAFT (primary signal)
        2. TaskState.APPROVED (still planning, not executing yet)
        3. metadata.current_stage == "planning"
        4. mode_id == "planning"

        Args:
            task: Optional Task object
            task_state: Optional task state string
            current_stage: Optional current stage from metadata
            mode_id: Optional mode ID

        Returns:
            True if in planning phase, False otherwise
        """
        # Check task state (primary signal)
        if task:
            task_state = task.status
            current_stage = task.get_current_stage()

        if task_state:
            # DRAFT and APPROVED are both planning phases
            if task_state in [TaskState.DRAFT.value, TaskState.APPROVED.value]:
                return True
            # RUNNING is implementation phase
            if task_state == TaskState.RUNNING.value:
                return False

        # Check current_stage metadata
        if current_stage == "planning":
            return True

        # Check mode_id
        if mode_id == "planning":
            return True

        # Default: if no clear signal, be conservative and assume implementation
        # (to avoid false positives blocking legitimate operations)
        return False

    def assert_operation_allowed(
        self,
        operation_type: str,
        operation_name: str,
        task: Optional[Task] = None,
        task_state: Optional[str] = None,
        current_stage: Optional[str] = None,
        mode_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Assert that an operation is allowed in current phase

        Raises PlanningSideEffectForbiddenError if operation is forbidden.

        Args:
            operation_type: Type of operation (shell, file_write, git, network)
            operation_name: Specific operation name
            task: Optional Task object
            task_state: Optional task state string
            current_stage: Optional current stage
            mode_id: Optional mode ID
            metadata: Optional additional metadata

        Raises:
            PlanningSideEffectForbiddenError: If operation is forbidden in planning phase
        """
        # Check if in planning phase
        if not self.is_planning_phase(task, task_state, current_stage, mode_id):
            # Not in planning phase, allow all operations
            return

        # In planning phase, check if operation is a side effect
        if self._is_side_effect_operation(operation_type, operation_name):
            # Determine current phase for error message
            phase = "planning"
            if task_state:
                phase = f"task_state={task_state}"
            elif current_stage:
                phase = f"stage={current_stage}"
            elif mode_id:
                phase = f"mode={mode_id}"

            task_id = task.task_id if task else None

            logger.error(
                f"Planning phase side effect forbidden: {operation_type}.{operation_name}",
                extra={
                    "operation_type": operation_type,
                    "operation_name": operation_name,
                    "current_phase": phase,
                    "task_id": task_id,
                }
            )

            raise PlanningSideEffectForbiddenError(
                operation_type=operation_type,
                operation_name=operation_name,
                current_phase=phase,
                task_id=task_id,
                metadata=metadata,
            )

    def _is_side_effect_operation(
        self,
        operation_type: str,
        operation_name: str
    ) -> bool:
        """
        Check if operation is a side-effect operation

        Args:
            operation_type: Type of operation
            operation_name: Specific operation name

        Returns:
            True if operation has side effects, False otherwise
        """
        if operation_type not in self.SIDE_EFFECT_OPERATIONS:
            # Unknown operation type, be conservative (assume not side effect)
            return False

        operations = self.SIDE_EFFECT_OPERATIONS[operation_type]
        return operation_name in operations

    def check_and_log(
        self,
        operation_type: str,
        operation_name: str,
        task: Optional[Task] = None,
        task_state: Optional[str] = None,
        current_stage: Optional[str] = None,
        mode_id: Optional[str] = None,
    ) -> bool:
        """
        Check if operation is allowed and log the decision

        This is a non-raising version for conditional logic.

        Args:
            operation_type: Type of operation
            operation_name: Specific operation name
            task: Optional Task object
            task_state: Optional task state string
            current_stage: Optional current stage
            mode_id: Optional mode ID

        Returns:
            True if operation is allowed, False if forbidden
        """
        try:
            self.assert_operation_allowed(
                operation_type=operation_type,
                operation_name=operation_name,
                task=task,
                task_state=task_state,
                current_stage=current_stage,
                mode_id=mode_id,
            )
            return True
        except PlanningSideEffectForbiddenError:
            return False


# Global guard instance (can be overridden for testing)
_global_guard: Optional[PlanningGuard] = None


def get_planning_guard(db_path: Optional[Path] = None) -> PlanningGuard:
    """
    Get the global planning guard instance

    Args:
        db_path: Optional database path

    Returns:
        PlanningGuard instance
    """
    global _global_guard
    if _global_guard is None:
        _global_guard = PlanningGuard(db_path=db_path)
    return _global_guard


def reset_planning_guard() -> None:
    """
    Reset the global planning guard (for testing)
    """
    global _global_guard
    _global_guard = None
