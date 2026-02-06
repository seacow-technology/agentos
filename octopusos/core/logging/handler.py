"""
Log capture handler integrating with Python logging system.

Intercepts ERROR and CRITICAL level logs, enriches them with context
(task_id, session_id), and stores them in LogStore.

Design Principles:
- Exception-safe: Never crash the application due to logging failures
- Non-blocking: O(1) operations, no I/O in emit()
- Context-aware: Automatically attaches task/session IDs
- Standards-compliant: Follows Python logging.Handler contract
"""

import logging
import traceback
import uuid
from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone

from agentos.core.logging.context import get_current_task_id, get_current_session_id
from agentos.core.logging.models import LogEntry

if TYPE_CHECKING:
    from agentos.core.logging.store import LogStore


class LogCaptureHandler(logging.Handler):
    """
    Custom logging handler that captures logs and stores them in LogStore.

    Automatically enriches log records with contextual information from
    ContextVars (task_id, session_id) and formats them as LogEntry objects.

    Performance:
    - emit() < 1ms (memory operations only)
    - Exception-safe (never crashes application)
    """

    def __init__(
        self,
        log_store: LogStore,
        level: int = logging.ERROR,
    ):
        """
        Initialize the log capture handler.

        Args:
            log_store: The LogStore instance to write logs to
            level: Minimum log level to capture (default: ERROR)
        """
        super().__init__(level=level)
        self.log_store = log_store

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record.

        This method is called by the logging system when a log message
        needs to be handled. It extracts context, formats the log entry,
        and stores it.

        Args:
            record: The log record from Python logging system
        """
        try:
            # Extract context from ContextVars
            task_id = get_current_task_id()
            session_id = get_current_session_id()

            # Map Python log levels to API log levels
            level_mapping = {
                logging.DEBUG: "debug",
                logging.INFO: "info",
                logging.WARNING: "warn",
                logging.ERROR: "error",
                logging.CRITICAL: "error",  # Map CRITICAL to error
            }
            level = level_mapping.get(record.levelno, "error")

            # Format timestamp (ISO 8601 with timezone)
            timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

            # Build metadata
            metadata = {
                "logger": record.name,
                "filename": record.filename,
                "lineno": record.lineno,
                "funcName": record.funcName,
                "pathname": record.pathname,
                "module": record.module,
            }

            # Add exception info if present
            if record.exc_info:
                metadata["exc_info"] = {
                    "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                    "value": str(record.exc_info[1]) if record.exc_info[1] else None,
                    "traceback": "".join(
                        traceback.format_exception(*record.exc_info)
                    ),
                }

            # Add stack info if present
            if record.stack_info:
                metadata["stack_info"] = record.stack_info

            # Format log message
            message = self.format(record) if self.formatter else record.getMessage()

            # Create LogEntry
            log_entry = LogEntry(
                id=str(uuid.uuid4()),
                level=level,
                timestamp=timestamp,
                task_id=task_id,
                session_id=session_id,
                span_id=None,  # Reserved for future use
                message=message,
                metadata=metadata,
            )

            # Store the log entry
            self.log_store.add(log_entry)

        except Exception:
            # CRITICAL: Never crash the application due to logging failures
            # Use handleError() which by default writes to stderr
            self.handleError(record)

    def close(self) -> None:
        """
        Close the handler and release resources.

        Called when the handler is removed from the logging system.
        """
        try:
            if hasattr(self.log_store, "shutdown"):
                self.log_store.shutdown()
        except Exception:
            pass  # Ignore errors during cleanup
        finally:
            super().close()
