"""
System logging components for AgentOS.

Provides a comprehensive logging infrastructure to capture, store and query
application logs with contextual information (task_id, session_id).

Components:
- context: Thread-safe context passing using ContextVars
- store: High-performance log storage (memory + optional persistence)
- handler: Log capture handler integrating with Python logging system
"""

# Import context functions (no circular dependency)
from agentos.core.logging.context import (
    set_log_context,
    get_current_task_id,
    get_current_session_id,
    clear_log_context,
)

# Lazy imports for store and handler to avoid circular dependencies
# These should be imported directly where needed
__all__ = [
    "set_log_context",
    "get_current_task_id",
    "get_current_session_id",
    "clear_log_context",
]


def __getattr__(name):
    """Lazy import for LogStore and LogCaptureHandler."""
    if name == "LogStore":
        from agentos.core.logging.store import LogStore
        return LogStore
    elif name == "LogCaptureHandler":
        from agentos.core.logging.handler import LogCaptureHandler
        return LogCaptureHandler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
