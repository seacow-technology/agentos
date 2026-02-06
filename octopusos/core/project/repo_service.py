"""Repository Management Service

Provides high-level repository operations for v0.4 Project-Aware Task OS.

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

from agentos.schemas.v31_models import Repo
from agentos.core.project.errors import (
    RepoNotFoundError,
    RepoNameConflictError,
    RepoNotInProjectError,
    InvalidPathError,
    PathNotFoundError,
    ProjectNotFoundError,
)
from agentos.core.project.path_utils import (
    validate_absolute_path,
    validate_path_exists,
)
from agentos.store import get_db, get_writer

logger = logging.getLogger(__name__)


class RepoService:
    """Repository management service

    Provides business-level operations for repository management.
    All database writes go through SQLiteWriter for concurrency safety.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize RepoService

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
    # REPOSITORY CRUD
    # =========================================================================

    def add_repo(
        self,
        project_id: str,
        name: str,
        local_path: str,
        vcs_type: str = "git",
        remote_url: str = None,
        default_branch: str = None,
    ) -> Repo:
        """Add a repo to a project

        Args:
            project_id: Project ID
            name: Repository name (unique within project)
            local_path: Local absolute path to repository
            vcs_type: Version control system type (default: git)
            remote_url: Optional remote repository URL
            default_branch: Optional default branch name

        Returns:
            Repo object with repo_id

        Raises:
            InvalidPathError: If path is invalid/unsafe
            PathNotFoundError: If path doesn't exist
            RepoNameConflictError: If name already exists in project
            ProjectNotFoundError: If project_id doesn't exist
        """
        # Validate path
        is_valid, error_msg = validate_absolute_path(local_path)
        if not is_valid:
            raise InvalidPathError(local_path, error_msg)

        exists, error_msg = validate_path_exists(local_path)
        if not exists:
            raise PathNotFoundError(local_path)

        # Generate repo ID
        repo_id = str(ULID.from_datetime(utc_now()))
        now = utc_now_iso()

        # Define write function
        def _write_repo(conn):
            cursor = conn.cursor()

            # Check project exists
            cursor.execute("SELECT project_id FROM projects WHERE project_id = ?", (project_id,))
            if not cursor.fetchone():
                raise ProjectNotFoundError(project_id)

            # Check for name conflict
            cursor.execute(
                "SELECT repo_id FROM repos WHERE project_id = ? AND name = ?",
                (project_id, name),
            )
            if cursor.fetchone():
                raise RepoNameConflictError(project_id, name)

            # Insert repo
            cursor.execute(
                """
                INSERT INTO repos (repo_id, project_id, name, local_path, vcs_type, remote_url, default_branch, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo_id,
                    project_id,
                    name,
                    local_path,
                    vcs_type,
                    remote_url,
                    default_branch,
                    now,
                    now,
                ),
            )

            logger.info(f"Added repo: {repo_id} ({name}) to project {project_id}")
            return repo_id

        # Submit write operation
        writer = get_writer()
        try:
            result_id = writer.submit(_write_repo, timeout=10.0)
        except Exception as e:
            logger.error(f"Failed to add repo: {e}", exc_info=True)
            raise

        # Return repo object
        return Repo(
            repo_id=repo_id,
            project_id=project_id,
            name=name,
            local_path=local_path,
            vcs_type=vcs_type,
            remote_url=remote_url,
            default_branch=default_branch,
            created_at=now,
            updated_at=now,
        )

    def get_repo(self, repo_id: str) -> Optional[Repo]:
        """Get repo by ID

        Args:
            repo_id: Repository ID

        Returns:
            Repo object or None if not found
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT repo_id, project_id, name, local_path, vcs_type, remote_url, default_branch, created_at, updated_at, metadata
                FROM repos
                WHERE repo_id = ?
                """,
                (repo_id,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            return Repo.from_db_row(dict(row))
        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

    def list_repos(
        self,
        project_id: str = None,
        limit: int = 100,
    ) -> List[Repo]:
        """List repos, optionally filtered by project

        Args:
            project_id: Optional project ID to filter by
            limit: Maximum number of repos to return

        Returns:
            List of Repo objects
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            if project_id:
                cursor.execute(
                    """
                    SELECT repo_id, project_id, name, local_path, vcs_type, remote_url, default_branch, created_at, updated_at, metadata
                    FROM repos
                    WHERE project_id = ?
                    ORDER BY created_at
                    LIMIT ?
                    """,
                    (project_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT repo_id, project_id, name, local_path, vcs_type, remote_url, default_branch, created_at, updated_at, metadata
                    FROM repos
                    ORDER BY created_at
                    LIMIT ?
                    """,
                    (limit,),
                )

            rows = cursor.fetchall()
            return [Repo.from_db_row(dict(row)) for row in rows]
        finally:
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

    def update_repo(
        self,
        repo_id: str,
        name: str = None,
        local_path: str = None,
        remote_url: str = None,
        default_branch: str = None,
    ) -> Repo:
        """Update repo fields (re-validate path if changed)

        Args:
            repo_id: Repository ID
            name: Optional new name (unique within project)
            local_path: Optional new local path (will be validated)
            remote_url: Optional new remote URL
            default_branch: Optional new default branch

        Returns:
            Updated Repo object

        Raises:
            RepoNotFoundError: If repo doesn't exist
            InvalidPathError: If new path is invalid
            PathNotFoundError: If new path doesn't exist
            RepoNameConflictError: If new name conflicts
        """
        # Validate new path if provided
        if local_path:
            is_valid, error_msg = validate_absolute_path(local_path)
            if not is_valid:
                raise InvalidPathError(local_path, error_msg)

            exists, error_msg = validate_path_exists(local_path)
            if not exists:
                raise PathNotFoundError(local_path)

        now = utc_now_iso()

        # Define write function
        def _write_update(conn):
            cursor = conn.cursor()

            # Check repo exists and get project_id
            cursor.execute(
                "SELECT project_id FROM repos WHERE repo_id = ?",
                (repo_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise RepoNotFoundError(repo_id)

            project_id = row["project_id"]

            # Check name conflict (if changing name)
            if name:
                cursor.execute(
                    "SELECT repo_id FROM repos WHERE project_id = ? AND name = ? AND repo_id != ?",
                    (project_id, name, repo_id),
                )
                if cursor.fetchone():
                    raise RepoNameConflictError(project_id, name)

            # Build update query dynamically
            updates = []
            params = []

            if name is not None:
                updates.append("name = ?")
                params.append(name)

            if local_path is not None:
                updates.append("local_path = ?")
                params.append(local_path)

            if remote_url is not None:
                updates.append("remote_url = ?")
                params.append(remote_url)

            if default_branch is not None:
                updates.append("default_branch = ?")
                params.append(default_branch)

            # Always update updated_at
            updates.append("updated_at = ?")
            params.append(now)

            params.append(repo_id)

            query = f"UPDATE repos SET {', '.join(updates)} WHERE repo_id = ?"
            cursor.execute(query, params)

            logger.info(f"Updated repo: {repo_id}")
            return repo_id

        # Submit write operation
        writer = get_writer()
        try:
            writer.submit(_write_update, timeout=10.0)
        except Exception as e:
            logger.error(f"Failed to update repo: {e}", exc_info=True)
            raise

        # Fetch and return updated repo
        return self.get_repo(repo_id)

    def delete_repo(self, repo_id: str) -> bool:
        """Delete repo (tasks using this repo will have repo_id set to NULL)

        Args:
            repo_id: Repository ID

        Returns:
            True if deleted

        Raises:
            RepoNotFoundError: If repo doesn't exist
        """

        def _write_delete(conn):
            cursor = conn.cursor()

            # Check repo exists
            cursor.execute("SELECT repo_id FROM repos WHERE repo_id = ?", (repo_id,))
            if not cursor.fetchone():
                raise RepoNotFoundError(repo_id)

            # Delete repo (FK constraint will SET NULL on task_bindings.repo_id)
            cursor.execute("DELETE FROM repos WHERE repo_id = ?", (repo_id,))

            logger.info(f"Deleted repo: {repo_id}")
            return True

        # Submit write operation
        writer = get_writer()
        try:
            result = writer.submit(_write_delete, timeout=10.0)
            return result
        except Exception as e:
            logger.error(f"Failed to delete repo: {e}", exc_info=True)
            raise

    # =========================================================================
    # REPOSITORY SCANNING (Optional)
    # =========================================================================

    def scan_repo(self, repo_id: str) -> Dict[str, Any]:
        """Scan repo for git info (optional, can be P1)

        Args:
            repo_id: Repository ID

        Returns:
            Dictionary with repo scan info:
                {
                    "vcs_type": "git",
                    "current_branch": "main",
                    "remote_url": "https://...",
                    "last_commit": "abc123...",
                    "is_dirty": False
                }

        Raises:
            RepoNotFoundError: If repo doesn't exist

        Note:
            This is an optional feature. Basic implementation for now.
        """
        repo = self.get_repo(repo_id)
        if not repo:
            raise RepoNotFoundError(repo_id)

        result = {
            "vcs_type": repo.vcs_type,
            "local_path": repo.local_path,
            "remote_url": repo.remote_url,
        }

        # Try to get git info if it's a git repo
        if repo.vcs_type == "git":
            try:
                import subprocess

                repo_path = Path(repo.local_path)

                # Get current branch
                branch_result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if branch_result.returncode == 0:
                    result["current_branch"] = branch_result.stdout.strip()

                # Get last commit
                commit_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if commit_result.returncode == 0:
                    result["last_commit"] = commit_result.stdout.strip()

                # Check if dirty
                status_result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if status_result.returncode == 0:
                    result["is_dirty"] = bool(status_result.stdout.strip())

            except Exception as e:
                logger.warning(f"Failed to scan git repo {repo_id}: {e}")
                result["scan_error"] = str(e)

        return result
