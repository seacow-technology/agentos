"""Task Binding Service

Provides high-level task binding operations for v0.4 Project-Aware Task OS.

Created for Task #3 Phase 2: Core Service Implementation
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agentos.schemas.v31_models import TaskBinding
from agentos.core.time import utc_now_iso
from agentos.core.project.errors import (
    BindingNotFoundError,
    BindingAlreadyExistsError,
    InvalidWorkdirError,
    BindingValidationError,
    ProjectNotFoundError,
    RepoNotFoundError,
    RepoNotInProjectError,
)
from agentos.core.task.errors import TaskNotFoundError
from agentos.core.project.path_utils import validate_relative_path
from agentos.store import get_db, get_writer

logger = logging.getLogger(__name__)


class BindingService:
    """Task binding management service

    Provides business-level operations for task-project-repo binding.
    All database writes go through SQLiteWriter for concurrency safety.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize BindingService

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
    # TASK BINDING CRUD
    # =========================================================================

    def create_binding(
        self,
        task_id: str,
        project_id: str,
        repo_id: str = None,
        workdir: str = None,
    ) -> TaskBinding:
        """Create task binding

        Args:
            task_id: Task ID
            project_id: Project ID
            repo_id: Optional repository ID
            workdir: Optional working directory (relative path)

        Returns:
            TaskBinding object

        Raises:
            TaskNotFoundError: If task doesn't exist
            ProjectNotFoundError: If project doesn't exist
            RepoNotFoundError: If repo_id provided but doesn't exist
            RepoNotInProjectError: If repo not in project
            BindingAlreadyExistsError: If task already has binding
            InvalidWorkdirError: If workdir is unsafe
        """
        # Validate workdir
        if workdir:
            is_valid, error_msg = validate_relative_path(workdir)
            if not is_valid:
                raise InvalidWorkdirError(workdir, error_msg)

        now = utc_now_iso()

        # Define write function
        def _write_binding(conn):
            cursor = conn.cursor()

            # Check task exists
            cursor.execute("SELECT task_id FROM tasks WHERE task_id = ?", (task_id,))
            if not cursor.fetchone():
                raise TaskNotFoundError(task_id)

            # Check project exists
            cursor.execute("SELECT project_id FROM projects WHERE project_id = ?", (project_id,))
            if not cursor.fetchone():
                raise ProjectNotFoundError(project_id)

            # Check repo exists and belongs to project (if repo_id provided)
            if repo_id:
                cursor.execute(
                    "SELECT project_id FROM repos WHERE repo_id = ?",
                    (repo_id,),
                )
                repo_row = cursor.fetchone()
                if not repo_row:
                    raise RepoNotFoundError(repo_id)

                if repo_row["project_id"] != project_id:
                    raise RepoNotInProjectError(repo_id, project_id)

            # Check if binding already exists
            cursor.execute("SELECT task_id FROM task_bindings WHERE task_id = ?", (task_id,))
            if cursor.fetchone():
                raise BindingAlreadyExistsError(task_id)

            # Insert binding
            cursor.execute(
                """
                INSERT INTO task_bindings (task_id, project_id, repo_id, workdir, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, project_id, repo_id, workdir, now),
            )

            # Also update tasks.project_id for backward compatibility
            cursor.execute(
                "UPDATE tasks SET project_id = ?, updated_at = ? WHERE task_id = ?",
                (project_id, now, task_id),
            )

            logger.info(f"Created binding for task {task_id} to project {project_id}")
            return task_id

        # Submit write operation
        writer = get_writer()
        try:
            writer.submit(_write_binding, timeout=10.0)
        except Exception as e:
            logger.error(f"Failed to create binding: {e}", exc_info=True)
            raise

        # Return binding object
        return TaskBinding(
            task_id=task_id,
            project_id=project_id,
            repo_id=repo_id,
            workdir=workdir,
            created_at=now,
        )

    def get_binding(self, task_id: str) -> Optional[TaskBinding]:
        """Get binding for task

        Args:
            task_id: Task ID

        Returns:
            TaskBinding or None if not found
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT task_id, project_id, repo_id, workdir, created_at, metadata
                FROM task_bindings
                WHERE task_id = ?
                """,
                (task_id,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            return TaskBinding.from_db_row(dict(row))
        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

    def update_binding(
        self,
        task_id: str,
        project_id: str = None,
        repo_id: str = None,
        workdir: str = None,
    ) -> TaskBinding:
        """Update existing binding (re-validate)

        Args:
            task_id: Task ID
            project_id: Optional new project ID
            repo_id: Optional new repo ID (or None to clear)
            workdir: Optional new workdir (or None to clear)

        Returns:
            Updated TaskBinding

        Raises:
            BindingNotFoundError: If binding doesn't exist
            ProjectNotFoundError: If new project doesn't exist
            RepoNotFoundError: If new repo doesn't exist
            RepoNotInProjectError: If new repo not in new project
            InvalidWorkdirError: If new workdir is unsafe
        """
        # Validate workdir if provided
        if workdir:
            is_valid, error_msg = validate_relative_path(workdir)
            if not is_valid:
                raise InvalidWorkdirError(workdir, error_msg)

        now = utc_now_iso()

        # Define write function
        def _write_update(conn):
            cursor = conn.cursor()

            # Check binding exists
            cursor.execute(
                "SELECT project_id FROM task_bindings WHERE task_id = ?",
                (task_id,),
            )
            if not cursor.fetchone():
                raise BindingNotFoundError(task_id)

            # Check new project exists (if changing)
            if project_id:
                cursor.execute("SELECT project_id FROM projects WHERE project_id = ?", (project_id,))
                if not cursor.fetchone():
                    raise ProjectNotFoundError(project_id)

            # Check repo exists and belongs to project (if provided)
            if repo_id:
                cursor.execute(
                    "SELECT project_id FROM repos WHERE repo_id = ?",
                    (repo_id,),
                )
                repo_row = cursor.fetchone()
                if not repo_row:
                    raise RepoNotFoundError(repo_id)

                # Use new project_id if provided, otherwise get current
                target_project_id = project_id
                if not target_project_id:
                    cursor.execute(
                        "SELECT project_id FROM task_bindings WHERE task_id = ?",
                        (task_id,),
                    )
                    target_project_id = cursor.fetchone()["project_id"]

                if repo_row["project_id"] != target_project_id:
                    raise RepoNotInProjectError(repo_id, target_project_id)

            # Build update query dynamically
            updates = []
            params = []

            if project_id is not None:
                updates.append("project_id = ?")
                params.append(project_id)

            if repo_id is not None:
                updates.append("repo_id = ?")
                params.append(repo_id)

            if workdir is not None:
                updates.append("workdir = ?")
                params.append(workdir)

            if not updates:
                # Nothing to update
                return task_id

            params.append(task_id)

            query = f"UPDATE task_bindings SET {', '.join(updates)} WHERE task_id = ?"
            cursor.execute(query, params)

            # Also update tasks.project_id if project changed
            if project_id:
                cursor.execute(
                    "UPDATE tasks SET project_id = ?, updated_at = ? WHERE task_id = ?",
                    (project_id, now, task_id),
                )

            logger.info(f"Updated binding for task {task_id}")
            return task_id

        # Submit write operation
        writer = get_writer()
        try:
            writer.submit(_write_update, timeout=10.0)
        except Exception as e:
            logger.error(f"Failed to update binding: {e}", exc_info=True)
            raise

        # Fetch and return updated binding
        return self.get_binding(task_id)

    def delete_binding(self, task_id: str) -> bool:
        """Delete binding (rarely used)

        Args:
            task_id: Task ID

        Returns:
            True if deleted

        Raises:
            BindingNotFoundError: If binding doesn't exist
        """

        def _write_delete(conn):
            cursor = conn.cursor()

            # Check binding exists
            cursor.execute("SELECT task_id FROM task_bindings WHERE task_id = ?", (task_id,))
            if not cursor.fetchone():
                raise BindingNotFoundError(task_id)

            # Delete binding
            cursor.execute("DELETE FROM task_bindings WHERE task_id = ?", (task_id,))

            logger.info(f"Deleted binding for task {task_id}")
            return True

        # Submit write operation
        writer = get_writer()
        try:
            result = writer.submit(_write_delete, timeout=10.0)
            return result
        except Exception as e:
            logger.error(f"Failed to delete binding: {e}", exc_info=True)
            raise

    # =========================================================================
    # BINDING VALIDATION
    # =========================================================================

    def validate_binding(
        self,
        task_id: str,
        project_id: str,
        repo_id: str = None,
    ) -> Tuple[bool, List[str]]:
        """Validate binding for task.ready transition

        Returns:
            (is_valid, list_of_errors)

        Checks:
            - project_id is not None
            - project exists
            - repo (if set) belongs to project
            - spec is frozen
        """
        errors = []

        if not project_id:
            errors.append("project_id is required")
            return False, errors

        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # Check project exists
            cursor.execute("SELECT project_id FROM projects WHERE project_id = ?", (project_id,))
            if not cursor.fetchone():
                errors.append(f"Project {project_id} does not exist")

            # Check repo belongs to project (if repo_id provided)
            if repo_id:
                cursor.execute(
                    "SELECT project_id FROM repos WHERE repo_id = ?",
                    (repo_id,),
                )
                repo_row = cursor.fetchone()
                if not repo_row:
                    errors.append(f"Repo {repo_id} does not exist")
                elif repo_row["project_id"] != project_id:
                    errors.append(f"Repo {repo_id} does not belong to project {project_id}")

            # Check spec is frozen
            cursor.execute("SELECT spec_frozen FROM tasks WHERE task_id = ?", (task_id,))
            task_row = cursor.fetchone()
            if not task_row:
                errors.append(f"Task {task_id} does not exist")
            elif task_row["spec_frozen"] != 1:
                errors.append(f"Task {task_id} spec is not frozen")

        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

        is_valid = len(errors) == 0
        return is_valid, errors
