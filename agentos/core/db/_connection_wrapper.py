"""Connection wrapper for debugging database close issues.

This module provides a wrapper around sqlite3.Connection that logs
the full stack trace when .close() is called. Use this to track down
where shared connections are being closed prematurely.

Usage:
    Replace `_thread_local.connection = conn` in registry_db.get_db()
    with `_thread_local.connection = DebugConnection(conn)`
"""

import logging
import sqlite3
import traceback
from typing import Any

logger = logging.getLogger(__name__)


class DebugConnection:
    """Wrapper that logs stack trace when close() is called on a shared connection.

    This is a transparent proxy that delegates all operations to the real connection,
    except for close() which triggers a loud error log with stack trace.
    """

    def __init__(self, real_conn: sqlite3.Connection):
        """Wrap a real connection.

        Args:
            real_conn: The actual sqlite3.Connection to wrap
        """
        self._real_conn = real_conn
        self._closed = False

        # Log where this connection was created
        creation_stack = "".join(traceback.format_stack(limit=15))
        logger.warning(
            f"[DB-TRACE] Thread-local connection CREATED\n"
            f"Thread: {__import__('threading').current_thread().name}\n"
            f"Connection ID: {id(real_conn)}\n"
            f"Creation stack:\n{creation_stack}"
        )

    def close(self):
        """Intercept close() and log stack trace."""
        if self._closed:
            logger.warning(f"[DB-TRACE] Double close detected on conn {id(self._real_conn)}")
            return

        self._closed = True

        # 🔥 抓到罪犯！打印完整调用栈
        close_stack = "".join(traceback.format_stack(limit=25))
        logger.error(
            f"🚨 [DB-TRACE] SHARED CONNECTION CLOSE DETECTED! 🚨\n"
            f"Thread: {__import__('threading').current_thread().name}\n"
            f"Connection ID: {id(self._real_conn)}\n"
            f"This is a thread-local shared connection from get_db()!\n"
            f"Closing it will break other code in the same thread.\n"
            f"\n"
            f"🔍 CLOSE CALLED FROM:\n"
            f"{close_stack}\n"
            f"\n"
            f"💡 FIX: Remove conn.close() if conn comes from get_db().\n"
            f"       Only close connections created with sqlite3.connect()."
        )

        # Actually close it (to reproduce the bug)
        self._real_conn.close()

    def __getattr__(self, name: str) -> Any:
        """Delegate all other operations to real connection."""
        return getattr(self._real_conn, name)

    def __enter__(self):
        """Support context manager protocol."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support context manager - but DON'T close on exit."""
        if exc_type is not None:
            # Rollback on exception
            try:
                self._real_conn.rollback()
            except Exception as e:
                logger.warning(f"Rollback failed: {e}")
        return False  # Don't suppress exceptions
