"""
Task State Definitions

Defines all task states and constants for the task state machine.
This module provides the state enumeration and related constants used
throughout the task lifecycle management system.
"""

from enum import Enum
from typing import Set


class TaskState(str, Enum):
    """
    Task State Enumeration

    Represents all possible states a task can be in during its lifecycle.
    States are organized in a directed flow from creation to completion.
    """

    # Initial state
    DRAFT = "draft"           # Task is being drafted, not yet ready for approval

    # Approval phase
    APPROVED = "approved"      # Task has been approved, ready to be queued

    # Execution phase
    QUEUED = "queued"         # Task is queued for execution
    RUNNING = "running"       # Task is currently executing

    # Verification phase
    VERIFYING = "verifying"   # Task execution completed, undergoing verification
    VERIFIED = "verified"     # Task has been verified successfully

    # Terminal states
    DONE = "done"             # Task completed successfully
    FAILED = "failed"         # Task execution failed
    CANCELED = "canceled"     # Task was canceled by user or system
    BLOCKED = "blocked"       # Task execution blocked (e.g., AUTONOMOUS mode hit approval checkpoint)

    def __str__(self) -> str:
        """String representation returns the value"""
        return self.value

    def is_terminal(self) -> bool:
        """Check if this is a terminal state"""
        return self in TERMINAL_STATES

    def is_active(self) -> bool:
        """Check if this is an active execution state"""
        return self in ACTIVE_STATES


# State groups for easy categorization
INITIAL_STATES: Set[TaskState] = {
    TaskState.DRAFT,
}

APPROVAL_STATES: Set[TaskState] = {
    TaskState.APPROVED,
}

EXECUTION_STATES: Set[TaskState] = {
    TaskState.QUEUED,
    TaskState.RUNNING,
}

VERIFICATION_STATES: Set[TaskState] = {
    TaskState.VERIFYING,
    TaskState.VERIFIED,
}

TERMINAL_STATES: Set[TaskState] = {
    TaskState.DONE,
    TaskState.FAILED,
    TaskState.CANCELED,
    TaskState.BLOCKED,
}

ACTIVE_STATES: Set[TaskState] = {
    TaskState.QUEUED,
    TaskState.RUNNING,
    TaskState.VERIFYING,
}

# All valid states
ALL_STATES: Set[TaskState] = (
    INITIAL_STATES |
    APPROVAL_STATES |
    EXECUTION_STATES |
    VERIFICATION_STATES |
    TERMINAL_STATES
)


def is_valid_state(state: str) -> bool:
    """
    Check if a state string is a valid task state

    Args:
        state: State string to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        TaskState(state)
        return True
    except ValueError:
        return False


def normalize_state(state: str) -> TaskState:
    """
    Normalize a state string to a TaskState enum

    Args:
        state: State string to normalize

    Returns:
        TaskState enum value

    Raises:
        ValueError: If state is not valid
    """
    return TaskState(state.lower())
