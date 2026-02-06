"""Project Management Service

Provides high-level project operations for v0.4 Project-Aware Task OS.

Created for Task #3 Phase 2: Core Service Implementation
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from agentos.core.time import utc_now, utc_now_iso


try:
    from ulid import ULID
except ImportError:
    import uuid

    class ULID:
        @staticmethod
        def from_datetime(dt):
            return str(uuid.uuid4())

from agentos.schemas.v31_models import Project, Repo
from agentos.core.project.errors import (
    ProjectNotFoundError,
    ProjectNameConflictError,
    ProjectHasTasksError,
)
from agentos.core.task.models import Task
from agentos.store import get_db, get_writer

logger = logging.getLogger(__name__)


class ProjectService:
    """Project management service

    Provides business-level operations for project management.
    All database writes go through SQLiteWriter for concurrency safety.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize ProjectService

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
    # PROJECT CRUD
    # =========================================================================

    def create_project(
        self,
        name: str,
        description: str = None,
        tags: List[str] = None,
        default_repo_id: str = None,
    ) -> Project:
        """Create a new project

        Args:
            name: Project name (must be unique)
            description: Optional project description
            tags: Optional list of tags
            default_repo_id: Optional default repository ID

        Returns:
            Project object with project_id

        Raises:
            ProjectNameConflictError: If name already exists
        """
        # Generate project ID
        project_id = str(ULID.from_datetime(utc_now()))
        now = utc_now_iso()

        # Prepare data
        if tags is None:
            tags = []

        # Define write function for serialized execution
        def _write_project(conn):
            cursor = conn.cursor()

            # Check for name conflict
            cursor.execute("SELECT project_id FROM projects WHERE name = ?", (name,))
            if cursor.fetchone():
                raise ProjectNameConflictError(name)

            # Insert project
            cursor.execute(
                """
                INSERT INTO projects (project_id, name, description, tags, default_repo_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    name,
                    description,
                    json.dumps(tags),
                    default_repo_id,
                    now,
                    now,
                ),
            )

            logger.info(f"Created project: {project_id} ({name})")
            return project_id

        # Submit write operation
        writer = get_writer()
        try:
            result_id = writer.submit(_write_project, timeout=10.0)
        except Exception as e:
            logger.error(f"Failed to create project: {e}", exc_info=True)
            raise

        # Return project object
        return Project(
            project_id=project_id,
            name=name,
            description=description,
            tags=tags,
            default_repo_id=default_repo_id,
            created_at=now,
            updated_at=now,
        )

    def get_project(self, project_id: str) -> Optional[Project]:
        """Get project by ID

        Args:
            project_id: Project ID

        Returns:
            Project object or None if not found
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT project_id, name, description, tags, default_repo_id, created_at, updated_at, metadata
                FROM projects
                WHERE project_id = ?
                """,
                (project_id,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            return Project.from_db_row(dict(row))
        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

    def list_projects(
        self,
        limit: int = 100,
        offset: int = 0,
        tags: List[str] = None,
    ) -> List[Project]:
        """List all projects with optional tag filtering

        Args:
            limit: Maximum number of projects to return
            offset: Offset for pagination
            tags: Optional list of tags to filter by (OR logic)

        Returns:
            List of Project objects
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            if tags:
                # Tag filtering (OR logic: match any tag)
                # This is a simple implementation; for production, consider FTS or JSON1
                query = """
                    SELECT project_id, name, description, tags, default_repo_id, created_at, updated_at, metadata
                    FROM projects
                    WHERE 1=1
                """
                # Add tag filter for each tag (using LIKE for simplicity)
                tag_conditions = " OR ".join(["tags LIKE ?" for _ in tags])
                query += f" AND ({tag_conditions})"
                query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"

                params = [f'%"{tag}"%' for tag in tags] + [limit, offset]
                cursor.execute(query, params)
            else:
                # No tag filtering
                cursor.execute(
                    """
                    SELECT project_id, name, description, tags, default_repo_id, created_at, updated_at, metadata
                    FROM projects
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )

            rows = cursor.fetchall()
            return [Project.from_db_row(dict(row)) for row in rows]
        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

    def update_project(
        self,
        project_id: str,
        name: str = None,
        description: str = None,
        tags: List[str] = None,
        default_repo_id: str = None,
    ) -> Project:
        """Update project fields

        Args:
            project_id: Project ID
            name: Optional new name (must be unique)
            description: Optional new description
            tags: Optional new tags list
            default_repo_id: Optional new default repo ID

        Returns:
            Updated Project object

        Raises:
            ProjectNotFoundError: If project doesn't exist
            ProjectNameConflictError: If new name already exists
        """
        now = utc_now_iso()

        # Define write function
        def _write_update(conn):
            cursor = conn.cursor()

            # Check project exists
            cursor.execute("SELECT project_id FROM projects WHERE project_id = ?", (project_id,))
            if not cursor.fetchone():
                raise ProjectNotFoundError(project_id)

            # Check name conflict (if changing name)
            if name:
                cursor.execute(
                    "SELECT project_id FROM projects WHERE name = ? AND project_id != ?",
                    (name, project_id),
                )
                if cursor.fetchone():
                    raise ProjectNameConflictError(name)

            # Build update query dynamically
            updates = []
            params = []

            if name is not None:
                updates.append("name = ?")
                params.append(name)

            if description is not None:
                updates.append("description = ?")
                params.append(description)

            if tags is not None:
                updates.append("tags = ?")
                params.append(json.dumps(tags))

            if default_repo_id is not None:
                updates.append("default_repo_id = ?")
                params.append(default_repo_id)

            # Always update updated_at
            updates.append("updated_at = ?")
            params.append(now)

            params.append(project_id)

            query = f"UPDATE projects SET {', '.join(updates)} WHERE project_id = ?"
            cursor.execute(query, params)

            logger.info(f"Updated project: {project_id}")
            return project_id

        # Submit write operation
        writer = get_writer()
        try:
            writer.submit(_write_update, timeout=10.0)
        except Exception as e:
            logger.error(f"Failed to update project: {e}", exc_info=True)
            raise

        # Fetch and return updated project
        return self.get_project(project_id)

    def delete_project(self, project_id: str, force: bool = False) -> bool:
        """Delete project with referential integrity enforcement

        Deletion Strategy (M-24 Fix):
        1. By default (force=False): RESTRICT - prevents deletion if tasks exist
        2. With force=True: Attempts deletion but will FAIL due to FK RESTRICT constraint
        3. Associated repos: CASCADE deleted automatically (ON DELETE CASCADE)

        Foreign Key Constraints:
        - task_bindings.project_id -> projects.project_id (ON DELETE RESTRICT)
          * Prevents deletion if any tasks reference this project
          * Ensures data integrity - tasks must be deleted/reassigned first
        - repos.project_id -> projects.project_id (ON DELETE CASCADE)
          * Automatically deletes all repos when project deleted
          * Cascades to task_repo_scope entries

        Args:
            project_id: Project ID
            force: If True, attempts deletion even if project has tasks
                   (will still fail due to FK RESTRICT constraint on task_bindings)

        Returns:
            True if deleted successfully

        Raises:
            ProjectNotFoundError: If project doesn't exist
            ProjectHasTasksError: If project has tasks and force=False
            sqlite3.IntegrityError: If project has tasks and force=True
                (FK constraint violation)

        Example:
            # Safe deletion (checks first)
            service.delete_project("proj_123")  # Raises ProjectHasTasksError if tasks exist

            # Force deletion (will fail at DB level if tasks exist)
            try:
                service.delete_project("proj_123", force=True)
            except sqlite3.IntegrityError as e:
                # FK constraint prevents deletion
                pass
        """

        def _write_delete(conn):
            cursor = conn.cursor()

            # Check project exists
            cursor.execute("SELECT project_id FROM projects WHERE project_id = ?", (project_id,))
            if not cursor.fetchone():
                raise ProjectNotFoundError(project_id)

            # Check for tasks if not forcing (application-level check)
            if not force:
                cursor.execute(
                    "SELECT COUNT(*) as count FROM task_bindings WHERE project_id = ?",
                    (project_id,),
                )
                row = cursor.fetchone()
                task_count = row["count"] if row else 0

                if task_count > 0:
                    raise ProjectHasTasksError(project_id, task_count)

            # Delete project
            # - CASCADE will delete repos automatically
            # - RESTRICT will prevent deletion if task_bindings exist (DB-level check)
            cursor.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))

            logger.info(f"Deleted project: {project_id} (force={force})")
            return True

        # Submit write operation
        writer = get_writer()
        try:
            result = writer.submit(_write_delete, timeout=10.0)
            return result
        except Exception as e:
            logger.error(f"Failed to delete project: {e}", exc_info=True)
            raise

    # =========================================================================
    # PROJECT RELATIONSHIPS
    # =========================================================================

    def get_project_repos(self, project_id: str) -> List[Repo]:
        """Get all repos for a project

        Args:
            project_id: Project ID

        Returns:
            List of Repo objects
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT repo_id, project_id, name, local_path, vcs_type, remote_url, default_branch, created_at, updated_at, metadata
                FROM repos
                WHERE project_id = ?
                ORDER BY created_at
                """,
                (project_id,),
            )
            rows = cursor.fetchall()
            return [Repo.from_db_row(dict(row)) for row in rows]
        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

    def get_project_tasks(
        self,
        project_id: str,
        status: str = None,
        limit: int = 100,
    ) -> List[Task]:
        """Get all tasks for a project

        Args:
            project_id: Project ID
            status: Optional status filter
            limit: Maximum number of tasks to return

        Returns:
            List of Task objects
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            if status:
                cursor.execute(
                    """
                    SELECT t.task_id, t.title, t.status, t.session_id, t.project_id, t.created_at, t.updated_at, t.created_by, t.metadata, t.exit_reason
                    FROM tasks t
                    JOIN task_bindings tb ON t.task_id = tb.task_id
                    WHERE tb.project_id = ? AND t.status = ?
                    ORDER BY t.created_at DESC
                    LIMIT ?
                    """,
                    (project_id, status, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT t.task_id, t.title, t.status, t.session_id, t.project_id, t.created_at, t.updated_at, t.created_by, t.metadata, t.exit_reason
                    FROM tasks t
                    JOIN task_bindings tb ON t.task_id = tb.task_id
                    WHERE tb.project_id = ?
                    ORDER BY t.created_at DESC
                    LIMIT ?
                    """,
                    (project_id, limit),
                )

            rows = cursor.fetchall()
            tasks = []
            for row in rows:
                row_dict = dict(row)
                # Parse metadata from JSON
                if row_dict.get("metadata"):
                    try:
                        row_dict["metadata"] = json.loads(row_dict["metadata"])
                    except json.JSONDecodeError:
                        row_dict["metadata"] = {}
                else:
                    row_dict["metadata"] = {}

                tasks.append(Task(**row_dict))

            return tasks
        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()
