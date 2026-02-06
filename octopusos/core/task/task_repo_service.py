"""Task Repository Service - Manages task-repository associations

This module provides high-level operations for managing task-repository associations,
including creating repo scopes, building execution environments, and validating access.

Key Features:
1. CRUD operations for task_repo_scope
2. Build ExecutionEnv from task configuration
3. Validate repo access and scope
4. Integration with ProjectRepository

Created for Phase 5.1: Runner support for cross-repository workspace selection
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import List, Optional

from agentos.core.task.models import TaskRepoScope, RepoScopeType
from agentos.core.task.repo_context import TaskRepoContext, ExecutionEnv
from agentos.core.project.repository import ProjectRepository, RepoRegistry
from agentos.schemas.project import RepoSpec

logger = logging.getLogger(__name__)


class TaskRepoService:
    """Task Repository Service

    Manages task-repository associations and builds execution environments.
    """

    def __init__(self, db_path: Path, workspace_root: Path):
        """Initialize TaskRepoService

        Args:
            db_path: Path to SQLite database
            workspace_root: Project workspace root path
        """
        self.db_path = db_path
        self.workspace_root = workspace_root
        self.project_repo = ProjectRepository(db_path)
        logger.info(f"TaskRepoService initialized with db_path={db_path}, workspace_root={workspace_root}")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def add_repo_scope(self, scope: TaskRepoScope) -> int:
        """Add a repository scope for a task

        Args:
            scope: TaskRepoScope to add

        Returns:
            scope_id of the created entry

        Raises:
            sqlite3.IntegrityError: If scope already exists or constraints violated
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            # Validate repo exists (will raise if not found)
            # Note: We need to extract project_id from somewhere - for now we'll skip this check
            # In production, you'd look up the task's project_id first

            scope_dict = scope.to_dict()

            cursor.execute(
                """
                INSERT INTO task_repo_scope (
                    task_id, repo_id, scope, path_filters, created_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    scope_dict["task_id"],
                    scope_dict["repo_id"],
                    scope_dict["scope"],
                    scope_dict["path_filters"],
                    scope_dict["created_at"],
                    scope_dict["metadata"],
                ),
            )

            scope_id = cursor.lastrowid
            conn.commit()

            logger.info(f"Added task_repo_scope {scope_id} for task {scope.task_id}, repo {scope.repo_id}")
            return scope_id

        except sqlite3.IntegrityError as e:
            logger.error(f"Failed to add repo scope: {e}")
            raise
        finally:
            conn.close()

    def get_repo_scopes(self, task_id: str) -> List[TaskRepoScope]:
        """Get all repository scopes for a task

        Args:
            task_id: Task ID

        Returns:
            List of TaskRepoScope objects
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM task_repo_scope
                WHERE task_id = ?
                ORDER BY created_at ASC
                """,
                (task_id,),
            )

            rows = cursor.fetchall()
            scopes = [TaskRepoScope.from_db_row(dict(row)) for row in rows]

            logger.debug(f"Retrieved {len(scopes)} repo scopes for task {task_id}")
            return scopes

        finally:
            conn.close()

    def remove_repo_scope(self, task_id: str, repo_id: str) -> bool:
        """Remove a repository scope from a task

        Args:
            task_id: Task ID
            repo_id: Repository ID

        Returns:
            True if removed, False if not found
        """
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM task_repo_scope
                WHERE task_id = ? AND repo_id = ?
                """,
                (task_id, repo_id),
            )
            conn.commit()

            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Removed repo scope: task {task_id}, repo {repo_id}")
            else:
                logger.warning(f"Repo scope not found: task {task_id}, repo {repo_id}")

            return deleted

        finally:
            conn.close()

    def validate_repo_scope(self, task_id: str, repo_id: str, project_id: str) -> None:
        """Validate that a repository scope is valid

        Args:
            task_id: Task ID
            repo_id: Repository ID to validate
            project_id: Project ID

        Raises:
            ValueError: If repo_id doesn't exist or validation fails
        """
        # Check repo exists in project
        repo_spec = self.project_repo.get_repo(project_id, repo_id)
        if not repo_spec:
            raise ValueError(f"Repository {repo_id} not found in project {project_id}")

        logger.debug(f"Validated repo scope: task {task_id}, repo {repo_id}")

    def build_execution_env(
        self,
        task_id: str,
        project_id: str,
        repo_scopes: Optional[List[TaskRepoScope]] = None
    ) -> ExecutionEnv:
        """Build execution environment for a task

        Args:
            task_id: Task ID
            project_id: Project ID
            repo_scopes: Optional list of TaskRepoScope (if None, loads from DB)

        Returns:
            ExecutionEnv with all repository contexts configured

        Raises:
            ValueError: If configuration is invalid
        """
        # Load repo scopes if not provided
        if repo_scopes is None:
            repo_scopes = self.get_repo_scopes(task_id)

        # Create execution environment
        env = ExecutionEnv(task_id=task_id)

        # If no repo scopes defined, use all project repos with FULL scope
        if not repo_scopes:
            logger.info(f"No repo scopes for task {task_id}, using all project repos with FULL scope")
            repo_specs = self.project_repo.list_repos(project_id)

            for repo_spec in repo_specs:
                # Create default scope
                default_scope = TaskRepoScope(
                    task_id=task_id,
                    repo_id=repo_spec.repo_id,
                    scope=RepoScopeType.FULL,
                    path_filters=[],
                    metadata={"auto_generated": True}
                )

                # Build context
                context = TaskRepoContext.from_task_repo_scope(
                    task_repo_scope=default_scope,
                    repo_spec=repo_spec,
                    workspace_root=self.workspace_root,
                    task_id=task_id
                )

                env.add_repo(context)

        else:
            # Build contexts from defined scopes
            for scope in repo_scopes:
                # Load repo spec
                repo_spec = self.project_repo.get_repo(project_id, scope.repo_id)
                if not repo_spec:
                    raise ValueError(
                        f"Repository {scope.repo_id} not found in project {project_id} "
                        f"(required by task {task_id})"
                    )

                # Build context
                context = TaskRepoContext.from_task_repo_scope(
                    task_repo_scope=scope,
                    repo_spec=repo_spec,
                    workspace_root=self.workspace_root,
                    task_id=task_id
                )

                env.add_repo(context)

        logger.info(
            f"Built ExecutionEnv for task {task_id}: {len(env.repos)} repos, "
            f"default={env.default_repo_id}"
        )

        return env

    def validate_execution_env(self, env: ExecutionEnv) -> List[str]:
        """Validate execution environment configuration

        Args:
            env: ExecutionEnv to validate

        Returns:
            List of validation warnings (empty if no issues)
        """
        warnings = []

        # Check at least one repo
        if not env.repos:
            warnings.append("No repositories configured for task")

        # Check default repo exists
        if env.default_repo_id and env.default_repo_id not in env.repos:
            warnings.append(f"Default repo {env.default_repo_id} not found in environment")

        # Check at least one writable repo
        writable_repos = env.list_writable_repos()
        if not writable_repos:
            warnings.append("No writable repositories configured for task")

        # Check for path collisions (multiple repos with same workspace path)
        paths_seen = set()
        for context in env.repos.values():
            path_str = str(context.path)
            if path_str in paths_seen:
                warnings.append(f"Path collision detected: {path_str} used by multiple repos")
            paths_seen.add(path_str)

        # Validate each context
        for context in env.repos.values():
            # Check repo path exists
            if not context.path.exists():
                warnings.append(f"Repository path does not exist: {context.path} (repo {context.repo_id})")

            # Check scope vs path_filters consistency
            if context.scope == RepoScopeType.PATHS and not context.path_filters:
                warnings.append(
                    f"Repository {context.repo_id} has scope=PATHS but no path_filters "
                    "(will deny all access)"
                )

        if warnings:
            logger.warning(f"ExecutionEnv validation warnings for task {env.task_id}: {warnings}")

        return warnings

    def get_repo_for_file(self, env: ExecutionEnv, file_path: Path) -> Optional[TaskRepoContext]:
        """Find which repository context contains a file path

        Args:
            env: ExecutionEnv to search
            file_path: File path to locate

        Returns:
            TaskRepoContext that contains the file, or None if not found
        """
        file_path = Path(file_path).resolve()

        # Check each repo context
        for context in env.repos.values():
            if context.is_path_within_repo(file_path):
                return context

        return None

    def create_default_scope(
        self,
        task_id: str,
        project_id: str,
        scope_type: RepoScopeType = RepoScopeType.FULL
    ) -> List[TaskRepoScope]:
        """Create default repository scopes for a task

        Creates scopes for all repositories in the project.

        Args:
            task_id: Task ID
            project_id: Project ID
            scope_type: Default scope type (default: FULL)

        Returns:
            List of created TaskRepoScope objects
        """
        repo_specs = self.project_repo.list_repos(project_id)
        scopes = []

        for repo_spec in repo_specs:
            scope = TaskRepoScope(
                task_id=task_id,
                repo_id=repo_spec.repo_id,
                scope=scope_type,
                path_filters=[],
                metadata={"auto_generated": True}
            )

            try:
                scope_id = self.add_repo_scope(scope)
                scope.scope_id = scope_id
                scopes.append(scope)
            except sqlite3.IntegrityError:
                logger.warning(f"Scope already exists for task {task_id}, repo {repo_spec.repo_id}")

        logger.info(f"Created {len(scopes)} default scopes for task {task_id}")
        return scopes


def build_repo_contexts(
    task_id: str,
    project_id: str,
    db_path: Path,
    workspace_root: Path,
    repo_scopes: Optional[List[TaskRepoScope]] = None
) -> ExecutionEnv:
    """Convenience function to build execution environment

    Args:
        task_id: Task ID
        project_id: Project ID
        db_path: Path to SQLite database
        workspace_root: Project workspace root path
        repo_scopes: Optional list of TaskRepoScope

    Returns:
        ExecutionEnv with all repository contexts configured
    """
    service = TaskRepoService(db_path, workspace_root)
    return service.build_execution_env(task_id, project_id, repo_scopes)
