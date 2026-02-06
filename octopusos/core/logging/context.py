"""
Context management for system logs using Python ContextVars.

ContextVars provide thread-safe and async-safe context passing without
global state pollution. Each request/task can have its own isolated context.

Usage:
    # In middleware/request handler
    set_log_context(task_id="task_123", session_id="sess_456")

    # Anywhere in the application
    task_id = get_current_task_id()  # Returns "task_123"
    session_id = get_current_session_id()  # Returns "sess_456"

    # At request end
    clear_log_context()
"""

from contextvars import ContextVar
from typing import Optional


# Context variables for tracking task and session IDs
_task_id_var: ContextVar[Optional[str]] = ContextVar("task_id", default=None)
_session_id_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)


def set_log_context(
    task_id: Optional[str] = None, session_id: Optional[str] = None
) -> None:
    """
    Set the logging context for the current execution context.

    This should be called at the beginning of request processing to attach
    contextual information to all logs generated during the request.

    Args:
        task_id: The ID of the task being executed
        session_id: The ID of the user session
    """
    if task_id is not None:
        _task_id_var.set(task_id)
    if session_id is not None:
        _session_id_var.set(session_id)


def get_current_task_id() -> Optional[str]:
    """
    Get the task_id from the current execution context.

    Returns:
        The current task_id, or None if not set
    """
    return _task_id_var.get()


def get_current_session_id() -> Optional[str]:
    """
    Get the session_id from the current execution context.

    Returns:
        The current session_id, or None if not set
    """
    return _session_id_var.get()


def clear_log_context() -> None:
    """
    Clear the logging context for the current execution context.

    This should be called at the end of request processing to prevent
    context leakage.
    """
    _task_id_var.set(None)
    _session_id_var.set(None)
