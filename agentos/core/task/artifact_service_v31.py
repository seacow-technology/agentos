"""Task Artifact Service (v0.31)

Provides high-level task artifact operations for v0.4 Project-Aware Task OS.
Maps to task_artifacts table in schema_v31.

Created for Task #3 Phase 2: Core Service Implementation
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from agentos.core.time import utc_now, utc_now_iso


try:
    from ulid import ULID
except ImportError:
    import uuid

    class ULID:
        @staticmethod
        def from_datetime(dt):
            return str(uuid.uuid4())

from agentos.schemas.v31_models import TaskArtifact
from agentos.core.project.errors import (
    ArtifactNotFoundError,
    InvalidKindError,
    UnsafePathError,
    ArtifactPathNotFoundError,
)
from agentos.core.task.errors import TaskNotFoundError
from agentos.core.project.path_utils import validate_artifact_path
from agentos.store import get_db, get_writer

logger = logging.getLogger(__name__)


# Valid artifact kinds
VALID_KINDS = ["file", "dir", "url", "log", "report"]


class ArtifactService:
    """Task artifact management service

    Provides business-level operations for task artifact tracking.
    All database writes go through SQLiteWriter for concurrency safety.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize ArtifactService

        Args:
            db_path: Optional path to database (defaults to store default)
        """
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection (read-only)"""
        if self.db_path:
            conn = sqlite3.connect(str(self.db_path))
        else:
            conn = get_db()
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # TASK ARTIFACT CRUD
    # =========================================================================

    def register_artifact(
        self,
        task_id: str,
        kind: str,
        path: str,
        display_name: str = None,
        hash: str = None,
        size_bytes: int = None,
    ) -> TaskArtifact:
        """Register a task artifact

        Args:
            task_id: Task ID
            kind: Artifact kind (file/dir/url/log/report)
            path: Artifact path (local path or URL)
            display_name: Optional display name
            hash: Optional content hash (e.g., sha256:abc123)
            size_bytes: Optional file size in bytes

        Returns:
            TaskArtifact object

        Raises:
            TaskNotFoundError: If task doesn't exist
            InvalidKindError: If kind is invalid
            UnsafePathError: If path is unsafe
            ArtifactPathNotFoundError: If file/dir doesn't exist
        """
        # Validate kind
        if kind not in VALID_KINDS:
            raise InvalidKindError(kind)

        # Validate path
        is_valid, error_msg = validate_artifact_path(kind, path)
        if not is_valid:
            raise UnsafePathError(path, error_msg)

        # Check if file/dir exists (for non-URL kinds)
        if kind in ("file", "dir") and not path.startswith("http"):
            try:
                path_obj = Path(path)
                if not path_obj.exists():
                    raise ArtifactPathNotFoundError(path)
            except (ValueError, OSError):
                pass  # Path validation already done above

        # Generate artifact ID
        artifact_id = str(ULID.from_datetime(utc_now()))
        now = utc_now_iso()

        # Define write function
        def _write_artifact(conn):
            cursor = conn.cursor()

            # Check task exists
            cursor.execute("SELECT task_id FROM tasks WHERE task_id = ?", (task_id,))
            if not cursor.fetchone():
                raise TaskNotFoundError(task_id)

            # Insert artifact
            cursor.execute(
                """
                INSERT INTO task_artifacts (artifact_id, task_id, kind, path, display_name, hash, size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    task_id,
                    kind,
                    path,
                    display_name,
                    hash,
                    size_bytes,
                    now,
                ),
            )

            logger.info(f"Registered artifact {artifact_id} for task {task_id}: {kind} {path}")
            return artifact_id

        # Submit write operation
        writer = get_writer()
        try:
            result_id = writer.submit(_write_artifact, timeout=10.0)
        except Exception as e:
            logger.error(f"Failed to register artifact: {e}", exc_info=True)
            raise

        # Return artifact object
        return TaskArtifact(
            artifact_id=artifact_id,
            task_id=task_id,
            kind=kind,
            path=path,
            display_name=display_name,
            hash=hash,
            size_bytes=size_bytes,
            created_at=now,
        )

    def get_artifact(self, artifact_id: str) -> Optional[TaskArtifact]:
        """Get artifact by ID

        Args:
            artifact_id: Artifact ID

        Returns:
            TaskArtifact or None if not found
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT artifact_id, task_id, kind, path, display_name, hash, size_bytes, created_at, metadata
                FROM task_artifacts
                WHERE artifact_id = ?
                """,
                (artifact_id,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            return TaskArtifact.from_db_row(dict(row))
        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

    def list_artifacts(
        self,
        task_id: str = None,
        kind: str = None,
        limit: int = 100,
    ) -> List[TaskArtifact]:
        """List artifacts, optionally filtered by task and/or kind

        Args:
            task_id: Optional task ID filter
            kind: Optional kind filter
            limit: Maximum number of artifacts to return

        Returns:
            List of TaskArtifact objects
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # Build query dynamically
            query = """
                SELECT artifact_id, task_id, kind, path, display_name, hash, size_bytes, created_at, metadata
                FROM task_artifacts
                WHERE 1=1
            """
            params = []

            if task_id:
                query += " AND task_id = ?"
                params.append(task_id)

            if kind:
                query += " AND kind = ?"
                params.append(kind)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [TaskArtifact.from_db_row(dict(row)) for row in rows]
        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

    def delete_artifact(self, artifact_id: str) -> bool:
        """Delete artifact record (doesn't delete actual file)

        Args:
            artifact_id: Artifact ID

        Returns:
            True if deleted

        Raises:
            ArtifactNotFoundError: If artifact doesn't exist

        Note:
            This only deletes the database record. The actual file/directory
            is NOT deleted from the filesystem.
        """

        def _write_delete(conn):
            cursor = conn.cursor()

            # Check artifact exists
            cursor.execute(
                "SELECT artifact_id FROM task_artifacts WHERE artifact_id = ?",
                (artifact_id,),
            )
            if not cursor.fetchone():
                raise ArtifactNotFoundError(artifact_id)

            # Delete artifact
            cursor.execute("DELETE FROM task_artifacts WHERE artifact_id = ?", (artifact_id,))

            logger.info(f"Deleted artifact record: {artifact_id}")
            return True

        # Submit write operation
        writer = get_writer()
        try:
            result = writer.submit(_write_delete, timeout=10.0)
            return result
        except Exception as e:
            logger.error(f"Failed to delete artifact: {e}", exc_info=True)
            raise

    # =========================================================================
    # ARTIFACT PATH VALIDATION
    # =========================================================================

    def validate_artifact_path(self, kind: str, path: str) -> Tuple[bool, str]:
        """Validate artifact path

        Args:
            kind: Artifact kind (file/dir/url/log/report)
            path: Path or URL to validate

        Returns:
            (is_valid, error_message)
                - is_valid: True if path is valid, False otherwise
                - error_message: Error message if invalid, empty string if valid

        For file/dir:
            - Must be absolute or relative (no ..)
            - Must not contain path traversal
            - Must exist

        For url:
            - Must be valid URL
        """
        return validate_artifact_path(kind, path)
