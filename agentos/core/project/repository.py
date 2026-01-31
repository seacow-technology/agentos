"""Repository Management Layer

Provides CRUD operations for project repository bindings and runtime context.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentos.schemas.project import RepoRole, RepoSpec
from agentos.core.time import utc_now


logger = logging.getLogger(__name__)


@dataclass
class RepoContext:
    """Runtime repository context

    Represents a repository's runtime state for task execution.
    Not persisted to database - computed on-demand from RepoSpec.
    """

    repo_id: str
    name: str
    path: Path  # Absolute path to repository workspace
    remote_url: Optional[str] = None
    branch: str = "main"
    writable: bool = True
    role: RepoRole = RepoRole.CODE
    path_filters: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_repo_spec(cls, spec: RepoSpec, workspace_root: Path) -> "RepoContext":
        """Create runtime context from RepoSpec

        Args:
            spec: Repository specification from database
            workspace_root: Project workspace root path

        Returns:
            RepoContext with absolute paths resolved
        """
        # Resolve workspace_relpath to absolute path
        repo_path = workspace_root / spec.workspace_relpath
        repo_path = repo_path.resolve()

        return cls(
            repo_id=spec.repo_id,
            name=spec.name,
            path=repo_path,
            remote_url=spec.remote_url,
            branch=spec.default_branch,
            writable=spec.is_writable,
            role=spec.role,
            metadata=spec.metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "repo_id": self.repo_id,
            "name": self.name,
            "path": str(self.path),
            "remote_url": self.remote_url,
            "branch": self.branch,
            "writable": self.writable,
            "role": self.role.value if isinstance(self.role, RepoRole) else self.role,
            "path_filters": self.path_filters,
            "metadata": self.metadata,
        }


class ProjectRepository:
    """Project Repository CRUD Operations

    Manages repository bindings for projects in the database.
    """

    def __init__(self, db_path: Path):
        """Initialize ProjectRepository

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        logger.info(f"ProjectRepository initialized with db_path={db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def add_repo(self, repo_spec: RepoSpec) -> str:
        """Add a repository binding to a project

        Args:
            repo_spec: Repository specification

        Returns:
            repo_id of the created repository

        Raises:
            sqlite3.IntegrityError: If repo already exists or constraints violated
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # Set timestamps if not provided
            now = utc_now()
            if repo_spec.created_at is None:
                repo_spec.created_at = now
            if repo_spec.updated_at is None:
                repo_spec.updated_at = now

            db_dict = repo_spec.to_db_dict()

            cursor.execute(
                """
                INSERT INTO repos (
                    repo_id, project_id, name, remote_url, default_branch,
                    workspace_relpath, role, is_writable, auth_profile,
                    created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    db_dict["repo_id"],
                    db_dict["project_id"],
                    db_dict["name"],
                    db_dict["remote_url"],
                    db_dict["default_branch"],
                    db_dict["workspace_relpath"],
                    db_dict["role"],
                    db_dict["is_writable"],
                    db_dict["auth_profile"],
                    db_dict["created_at"],
                    db_dict["updated_at"],
                    db_dict["metadata"],
                ),
            )

            conn.commit()
            logger.info(f"Added repo {repo_spec.repo_id} to project {repo_spec.project_id}")
            return repo_spec.repo_id

        except sqlite3.IntegrityError as e:
            logger.error(f"Failed to add repo: {e}")
            raise
        finally:
            conn.close()

    def remove_repo(self, project_id: str, repo_id: str) -> bool:
        """Remove a repository binding from a project

        Args:
            project_id: Project ID
            repo_id: Repository ID to remove

        Returns:
            True if removed, False if not found

        Note:
            Cascading deletes will remove associated task_repo_scope and task_artifact_ref entries
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM repos
                WHERE project_id = ? AND repo_id = ?
                """,
                (project_id, repo_id),
            )
            conn.commit()

            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Removed repo {repo_id} from project {project_id}")
            else:
                logger.warning(f"Repo {repo_id} not found in project {project_id}")

            return deleted

        finally:
            conn.close()

    def list_repos(self, project_id: str) -> List[RepoSpec]:
        """List all repositories bound to a project

        Args:
            project_id: Project ID

        Returns:
            List of RepoSpec objects, ordered by created_at DESC
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM repos
                WHERE project_id = ?
                ORDER BY created_at DESC
                """,
                (project_id,),
            )

            rows = cursor.fetchall()
            repos = [RepoSpec.from_db_row(dict(row)) for row in rows]

            logger.debug(f"Listed {len(repos)} repos for project {project_id}")
            return repos

        finally:
            conn.close()

    def get_repo(self, project_id: str, repo_id: str) -> Optional[RepoSpec]:
        """Get a specific repository by ID

        Args:
            project_id: Project ID
            repo_id: Repository ID

        Returns:
            RepoSpec if found, None otherwise
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM repos
                WHERE project_id = ? AND repo_id = ?
                """,
                (project_id, repo_id),
            )

            row = cursor.fetchone()
            if row:
                return RepoSpec.from_db_row(dict(row))

            return None

        finally:
            conn.close()

    def get_repo_by_name(self, project_id: str, name: str) -> Optional[RepoSpec]:
        """Get a repository by name

        Args:
            project_id: Project ID
            name: Repository name

        Returns:
            RepoSpec if found, None otherwise
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM repos
                WHERE project_id = ? AND name = ?
                """,
                (project_id, name),
            )

            row = cursor.fetchone()
            if row:
                return RepoSpec.from_db_row(dict(row))

            return None

        finally:
            conn.close()

    def update_repo(self, repo_spec: RepoSpec) -> bool:
        """Update repository metadata

        Args:
            repo_spec: Repository specification with updated fields

        Returns:
            True if updated, False if not found
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # Update timestamp
            repo_spec.updated_at = utc_now()
            db_dict = repo_spec.to_db_dict()

            cursor.execute(
                """
                UPDATE repos
                SET name = ?, remote_url = ?, default_branch = ?,
                    workspace_relpath = ?, role = ?, is_writable = ?,
                    auth_profile = ?, updated_at = ?, metadata = ?
                WHERE project_id = ? AND repo_id = ?
                """,
                (
                    db_dict["name"],
                    db_dict["remote_url"],
                    db_dict["default_branch"],
                    db_dict["workspace_relpath"],
                    db_dict["role"],
                    db_dict["is_writable"],
                    db_dict["auth_profile"],
                    db_dict["updated_at"],
                    db_dict["metadata"],
                    db_dict["project_id"],
                    db_dict["repo_id"],
                ),
            )

            conn.commit()
            updated = cursor.rowcount > 0

            if updated:
                logger.info(f"Updated repo {repo_spec.repo_id} in project {repo_spec.project_id}")
            else:
                logger.warning(f"Repo {repo_spec.repo_id} not found for update")

            return updated

        finally:
            conn.close()

    def get_writable_repos(self, project_id: str) -> List[RepoSpec]:
        """Get all writable repositories for a project

        Args:
            project_id: Project ID

        Returns:
            List of writable RepoSpec objects
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM repos
                WHERE project_id = ? AND is_writable = 1
                ORDER BY created_at DESC
                """,
                (project_id,),
            )

            rows = cursor.fetchall()
            return [RepoSpec.from_db_row(dict(row)) for row in rows]

        finally:
            conn.close()

    def get_repos_by_role(self, project_id: str, role: RepoRole) -> List[RepoSpec]:
        """Get repositories by role

        Args:
            project_id: Project ID
            role: Repository role

        Returns:
            List of RepoSpec objects matching the role
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM repos
                WHERE project_id = ? AND role = ?
                ORDER BY created_at DESC
                """,
                (project_id, role.value),
            )

            rows = cursor.fetchall()
            return [RepoSpec.from_db_row(dict(row)) for row in rows]

        finally:
            conn.close()


class RepoRegistry:
    """Repository Registry - Unified entry point for repository operations

    Provides high-level operations combining ProjectRepository CRUD
    with runtime context resolution.
    """

    def __init__(self, db_path: Path, workspace_root: Path):
        """Initialize RepoRegistry

        Args:
            db_path: Path to SQLite database
            workspace_root: Project workspace root path
        """
        self.repo_crud = ProjectRepository(db_path)
        self.workspace_root = workspace_root
        logger.info(f"RepoRegistry initialized with workspace_root={workspace_root}")

    def get_context(self, project_id: str, repo_id: str) -> Optional[RepoContext]:
        """Get runtime context for a repository

        Args:
            project_id: Project ID
            repo_id: Repository ID

        Returns:
            RepoContext if found, None otherwise
        """
        repo_spec = self.repo_crud.get_repo(project_id, repo_id)
        if not repo_spec:
            return None

        return RepoContext.from_repo_spec(repo_spec, self.workspace_root)

    def get_all_contexts(self, project_id: str) -> List[RepoContext]:
        """Get runtime contexts for all repositories in a project

        Args:
            project_id: Project ID

        Returns:
            List of RepoContext objects
        """
        repo_specs = self.repo_crud.list_repos(project_id)
        return [
            RepoContext.from_repo_spec(spec, self.workspace_root)
            for spec in repo_specs
        ]

    def get_default_context(self, project_id: str) -> Optional[RepoContext]:
        """Get default repository context for a project

        Args:
            project_id: Project ID

        Returns:
            RepoContext for default repository, or None if no repos found
        """
        # Try to find repo named "default"
        default_repo = self.repo_crud.get_repo_by_name(project_id, "default")
        if default_repo:
            return RepoContext.from_repo_spec(default_repo, self.workspace_root)

        # Fallback to first repo
        repos = self.repo_crud.list_repos(project_id)
        if repos:
            return RepoContext.from_repo_spec(repos[0], self.workspace_root)

        return None

    def add_repo(self, repo_spec: RepoSpec) -> str:
        """Add repository (delegate to CRUD)"""
        return self.repo_crud.add_repo(repo_spec)

    def get_repo(self, project_id: str, repo_id: str) -> Optional[RepoSpec]:
        """Get repository (delegate to CRUD)"""
        return self.repo_crud.get_repo(project_id, repo_id)

    def remove_repo(self, project_id: str, repo_id: str) -> bool:
        """Remove repository (delegate to CRUD)"""
        return self.repo_crud.remove_repo(project_id, repo_id)

    def list_repos(self, project_id: str) -> List[RepoSpec]:
        """List repositories (delegate to CRUD)"""
        return self.repo_crud.list_repos(project_id)
