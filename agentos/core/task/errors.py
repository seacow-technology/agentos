"""
Task State Machine Errors

Custom exceptions for task state machine operations.
"""


class TaskStateError(Exception):
    """
    Base exception for task state machine errors

    Raised when a state machine operation fails due to invalid state,
    transition rules, or other state-related issues.
    """

    def __init__(self, message: str, task_id: str = None, **kwargs):
        """
        Initialize TaskStateError

        Args:
            message: Error message
            task_id: Optional task ID for context
            **kwargs: Additional error context
        """
        self.message = message
        self.task_id = task_id
        self.context = kwargs
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with context"""
        parts = [self.message]
        if self.task_id:
            parts.append(f"(task_id: {self.task_id})")
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"[{context_str}]")
        return " ".join(parts)


class InvalidTransitionError(TaskStateError):
    """
    Exception raised when an invalid state transition is attempted

    This error is raised when attempting to transition a task from one state
    to another state that is not allowed by the state machine rules.
    """

    def __init__(
        self,
        from_state: str,
        to_state: str,
        task_id: str = None,
        reason: str = None
    ):
        """
        Initialize InvalidTransitionError

        Args:
            from_state: Current state
            to_state: Target state (invalid)
            task_id: Optional task ID
            reason: Optional reason for why transition is invalid
        """
        self.from_state = from_state
        self.to_state = to_state

        message = f"Invalid transition from '{from_state}' to '{to_state}'"
        if reason:
            message += f": {reason}"

        super().__init__(
            message=message,
            task_id=task_id,
            from_state=from_state,
            to_state=to_state
        )


class TaskNotFoundError(TaskStateError):
    """
    Exception raised when a task is not found in the database

    This error is raised when attempting to perform a state transition
    on a task that doesn't exist.
    """

    def __init__(self, task_id: str):
        """
        Initialize TaskNotFoundError

        Args:
            task_id: ID of the task that was not found
        """
        super().__init__(
            message=f"Task not found",
            task_id=task_id
        )


class TaskAlreadyInStateError(TaskStateError):
    """
    Exception raised when attempting to transition to the current state

    This is typically not an error condition, but can be used to signal
    that no action was taken because the task is already in the target state.
    """

    def __init__(self, task_id: str, state: str):
        """
        Initialize TaskAlreadyInStateError

        Args:
            task_id: Task ID
            state: Current state (same as target state)
        """
        super().__init__(
            message=f"Task is already in state '{state}'",
            task_id=task_id,
            state=state
        )


class RetryNotAllowedError(TaskStateError):
    """
    Exception raised when retry is not allowed

    This error is raised when attempting to retry a task but retry is not
    allowed due to max retries exceeded or retry loop detection.
    """

    def __init__(
        self,
        task_id: str,
        current_state: str,
        reason: str
    ):
        """
        Initialize RetryNotAllowedError

        Args:
            task_id: Task ID
            current_state: Current state
            reason: Reason why retry is not allowed
        """
        self.current_state = current_state

        message = f"Retry not allowed: {reason}"

        super().__init__(
            message=message,
            task_id=task_id,
            current_state=current_state,
            reason=reason
        )


class ModeViolationError(TaskStateError):
    """
    Exception raised when a mode constraint is violated during transition

    This error is raised when a mode gateway rejects a task state transition
    due to mode policy violations or approval requirements.

    Note:
        This is a task-level mode violation for state transitions.
        For operation-level violations, see agentos.core.mode.mode.ModeViolationError
    """

    def __init__(
        self,
        task_id: str,
        mode_id: str,
        from_state: str,
        to_state: str,
        reason: str,
        metadata: dict = None
    ):
        """
        Initialize ModeViolationError

        Args:
            task_id: Task ID
            mode_id: Mode that rejected the transition
            from_state: Current state
            to_state: Target state (rejected)
            reason: Reason for rejection
            metadata: Optional additional context
        """
        self.mode_id = mode_id
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason

        message = (
            f"Mode '{mode_id}' rejected transition from '{from_state}' to '{to_state}': "
            f"{reason}"
        )

        super().__init__(
            message=message,
            task_id=task_id,
            mode_id=mode_id,
            from_state=from_state,
            to_state=to_state,
            metadata=metadata or {}
        )


class ChatExecutionForbiddenError(TaskStateError):
    """
    Exception raised when chat attempts to directly execute tasks

    Task #1: Chat → Execution System-Level Hard Gate

    This error is raised when the chat system attempts to directly invoke
    execution without going through the proper task workflow. Chat is only
    allowed to create tasks in DRAFT state; execution must be triggered by
    the task runner after approval and queueing.

    Architecture Rule:
        chat → ✅ create Task (DRAFT state)
        chat → ❌ direct execution (FORBIDDEN)
        task runner → ✅ execution (ALLOWED)
    """

    def __init__(
        self,
        caller_context: str,
        attempted_operation: str,
        task_id: str = None,
        metadata: dict = None
    ):
        """
        Initialize ChatExecutionForbiddenError

        Args:
            caller_context: Context of the caller (e.g., "chat_engine", "chat_handler")
            attempted_operation: Operation that was attempted (e.g., "execute_task", "call_executor")
            task_id: Optional task ID if available
            metadata: Optional additional context
        """
        self.caller_context = caller_context
        self.attempted_operation = attempted_operation

        message = (
            f"Chat system is forbidden from directly executing tasks. "
            f"Context: {caller_context}, Attempted: {attempted_operation}. "
            f"Chat can only create DRAFT tasks. Use TaskService.create_approve_queue_and_start() "
            f"or wait for task runner to execute approved tasks."
        )

        super().__init__(
            message=message,
            task_id=task_id,
            caller_context=caller_context,
            attempted_operation=attempted_operation,
            metadata=metadata or {}
        )


class PlanningSideEffectForbiddenError(TaskStateError):
    """
    Exception raised when planning phase attempts side-effect operations

    Task #3: Planning Phase Side-Effect Prevention

    This error is raised when the task is in planning phase (DRAFT state or
    planning mode) and attempts to execute operations with side effects.

    Architecture Rule (v0.6 Soul):
        planning phase → ✅ pure reasoning (read-only)
        planning phase → ❌ side effects (FORBIDDEN)
        implementation phase → ✅ side effects (ALLOWED)

    Forbidden operations in planning phase:
        - Shell execution (os.system, subprocess, etc.)
        - File write operations (create, update, delete files)
        - Git operations (commit, push, branch, etc.)
        - Network calls (HTTP requests, API calls, etc.)
    """

    def __init__(
        self,
        operation_type: str,
        operation_name: str,
        current_phase: str,
        task_id: str = None,
        metadata: dict = None
    ):
        """
        Initialize PlanningSideEffectForbiddenError

        Args:
            operation_type: Type of operation (shell, file_write, git, network)
            operation_name: Specific operation name (e.g., "subprocess.run", "file.write")
            current_phase: Current task phase (planning, implementation)
            task_id: Optional task ID if available
            metadata: Optional additional context
        """
        self.operation_type = operation_type
        self.operation_name = operation_name
        self.current_phase = current_phase

        message = (
            f"Planning phase forbids side-effect operations. "
            f"Operation: {operation_type}.{operation_name}, "
            f"Current phase: {current_phase}. "
            f"Planning = pure reasoning (zero side effects). "
            f"Only implementation phase can execute side effects."
        )

        super().__init__(
            message=message,
            task_id=task_id,
            operation_type=operation_type,
            operation_name=operation_name,
            current_phase=current_phase,
            metadata=metadata or {}
        )


class SpecNotFrozenError(TaskStateError):
    """
    Exception raised when attempting to execute a task with unfrozen spec

    Task #4: Execution Frozen Plan Validation

    This error is raised when the executor attempts to execute a task that has
    not had its specification frozen (spec_frozen = 0). Execution can only
    proceed with frozen specifications to ensure traceability and auditability.

    Architecture Rule (v0.6 Frozen Plan):
        spec_frozen = 0 → ❌ execution blocked (FORBIDDEN)
        spec_frozen = 1 → ✅ execution allowed (VALID)

    Enforcement:
        - Executor must check spec_frozen before execution
        - Audit log must record rejection reason
        - Clear error message guides user to freeze spec first
    """

    def __init__(
        self,
        task_id: str,
        reason: str = "Task specification must be frozen before execution",
        metadata: dict = None
    ):
        """
        Initialize SpecNotFrozenError

        Args:
            task_id: Task ID that attempted execution
            reason: Reason for rejection (default provided)
            metadata: Optional additional context
        """
        self.reason = reason

        message = (
            f"Task specification is not frozen. "
            f"Execution requires spec_frozen = 1 (v0.6 constraint). "
            f"Please freeze the task specification before executing. "
            f"Reason: {reason}"
        )

        super().__init__(
            message=message,
            task_id=task_id,
            reason=reason,
            metadata=metadata or {}
        )
