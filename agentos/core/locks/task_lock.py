"""Task-level locking mechanism."""

from __future__ import annotations

import sqlite3
import time
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console

from agentos.core.locks.exceptions import LockConflict
from agentos.core.locks.lock_token import LockToken
from agentos.core.storage.paths import component_db_path
from agentos.core.time import utc_now, utc_now_iso


console = Console()


class TaskLockManager:
    """Task-level lock manager (v0.3 interface)."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize task lock manager."""
        if db_path is None:
            db_path = component_db_path("agentos")
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self.db_path)

    def acquire(self, task_id: str, holder: str, ttl_seconds: int = 300) -> LockToken:
        """
        Acquire task lock.

        Args:
            task_id: Task ID to lock
            holder: Worker/agent ID acquiring the lock
            ttl_seconds: Lock duration in seconds (default 5 minutes)

        Returns:
            LockToken if acquired

        Raises:
            LockConflict: If lock is already held by another holder
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row

        now = utc_now()
        expires_at = (now + timedelta(seconds=ttl_seconds)).timestamp()

        try:
            # Check if already locked
            cursor.execute(
                """
                SELECT id, lease_holder, lease_until FROM task_runs
                WHERE task_id = ? AND lease_holder IS NOT NULL AND lease_until >= ?
                ORDER BY started_at DESC LIMIT 1
            """,
                (task_id, now.isoformat()),
            )

            existing = cursor.fetchone()
            if existing and existing["lease_holder"] != holder:
                raise LockConflict(
                    resource=f"task:{task_id}",
                    owner=existing["lease_holder"],
                    wait=True,
                )

            # Try to acquire lock
            cursor.execute(
                """
                SELECT id FROM task_runs
                WHERE task_id = ? AND status IN ('QUEUED', 'WAITING_LOCK')
                ORDER BY started_at DESC LIMIT 1
            """,
                (task_id,),
            )

            row = cursor.fetchone()
            if not row:
                conn.close()
                raise ValueError(f"No queued run found for task {task_id}")

            run_id = row["id"]

            cursor.execute(
                """
                UPDATE task_runs
                SET lease_holder = ?,
                    lease_until = ?,
                    status = 'RUNNING'
                WHERE id = ?
                  AND (lease_holder IS NULL OR lease_until < ?)
                  AND status IN ('QUEUED', 'WAITING_LOCK')
            """,
                (holder, datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(), 
                 run_id, now.isoformat()),
            )

            if cursor.rowcount == 0:
                conn.commit()
                conn.close()
                raise LockConflict(resource=f"task:{task_id}", owner="unknown", wait=True)

            conn.commit()

            return LockToken(
                lock_id=f"task:{task_id}:{run_id}",
                task_id=task_id,
                holder=holder,
                expires_at=expires_at,
            )

        finally:
            conn.close()

    def renew(self, token: LockToken, ttl_seconds: int = 300) -> LockToken:
        """
        Renew lock.

        Args:
            token: Lock token to renew
            ttl_seconds: Additional duration in seconds

        Returns:
            New LockToken with updated expiry

        Raises:
            LockConflict: If lock no longer held
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = time.time()
        new_expires_at = now + ttl_seconds

        try:
            # Extract run_id from lock_id
            parts = token.lock_id.split(":")
            if len(parts) >= 3:
                run_id = int(parts[2])
            else:
                raise ValueError(f"Invalid lock_id format: {token.lock_id}")

            cursor.execute(
                """
                UPDATE task_runs
                SET lease_until = ?
                WHERE id = ? AND lease_holder = ? AND lease_until >= ?
            """,
                (
                    datetime.fromtimestamp(new_expires_at, tz=timezone.utc).isoformat(),
                    run_id,
                    token.holder,
                    utc_now_iso(),
                ),
            )

            if cursor.rowcount == 0:
                raise LockConflict(
                    resource=token.lock_id, owner=None, wait=False, message="Lock expired or lost"
                )

            conn.commit()

            return LockToken(
                lock_id=token.lock_id,
                task_id=token.task_id,
                holder=token.holder,
                expires_at=new_expires_at,
            )

        finally:
            conn.close()

    def release(self, token: LockToken) -> None:
        """
        Release task lock.

        Args:
            token: Lock token to release
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Extract run_id from lock_id
            parts = token.lock_id.split(":")
            if len(parts) >= 3:
                run_id = int(parts[2])
            else:
                raise ValueError(f"Invalid lock_id format: {token.lock_id}")

            cursor.execute(
                """
                UPDATE task_runs
                SET lease_holder = NULL,
                    lease_until = NULL,
                    status = CASE 
                        WHEN status = 'RUNNING' THEN 'QUEUED'
                        ELSE status
                    END
                WHERE id = ? AND lease_holder = ?
            """,
                (run_id, token.holder),
            )

            conn.commit()

        finally:
            conn.close()


class TaskLock:
    """Task-level lock (compatibility wrapper - DEPRECATED)."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        task_id: Optional[str] = None,
        run_id: Optional[int] = None,
    ):
        """
        Initialize task lock manager.

        DEPRECATED: Use TaskLockManager instead.

        Args:
            db_path: Database path
            task_id: Task ID (for compatibility)
            run_id: Run ID (for compatibility)
        """
        if task_id is not None or run_id is not None:
            warnings.warn(
                "TaskLock(task_id=..., run_id=...) is deprecated; use TaskLockManager",
                DeprecationWarning,
                stacklevel=2,
            )

        if db_path is None:
            db_path = component_db_path("agentos")

        self.db_path = db_path
        self.task_id = task_id
        self.run_id = run_id
        self._mgr = TaskLockManager(db_path)
        self._token: Optional[LockToken] = None

    def acquire(
        self, holder: str, lease_duration: int = 300, task_id: Optional[str] = None, 
        run_id: Optional[int] = None, worker_id: Optional[str] = None, duration: Optional[int] = None
    ) -> bool:
        """
        Acquire task lock (compatibility method).

        Args:
            holder: Worker/agent ID (preferred parameter name)
            lease_duration: Lease duration in seconds (preferred parameter name)
            task_id: Task ID (old API compatibility)
            run_id: Run ID (old API compatibility)
            worker_id: Worker ID (old API compatibility, same as holder)
            duration: Duration (old API compatibility, same as lease_duration)

        Returns:
            True if lock acquired, False otherwise
        """
        # Handle parameter aliases for backward compatibility
        actual_task_id = task_id or self.task_id
        actual_holder = worker_id or holder
        actual_duration = duration or lease_duration

        if not actual_task_id:
            raise ValueError("task_id required (set in __init__ or pass as argument)")

        try:
            self._token = self._mgr.acquire(actual_task_id, actual_holder, actual_duration)
            return True
        except LockConflict:
            return False

    def release(self, task_id: Optional[str] = None, run_id: Optional[int] = None) -> None:
        """
        Release task lock (compatibility method).

        Args:
            task_id: Task ID (ignored, for compatibility)
            run_id: Run ID (ignored, for compatibility)
        """
        if self._token:
            self._mgr.release(self._token)
            self._token = None

    def extend_lease(self, run_id: Optional[int] = None, duration: int = 300) -> bool:
        """
        Extend lease duration (compatibility method).

        Args:
            run_id: Run ID (ignored, for compatibility)
            duration: Additional duration in seconds

        Returns:
            True if extended, False if no lease or expired
        """
        if not self._token:
            return False

        try:
            self._token = self._mgr.renew(self._token, duration)
            return True
        except LockConflict:
            return False

    def get_lock_holder(self, task_id: str) -> Optional[dict]:
        """Get current lock holder for a task (old API compatibility)."""
        conn = self._mgr._get_connection()
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row

        try:
            cursor.execute(
                """
                SELECT id, lease_holder, lease_until, status
                FROM task_runs
                WHERE task_id = ? AND lease_holder IS NOT NULL
                ORDER BY started_at DESC
                LIMIT 1
            """,
                (task_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return dict(row)

        finally:
            conn.close()

    def cleanup_expired_locks(self) -> int:
        """
        Cleanup expired locks (old API compatibility).

        Returns:
            Number of locks cleaned up
        """
        conn = self._mgr._get_connection()
        cursor = conn.cursor()

        now = utc_now()

        try:
            cursor.execute(
                """
                UPDATE task_runs
                SET lease_holder = NULL,
                    lease_until = NULL,
                    status = 'FAILED',
                    error = 'Lock expired'
                WHERE lease_until < ? AND status = 'RUNNING'
            """,
                (now.isoformat(),),
            )

            cleaned = cursor.rowcount
            conn.commit()

            return cleaned

        finally:
            conn.close()
