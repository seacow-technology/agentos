"""
Task State Machine Definition

Defines task states and allowed transitions for the Guardian workflow.
"""

from typing import Literal, Dict, List

# TaskState type definition
TaskState = Literal[
    "PLANNED",
    "APPROVED",
    "RUNNING",
    "VERIFYING",
    "GUARD_REVIEW",
    "VERIFIED",
    "DONE",
    "FAILED",
    "BLOCKED",
    "PAUSED",
]

# Define allowed state transitions
ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "PLANNED": ["APPROVED", "BLOCKED", "FAILED"],
    "APPROVED": ["RUNNING", "BLOCKED", "PAUSED"],
    "RUNNING": ["VERIFYING", "DONE", "FAILED", "BLOCKED", "PAUSED"],
    "VERIFYING": ["GUARD_REVIEW", "BLOCKED", "RUNNING"],
    "GUARD_REVIEW": ["VERIFIED", "BLOCKED", "RUNNING"],
    "VERIFIED": ["DONE"],
    "BLOCKED": ["RUNNING", "FAILED"],
    "PAUSED": ["RUNNING", "FAILED"],
    "FAILED": [],  # Terminal state
    "DONE": [],    # Terminal state
}


def can_transition(from_state: TaskState, to_state: TaskState) -> bool:
    """
    Check if a state transition is legal

    Args:
        from_state: Current state
        to_state: Target state

    Returns:
        True if transition is allowed, False otherwise
    """
    allowed = ALLOWED_TRANSITIONS.get(from_state, [])
    return to_state in allowed


def get_allowed_transitions(state: TaskState) -> List[str]:
    """
    Get all allowed transitions from a given state

    Args:
        state: Current state

    Returns:
        List of allowed target states
    """
    return ALLOWED_TRANSITIONS.get(state, [])
