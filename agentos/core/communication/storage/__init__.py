"""Storage backends for communication audit data.

This module provides storage implementations for persisting
communication evidence and audit logs.
"""

from agentos.core.communication.storage.sqlite_store import SQLiteStore

__all__ = [
    "SQLiteStore",
]
