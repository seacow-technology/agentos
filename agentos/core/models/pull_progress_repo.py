"""
Model Pull Progress Repository - Persistent storage for model download progress

This module provides CRUD operations for model pull progress tracking with:
- Persistent storage in SQLite
- Thread-safe operations via SQLiteWriter
- Support for progress updates and status transitions
- Automatic cleanup of old records
"""

import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional

from agentos.core.time import utc_now_ms
from agentos.store import get_db, get_writer

logger = logging.getLogger(__name__)


class ModelPullProgressRepo:
    """Repository for managing model pull progress"""

    def __init__(self):
        """Initialize repository"""
        self.writer = get_writer()

    def start_pull(
        self,
        model_name: str,
        pull_id: str,
        total_bytes: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Start tracking a new model pull operation

        Args:
            model_name: Model name (e.g., "llama3.2:3b")
            pull_id: Unique pull operation ID
            total_bytes: Total download size in bytes (if known)
            metadata: Additional metadata (provider, digest, etc.)

        Example:
            >>> repo = ModelPullProgressRepo()
            >>> repo.start_pull("llama3.2:3b", "pull_abc123", total_bytes=2147483648)
        """
        now_ms = utc_now_ms()

        def _insert(conn: sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO model_pull_progress (
                    model_name, pull_id, status, progress_pct,
                    total_bytes, completed_bytes, started_at, updated_at,
                    completed_at, current_step, error_message, metadata
                )
                VALUES (?, ?, 'pulling', 0.0, ?, 0, ?, ?, NULL, 'Starting download...', NULL, ?)
                """,
                (
                    model_name,
                    pull_id,
                    total_bytes,
                    now_ms,
                    now_ms,
                    json.dumps(metadata) if metadata else None,
                ),
            )
            conn.commit()

        try:
            self.writer.submit(_insert, timeout=10.0)
            logger.info(f"Started pull tracking: model={model_name}, pull_id={pull_id}")
        except Exception as e:
            logger.error(f"Failed to start pull tracking: {e}", exc_info=True)
            raise

    def update_progress(
        self,
        pull_id: str,
        progress_pct: float,
        completed_bytes: Optional[int] = None,
        current_step: Optional[str] = None,
    ) -> None:
        """
        Update progress for an ongoing pull operation

        Args:
            pull_id: Pull operation ID
            progress_pct: Progress percentage (0.0 - 100.0)
            completed_bytes: Bytes downloaded so far
            current_step: Current operation description

        Example:
            >>> repo = ModelPullProgressRepo()
            >>> repo.update_progress("pull_abc123", 45.5, 966367641, "Downloading: 45%")
        """
        now_ms = utc_now_ms()

        # Build dynamic update query
        set_clauses = ["progress_pct = ?", "updated_at = ?"]
        params = [progress_pct, now_ms]

        if completed_bytes is not None:
            set_clauses.append("completed_bytes = ?")
            params.append(completed_bytes)

        if current_step is not None:
            set_clauses.append("current_step = ?")
            params.append(current_step)

        params.append(pull_id)  # For WHERE clause

        def _update(conn: sqlite3.Connection):
            cursor = conn.cursor()
            query = f"UPDATE model_pull_progress SET {', '.join(set_clauses)} WHERE pull_id = ?"
            cursor.execute(query, params)
            conn.commit()

        try:
            self.writer.submit(_update, timeout=10.0)
            logger.debug(f"Updated pull progress: pull_id={pull_id}, progress={progress_pct}%")
        except Exception as e:
            logger.error(f"Failed to update pull progress: {e}", exc_info=True)

    def complete_pull(self, pull_id: str) -> None:
        """
        Mark a pull operation as completed

        Args:
            pull_id: Pull operation ID

        Example:
            >>> repo = ModelPullProgressRepo()
            >>> repo.complete_pull("pull_abc123")
        """
        now_ms = utc_now_ms()

        def _update(conn: sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE model_pull_progress
                SET status = 'completed',
                    progress_pct = 100.0,
                    updated_at = ?,
                    completed_at = ?,
                    current_step = 'Download complete'
                WHERE pull_id = ?
                """,
                (now_ms, now_ms, pull_id),
            )
            conn.commit()

        try:
            self.writer.submit(_update, timeout=10.0)
            logger.info(f"Completed pull: pull_id={pull_id}")
        except Exception as e:
            logger.error(f"Failed to complete pull: {e}", exc_info=True)

    def fail_pull(self, pull_id: str, error: str) -> None:
        """
        Mark a pull operation as failed

        Args:
            pull_id: Pull operation ID
            error: Error message

        Example:
            >>> repo = ModelPullProgressRepo()
            >>> repo.fail_pull("pull_abc123", "Network timeout")
        """
        now_ms = utc_now_ms()

        def _update(conn: sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE model_pull_progress
                SET status = 'failed',
                    updated_at = ?,
                    completed_at = ?,
                    error_message = ?
                WHERE pull_id = ?
                """,
                (now_ms, now_ms, error, pull_id),
            )
            conn.commit()

        try:
            self.writer.submit(_update, timeout=10.0)
            logger.warning(f"Failed pull: pull_id={pull_id}, error={error}")
        except Exception as e:
            logger.error(f"Failed to mark pull as failed: {e}", exc_info=True)

    def cancel_pull(self, pull_id: str) -> None:
        """
        Mark a pull operation as canceled

        Args:
            pull_id: Pull operation ID

        Example:
            >>> repo = ModelPullProgressRepo()
            >>> repo.cancel_pull("pull_abc123")
        """
        now_ms = utc_now_ms()

        def _update(conn: sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE model_pull_progress
                SET status = 'canceled',
                    updated_at = ?,
                    completed_at = ?
                WHERE pull_id = ?
                """,
                (now_ms, now_ms, pull_id),
            )
            conn.commit()

        try:
            self.writer.submit(_update, timeout=10.0)
            logger.info(f"Canceled pull: pull_id={pull_id}")
        except Exception as e:
            logger.error(f"Failed to cancel pull: {e}", exc_info=True)

    def get_progress(self, pull_id: str) -> Optional[Dict[str, Any]]:
        """
        Get progress information for a pull operation

        Args:
            pull_id: Pull operation ID

        Returns:
            Progress dictionary or None if not found

        Example:
            >>> repo = ModelPullProgressRepo()
            >>> progress = repo.get_progress("pull_abc123")
            >>> print(progress['status'], progress['progress_pct'])
        """
        conn = get_db()
        cursor = conn.cursor()

        try:
            row = cursor.execute(
                "SELECT * FROM model_pull_progress WHERE pull_id = ?", (pull_id,)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get pull progress {pull_id}: {e}")
            return None

    def get_progress_by_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get progress information by model name

        Args:
            model_name: Model name

        Returns:
            Progress dictionary or None if not found

        Example:
            >>> repo = ModelPullProgressRepo()
            >>> progress = repo.get_progress_by_model("llama3.2:3b")
        """
        conn = get_db()
        cursor = conn.cursor()

        try:
            row = cursor.execute(
                "SELECT * FROM model_pull_progress WHERE model_name = ?", (model_name,)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get pull progress for model {model_name}: {e}")
            return None

    def list_active_pulls(self) -> List[Dict[str, Any]]:
        """
        List all active (ongoing) pull operations

        Returns:
            List of progress dictionaries with status='pulling'

        Example:
            >>> repo = ModelPullProgressRepo()
            >>> active_pulls = repo.list_active_pulls()
            >>> print(f"Active downloads: {len(active_pulls)}")
        """
        conn = get_db()
        cursor = conn.cursor()

        try:
            rows = cursor.execute(
                """
                SELECT * FROM model_pull_progress
                WHERE status = 'pulling'
                ORDER BY started_at DESC
                """
            ).fetchall()
            return [self._row_to_dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to list active pulls: {e}")
            return []

    def list_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List all pull operations (recent first)

        Args:
            limit: Maximum number of results (default: 100)

        Returns:
            List of progress dictionaries

        Example:
            >>> repo = ModelPullProgressRepo()
            >>> all_pulls = repo.list_all(limit=50)
        """
        conn = get_db()
        cursor = conn.cursor()

        try:
            rows = cursor.execute(
                """
                SELECT * FROM model_pull_progress
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [self._row_to_dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to list pulls: {e}")
            return []

    def cleanup_old_pulls(self, max_age_ms: int) -> int:
        """
        Clean up old completed/failed pull records

        Only removes records that are completed/failed/canceled and older than max_age_ms.
        Active pulls are never removed.

        Args:
            max_age_ms: Maximum age in milliseconds (records older than this are deleted)

        Returns:
            Number of records deleted

        Example:
            >>> repo = ModelPullProgressRepo()
            >>> # Clean up records older than 1 hour (3600000 ms)
            >>> deleted = repo.cleanup_old_pulls(3600000)
            >>> print(f"Cleaned up {deleted} old records")
        """
        now_ms = utc_now_ms()
        cutoff_ms = now_ms - max_age_ms

        def _delete(conn: sqlite3.Connection) -> int:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM model_pull_progress
                WHERE status IN ('completed', 'failed', 'canceled')
                AND updated_at < ?
                """,
                (cutoff_ms,),
            )
            conn.commit()
            return cursor.rowcount

        try:
            deleted = self.writer.submit(_delete, timeout=10.0)
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old pull progress records")
            return deleted
        except Exception as e:
            logger.error(f"Failed to cleanup old pulls: {e}", exc_info=True)
            return 0

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """
        Convert SQLite row to dictionary with JSON parsing

        Args:
            row: SQLite row object

        Returns:
            Dictionary representation
        """
        result = dict(row)

        # Parse JSON metadata field
        if result.get("metadata"):
            try:
                result["metadata"] = json.loads(result["metadata"])
            except json.JSONDecodeError:
                # Keep as string if not valid JSON
                pass

        return result
