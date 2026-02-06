"""File-level locking mechanism."""

from __future__ import annotations

import json
import sqlite3
import time
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console

from agentos.core.locks.exceptions import LockConflict
from agentos.core.locks.lock_token import LockToken
from agentos.core.storage.paths import component_db_path
from agentos.core.time import utc_now


console = Console()


@dataclass(frozen=True)
class FileLockInfo:
    """Information about a locked file."""

    path: str
    owner: str
    task_id: str
    run_id: int
    expires_at: float


class FileLockManager:
    """File-level lock manager (v0.3 interface)."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize file lock manager."""
        if db_path is None:
            db_path = component_db_path("agentos")
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def acquire_paths(
        self,
        task_id: str,
        holder: str,
        paths: list[str],
        ttl_seconds: int = 600,
        repo_root: str = ".",
        metadata: Optional[dict] = None,
    ) -> LockToken:
        """
        Acquire locks for multiple file paths atomically.

        Args:
            task_id: Task ID acquiring the lock
            holder: Holder identifier (agent/worker ID)
            paths: List of file paths to lock
            ttl_seconds: Lock duration in seconds (default 10 minutes)
            repo_root: Repository root path
            metadata: Optional metadata (e.g., change intent)

        Returns:
            LockToken if all locks acquired

        Raises:
            LockConflict: If any path is already locked
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = utc_now()
        expires_at = now + timedelta(seconds=ttl_seconds)
        expires_ts = expires_at.timestamp()

        try:
            # Check if any files are already locked
            locked_paths = self._check_locked(cursor, repo_root, paths, now)

            if locked_paths:
                # Get owner info for first conflict
                cursor.execute(
                    """
                    SELECT locked_by_task, locked_by_run FROM file_locks
                    WHERE repo_root = ? AND file_path = ? AND expires_at >= ?
                    LIMIT 1
                """,
                    (repo_root, locked_paths[0], now.isoformat()),
                )
                row = cursor.fetchone()
                owner = f"{row['locked_by_task']}:{row['locked_by_run']}" if row else "unknown"

                raise LockConflict(
                    resource=f"file:{locked_paths[0]}",
                    owner=owner,
                    wait=True,
                )

            # Acquire all locks
            metadata_json = json.dumps(metadata) if metadata else None
            run_id = int(time.time() * 1000)  # Use timestamp as run_id if not provided

            for file_path in paths:
                cursor.execute(
                    """
                    INSERT INTO file_locks (repo_root, file_path, locked_by_task, locked_by_run, expires_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(repo_root, file_path) DO UPDATE SET
                        locked_by_task = excluded.locked_by_task,
                        locked_by_run = excluded.locked_by_run,
                        expires_at = excluded.expires_at,
                        metadata = excluded.metadata
                """,
                    (repo_root, file_path, task_id, run_id, expires_at.isoformat(), metadata_json),
                )

            conn.commit()

            return LockToken(
                lock_id=f"files:{task_id}:{run_id}",
                task_id=task_id,
                holder=holder,
                expires_at=expires_ts,
            )

        except LockConflict:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            console.print(f"[red]Error acquiring file locks: {e}[/red]")
            raise
        finally:
            conn.close()

    def release_paths(self, token: LockToken, repo_root: str = ".") -> None:
        """
        Release locks associated with a token.

        Args:
            token: Lock token to release
            repo_root: Repository root path
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
                DELETE FROM file_locks
                WHERE repo_root = ? AND locked_by_run = ?
            """,
                (repo_root, run_id),
            )

            conn.commit()

        finally:
            conn.close()

    def get_owner(self, path: str, repo_root: str = ".") -> Optional[FileLockInfo]:
        """
        Get owner information for a locked file.

        Args:
            path: File path
            repo_root: Repository root path

        Returns:
            FileLockInfo if file is locked, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = utc_now()

        try:
            cursor.execute(
                """
                SELECT file_path, locked_by_task, locked_by_run, expires_at
                FROM file_locks
                WHERE repo_root = ? AND file_path = ? AND expires_at >= ?
            """,
                (repo_root, path, now.isoformat()),
            )

            row = cursor.fetchone()
            if not row:
                return None

            expires_at = datetime.fromisoformat(row["expires_at"]).timestamp()

            return FileLockInfo(
                path=row["file_path"],
                owner=f"{row['locked_by_task']}:{row['locked_by_run']}",
                task_id=row["locked_by_task"],
                run_id=row["locked_by_run"],
                expires_at=expires_at,
            )

        finally:
            conn.close()

    def _check_locked(
        self, cursor: sqlite3.Cursor, repo_root: str, file_paths: list[str], now: datetime
    ) -> list[str]:
        """
        Check which files are currently locked.

        Returns:
            List of locked file paths
        """
        if not file_paths:
            return []

        placeholders = ",".join("?" * len(file_paths))
        cursor.execute(
            f"""
            SELECT file_path FROM file_locks
            WHERE repo_root = ?
              AND file_path IN ({placeholders})
              AND expires_at >= ?
        """,
            [repo_root] + file_paths + [now.isoformat()],
        )

        return [row["file_path"] for row in cursor.fetchall()]


class FileLock:
    """File-level lock (compatibility wrapper - DEPRECATED)."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        task_id: Optional[str] = None,
        run_id: Optional[int] = None,
    ):
        """
        Initialize file lock manager.

        DEPRECATED: Use FileLockManager instead.

        Args:
            db_path: Database path
            task_id: Task ID (for compatibility)
            run_id: Run ID (for compatibility)
        """
        if task_id is not None or run_id is not None:
            warnings.warn(
                "FileLock(task_id=..., run_id=...) is deprecated; use FileLockManager",
                DeprecationWarning,
                stacklevel=2,
            )

        if db_path is None:
            db_path = component_db_path("agentos")

        self.db_path = db_path
        self.task_id = task_id
        self.run_id = run_id
        self._mgr = FileLockManager(db_path)
        self._token: Optional[LockToken] = None
        self._repo_root = "."

    def acquire_batch(
        self,
        file_paths: list[str],
        holder: str,
        repo_root: Optional[str] = None,
        task_id: Optional[str] = None,
        run_id: Optional[int] = None,
        duration: int = 600,
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        Acquire locks for multiple files (compatibility method).

        Args:
            file_paths: List of file paths to lock
            holder: Holder identifier
            repo_root: Repository root (optional, defaults to ".")
            task_id: Task ID (old API compatibility)
            run_id: Run ID (old API compatibility)
            duration: Lock duration in seconds
            metadata: Optional metadata

        Returns:
            True if all locks acquired, False if any conflict
        """
        actual_task_id = task_id or self.task_id or "unknown"
        actual_repo_root = repo_root or self._repo_root

        try:
            self._token = self._mgr.acquire_paths(
                task_id=actual_task_id,
                holder=holder,
                paths=file_paths,
                ttl_seconds=duration,
                repo_root=actual_repo_root,
                metadata=metadata,
            )
            return True
        except LockConflict:
            return False

    def release_batch(
        self, file_paths: list[str], repo_root: Optional[str] = None, run_id: Optional[int] = None
    ) -> None:
        """
        Release locks for multiple files (compatibility method).

        Args:
            file_paths: List of file paths (ignored, releases all from token)
            repo_root: Repository root
            run_id: Run ID (ignored, for compatibility)
        """
        if self._token:
            actual_repo_root = repo_root or self._repo_root
            self._mgr.release_paths(self._token, actual_repo_root)
            self._token = None

    def get_change_notes(self, repo_root: str, file_path: str) -> Optional[dict]:
        """
        Get change notes (metadata) for a locked file (old API compatibility).

        Args:
            repo_root: Repository root path
            file_path: File path

        Returns:
            Metadata dict or None
        """
        conn = self._mgr._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT metadata FROM file_locks
                WHERE repo_root = ? AND file_path = ?
            """,
                (repo_root, file_path),
            )

            row = cursor.fetchone()

            if row and row["metadata"]:
                return json.loads(row["metadata"])

            return None

        finally:
            conn.close()

    def get_locked_files(self, repo_root: str, run_id: Optional[int] = None) -> list[dict]:
        """
        Get list of locked files (old API compatibility).

        Args:
            repo_root: Repository root path
            run_id: Optional run ID filter

        Returns:
            List of locked file records
        """
        conn = self._mgr._get_connection()
        cursor = conn.cursor()

        try:
            if run_id:
                cursor.execute(
                    """
                    SELECT * FROM file_locks
                    WHERE repo_root = ? AND locked_by_run = ?
                """,
                    (repo_root, run_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM file_locks
                    WHERE repo_root = ?
                """,
                    (repo_root,),
                )

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        finally:
            conn.close()

    def cleanup_expired_locks(self) -> int:
        """
        Cleanup expired file locks (old API compatibility).

        Returns:
            Number of locks cleaned up
        """
        conn = self._mgr._get_connection()
        cursor = conn.cursor()

        now = utc_now()

        try:
            cursor.execute(
                """
                DELETE FROM file_locks
                WHERE expires_at < ?
            """,
                (now.isoformat(),),
            )

            cleaned = cursor.rowcount
            conn.commit()

            return cleaned

        finally:
            conn.close()
