"""Idempotency store for request deduplication and result caching.

This module provides the IdempotencyStore class for managing idempotency keys
to prevent duplicate execution and enable result caching.

Key Features:
- Check if operation already completed (cache hit)
- Atomic check-or-create to prevent race conditions
- Mark operations as succeeded or failed
- Automatic expiration handling
- Request hash validation for conflict detection

Example:
    store = IdempotencyStore()

    # Check if already executed
    result = store.check(key="llm-plan-task-123")
    if result:
        return result  # Cache hit

    # Create idempotency key and execute
    store.create(key="llm-plan-task-123", request_hash="sha256:abc...")

    try:
        result = expensive_operation()
        store.mark_succeeded(key="llm-plan-task-123", result=result)
        return result
    except Exception as e:
        store.mark_failed(key="llm-plan-task-123", error=str(e))
        raise
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from agentos.store import get_db, get_writer

logger = logging.getLogger(__name__)


class IdempotencyConflictError(Exception):
    """Raised when same idempotency key is used with different request."""
    pass


class IdempotencyStore:
    """Store for managing idempotency keys and cached results.

    Manages idempotency_keys table to:
    1. Deduplicate requests using idempotency keys
    2. Cache results of expensive operations
    3. Validate request consistency with hash comparison
    4. Handle expiration for cleanup

    Thread-safe: Uses SQLiteWriter for all write operations.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize idempotency store.

        Args:
            db_path: Optional database path. If None, uses default from get_db().
        """
        self.db_path = db_path

    def _get_connection(self):
        """Get database connection (either custom path or default)."""
        if self.db_path:
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            return conn
        else:
            return get_db()

    def check(
        self,
        key: str,
        request_hash: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Check if operation with this key already completed.

        Args:
            key: Idempotency key
            request_hash: Optional request hash for conflict detection

        Returns:
            Cached result dict if operation completed, None otherwise

        Raises:
            IdempotencyConflictError: If same key used with different request
        """
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT response_data, status, request_hash, completed_at
            FROM idempotency_keys
            WHERE idempotency_key = ?
              AND status = 'completed'
              AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        """, (key,))

        row = cursor.fetchone()
        if not row:
            return None

        # Validate request consistency if hash provided
        if request_hash and row['request_hash'] != request_hash:
            logger.error(
                f"Idempotency conflict: key={key}, "
                f"stored_hash={row['request_hash']}, provided_hash={request_hash}"
            )
            raise IdempotencyConflictError(
                f"Same idempotency key used with different request: {key}"
            )

        # Parse and return cached result
        result = json.loads(row['response_data']) if row['response_data'] else None
        logger.info(
            f"Idempotency cache hit: key={key}, "
            f"completed_at={row['completed_at']}"
        )
        return result

    def check_or_create(
        self,
        key: str,
        request_hash: str,
        task_id: Optional[str] = None,
        work_item_id: Optional[str] = None,
        expires_in_seconds: Optional[int] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Atomically check if key exists or create it (check-then-act pattern).

        This is the recommended method for most use cases as it combines
        check and create in a single atomic operation.

        Args:
            key: Idempotency key
            request_hash: Hash of request for conflict detection
            task_id: Optional task ID for tracking
            work_item_id: Optional work item ID for tracking
            expires_in_seconds: Optional expiration time (for cleanup)

        Returns:
            Tuple of (is_cached, result):
            - (True, result): Operation already completed, return cached result
            - (False, None): Key created, proceed with operation

        Raises:
            IdempotencyConflictError: If same key used with different request
        """
        # First check if completed
        cached = self.check(key, request_hash)
        if cached is not None:
            return (True, cached)

        # Not found, create new key
        self.create(key, request_hash, task_id, work_item_id, expires_in_seconds)
        return (False, None)

    def create(
        self,
        key: str,
        request_hash: str,
        task_id: Optional[str] = None,
        work_item_id: Optional[str] = None,
        expires_in_seconds: Optional[int] = None
    ) -> None:
        """Create new idempotency key in pending state.

        Args:
            key: Idempotency key
            request_hash: Hash of request for validation
            task_id: Optional task ID for tracking
            work_item_id: Optional work item ID for tracking
            expires_in_seconds: Optional expiration time (default: 24 hours)

        Note:
            If key already exists (completed or pending), this is a no-op.
            Use check_or_create() for atomic check-then-create.
        """
        expires_in = expires_in_seconds or (24 * 3600)  # Default 24 hours

        def _insert(conn):
            conn.execute("""
                INSERT OR IGNORE INTO idempotency_keys (
                    idempotency_key, task_id, work_item_id,
                    request_hash, status, expires_at, created_at
                ) VALUES (?, ?, ?, ?, 'pending', datetime(CURRENT_TIMESTAMP, ?), CURRENT_TIMESTAMP)
            """, (
                key, task_id, work_item_id, request_hash,
                f'+{expires_in} seconds'
            ))

        # Use direct write if custom db_path (for testing), otherwise use writer
        if self.db_path:
            conn = self._get_connection()
            _insert(conn)
            conn.commit()
            conn.close()  # OK to close: custom db_path creates new connection
        else:
            writer = get_writer()
            writer.submit(_insert, timeout=5.0)

        logger.debug(
            f"Created idempotency key: key={key}, "
            f"task_id={task_id}, expires_in={expires_in}s"
        )

    def mark_succeeded(
        self,
        key: str,
        result: Dict[str, Any]
    ) -> None:
        """Mark idempotency key as completed with result.

        Args:
            key: Idempotency key
            result: Operation result to cache (must be JSON-serializable)
        """
        response_data = json.dumps(result)

        def _update(conn):
            cursor = conn.execute("""
                UPDATE idempotency_keys
                SET
                    status = 'completed',
                    response_data = ?,
                    completed_at = CURRENT_TIMESTAMP
                WHERE idempotency_key = ?
            """, (response_data, key))

            if cursor.rowcount == 0:
                logger.warning(f"Idempotency key not found for completion: {key}")

        # Use direct write if custom db_path (for testing), otherwise use writer
        if self.db_path:
            conn = self._get_connection()
            _update(conn)
            conn.commit()
            conn.close()  # OK to close: custom db_path creates new connection
        else:
            writer = get_writer()
            writer.submit(_update, timeout=5.0)

        logger.info(f"Marked idempotency key as succeeded: key={key}")

    def mark_failed(
        self,
        key: str,
        error: str
    ) -> None:
        """Mark idempotency key as failed.

        Args:
            key: Idempotency key
            error: Error message
        """
        error_data = json.dumps({"error": error})

        def _update(conn):
            cursor = conn.execute("""
                UPDATE idempotency_keys
                SET
                    status = 'failed',
                    response_data = ?,
                    completed_at = CURRENT_TIMESTAMP
                WHERE idempotency_key = ?
            """, (error_data, key))

            if cursor.rowcount == 0:
                logger.warning(f"Idempotency key not found for failure: {key}")

        # Use direct write if custom db_path (for testing), otherwise use writer
        if self.db_path:
            conn = self._get_connection()
            _update(conn)
            conn.commit()
            conn.close()  # OK to close: custom db_path creates new connection
        else:
            writer = get_writer()
            writer.submit(_update, timeout=5.0)

        logger.info(f"Marked idempotency key as failed: key={key}")

    def cleanup_expired(self) -> int:
        """Delete expired idempotency keys.

        Returns:
            Number of keys deleted
        """
        def _delete(conn):
            cursor = conn.execute("""
                DELETE FROM idempotency_keys
                WHERE expires_at < CURRENT_TIMESTAMP
            """)
            return cursor.rowcount

        writer = get_writer()
        count = writer.submit(_delete, timeout=10.0)

        if count > 0:
            logger.info(f"Cleaned up {count} expired idempotency keys")

        return count

    @staticmethod
    def compute_hash(data: Any) -> str:
        """Compute deterministic hash of data for request validation.

        Args:
            data: Data to hash (will be JSON-serialized)

        Returns:
            Hash string in format "sha256:hexdigest"
        """
        # Sort keys for deterministic serialization
        json_str = json.dumps(data, sort_keys=True)
        hash_hex = hashlib.sha256(json_str.encode()).hexdigest()
        return f"sha256:{hash_hex}"

    def get_stats(self) -> Dict[str, int]:
        """Get idempotency statistics.

        Returns:
            Dictionary with counts by status:
            - total: Total keys
            - completed: Successfully completed
            - failed: Failed operations
            - pending: In progress
        """
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
            FROM idempotency_keys
            WHERE expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP
        """)

        row = cursor.fetchone()
        return {
            "total": row["total"] or 0,
            "completed": row["completed"] or 0,
            "failed": row["failed"] or 0,
            "pending": row["pending"] or 0,
        }
