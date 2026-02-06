"""Task Repository Context - Runtime execution environment for multi-repo tasks

This module provides runtime context for task execution across multiple repositories.
It enforces path isolation, access control, and scope filtering.

Key Features:
1. Path validation and isolation (prevent directory traversal)
2. Scope-based access control (full/paths/read_only)
3. Path filter support (glob patterns)
4. Safe file operation checks

Created for Phase 5.1: Runner support for cross-repository workspace selection
"""

import fnmatch
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentos.core.task.models import RepoScopeType, TaskRepoScope
from agentos.core.project.repository import RepoContext as BaseRepoContext
from agentos.schemas.project import RepoSpec

logger = logging.getLogger(__name__)


class PathSecurityError(Exception):
    """Raised when a path access violates security constraints"""
    pass


@dataclass
class TaskRepoContext:
    """Task-specific repository context with access control

    This extends BaseRepoContext with task-specific scope and path filtering.
    Used during task execution to enforce repository boundaries and access control.

    Attributes:
        repo_id: Repository ID
        task_id: Task ID this context belongs to
        name: Repository name
        path: Absolute path to repository
        remote_url: Remote repository URL (optional)
        branch: Branch name
        writable: Whether repository is writable for this task
        scope: Access scope (full/paths/read_only)
        path_filters: List of glob patterns for path filtering
        metadata: Extended metadata
    """

    repo_id: str
    task_id: str
    name: str
    path: Path
    remote_url: Optional[str] = None
    branch: str = "main"
    writable: bool = True
    scope: RepoScopeType = RepoScopeType.FULL
    path_filters: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration after initialization"""
        # Ensure path is absolute
        self.path = Path(self.path).resolve()

        # Validate scope
        if not isinstance(self.scope, RepoScopeType):
            self.scope = RepoScopeType(self.scope)

        # Validate path filters when scope is PATHS
        if self.scope == RepoScopeType.PATHS and not self.path_filters:
            logger.warning(
                f"TaskRepoContext {self.repo_id}: scope=paths but no path_filters provided. "
                "This will deny all file access."
            )

    @classmethod
    def from_base_context(
        cls,
        base_context: BaseRepoContext,
        task_id: str,
        scope: RepoScopeType = RepoScopeType.FULL,
        path_filters: Optional[List[str]] = None,
        task_writable_override: Optional[bool] = None
    ) -> "TaskRepoContext":
        """Create TaskRepoContext from BaseRepoContext

        Args:
            base_context: Base repository context
            task_id: Task ID
            scope: Access scope for this task
            path_filters: Optional path filters (glob patterns)
            task_writable_override: Override writable setting for this task

        Returns:
            TaskRepoContext instance
        """
        # Determine writable status
        writable = base_context.writable
        if task_writable_override is not None:
            writable = task_writable_override

        # READ_ONLY scope overrides writable
        if scope == RepoScopeType.READ_ONLY:
            writable = False

        return cls(
            repo_id=base_context.repo_id,
            task_id=task_id,
            name=base_context.name,
            path=base_context.path,
            remote_url=base_context.remote_url,
            branch=base_context.branch,
            writable=writable,
            scope=scope,
            path_filters=path_filters or [],
            metadata=base_context.metadata.copy()
        )

    @classmethod
    def from_task_repo_scope(
        cls,
        task_repo_scope: TaskRepoScope,
        repo_spec: RepoSpec,
        workspace_root: Path,
        task_id: str
    ) -> "TaskRepoContext":
        """Create TaskRepoContext from TaskRepoScope and RepoSpec

        Args:
            task_repo_scope: Task repository scope definition
            repo_spec: Repository specification
            workspace_root: Project workspace root path
            task_id: Task ID

        Returns:
            TaskRepoContext instance
        """
        # Resolve repository path
        repo_path = workspace_root / repo_spec.workspace_relpath
        repo_path = repo_path.resolve()

        # Determine writable status
        writable = repo_spec.is_writable
        if task_repo_scope.scope == RepoScopeType.READ_ONLY:
            writable = False

        return cls(
            repo_id=task_repo_scope.repo_id,
            task_id=task_id,
            name=repo_spec.name,
            path=repo_path,
            remote_url=repo_spec.remote_url,
            branch=repo_spec.default_branch,
            writable=writable,
            scope=task_repo_scope.scope,
            path_filters=task_repo_scope.path_filters,
            metadata={
                **repo_spec.metadata,
                **task_repo_scope.metadata,
            }
        )

    def is_path_within_repo(self, file_path: str | Path) -> bool:
        """Check if a file path is within the repository

        Protects against directory traversal attacks.

        Args:
            file_path: File path to check (can be relative or absolute)

        Returns:
            True if path is within repository, False otherwise
        """
        try:
            # Convert to Path and resolve (handles .., ., symlinks)
            file_path = Path(file_path)

            # If relative, resolve against repo path
            if not file_path.is_absolute():
                resolved_path = (self.path / file_path).resolve()
            else:
                resolved_path = file_path.resolve()

            # Check if resolved path is within repo path
            try:
                resolved_path.relative_to(self.path)
                return True
            except ValueError:
                # Path is outside repo
                return False

        except Exception as e:
            logger.warning(f"Path validation error for {file_path}: {e}")
            return False

    def is_path_allowed(self, file_path: str | Path) -> bool:
        """Check if a file path is allowed by scope and filters

        Args:
            file_path: File path to check

        Returns:
            True if path is allowed, False otherwise
        """
        # First check if path is within repo boundaries
        if not self.is_path_within_repo(file_path):
            return False

        # For FULL scope, all paths within repo are allowed
        if self.scope == RepoScopeType.FULL:
            return True

        # For PATHS scope, check against path_filters
        if self.scope == RepoScopeType.PATHS:
            if not self.path_filters:
                # No filters means deny all
                return False

            # Convert to relative path for pattern matching
            file_path = Path(file_path)
            if not file_path.is_absolute():
                rel_path = file_path
            else:
                try:
                    resolved = file_path.resolve()
                    rel_path = resolved.relative_to(self.path)
                except ValueError:
                    # Path is outside repo
                    return False

            # Check against glob patterns
            rel_path_str = str(rel_path)
            for pattern in self.path_filters:
                if fnmatch.fnmatch(rel_path_str, pattern):
                    return True
                # Also support directory patterns
                if fnmatch.fnmatch(rel_path_str, pattern + "/*"):
                    return True

            return False

        # For READ_ONLY scope, all paths are readable
        if self.scope == RepoScopeType.READ_ONLY:
            return True

        return False

    def validate_read_access(self, file_path: str | Path) -> None:
        """Validate read access to a file path

        Args:
            file_path: File path to validate

        Raises:
            PathSecurityError: If access is denied
        """
        if not self.is_path_allowed(file_path):
            raise PathSecurityError(
                f"Read access denied for {file_path} in repo {self.repo_id} "
                f"(scope={self.scope.value}, task={self.task_id})"
            )

    def validate_write_access(self, file_path: str | Path) -> None:
        """Validate write access to a file path

        Args:
            file_path: File path to validate

        Raises:
            PathSecurityError: If access is denied
        """
        # Check writable flag
        if not self.writable:
            raise PathSecurityError(
                f"Write access denied for {file_path} in repo {self.repo_id}: "
                f"repository is read-only for task {self.task_id}"
            )

        # Check path is allowed
        if not self.is_path_allowed(file_path):
            raise PathSecurityError(
                f"Write access denied for {file_path} in repo {self.repo_id} "
                f"(scope={self.scope.value}, task={self.task_id})"
            )

    def get_relative_path(self, file_path: str | Path) -> Optional[Path]:
        """Get relative path within repository

        Args:
            file_path: File path (absolute or relative)

        Returns:
            Relative path within repo, or None if outside repo
        """
        try:
            file_path = Path(file_path)
            if not file_path.is_absolute():
                # Already relative, validate it's within repo
                if self.is_path_within_repo(file_path):
                    return file_path
                return None

            # Convert absolute to relative
            resolved = file_path.resolve()
            return resolved.relative_to(self.path)
        except (ValueError, Exception) as e:
            logger.debug(f"Cannot get relative path for {file_path}: {e}")
            return None

    def get_absolute_path(self, rel_path: str | Path) -> Path:
        """Get absolute path from relative path

        Args:
            rel_path: Relative path within repository

        Returns:
            Absolute path

        Raises:
            PathSecurityError: If resulting path is outside repository
        """
        abs_path = (self.path / rel_path).resolve()
        if not self.is_path_within_repo(abs_path):
            raise PathSecurityError(
                f"Path {rel_path} resolves outside repository {self.repo_id}"
            )
        return abs_path

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "repo_id": self.repo_id,
            "task_id": self.task_id,
            "name": self.name,
            "path": str(self.path),
            "remote_url": self.remote_url,
            "branch": self.branch,
            "writable": self.writable,
            "scope": self.scope.value if isinstance(self.scope, RepoScopeType) else self.scope,
            "path_filters": self.path_filters,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"TaskRepoContext(repo_id={self.repo_id}, task_id={self.task_id}, "
            f"name={self.name}, path={self.path}, scope={self.scope.value}, "
            f"writable={self.writable})"
        )


@dataclass
class ExecutionEnv:
    """Task execution environment with multiple repository contexts

    This encapsulates all repository contexts available to a task during execution.
    Provides context switching and validation.

    Attributes:
        task_id: Task ID
        repos: Dictionary of repo_id -> TaskRepoContext
        default_repo_id: Default repository ID
    """

    task_id: str
    repos: Dict[str, TaskRepoContext] = field(default_factory=dict)
    default_repo_id: Optional[str] = None

    def add_repo(self, context: TaskRepoContext) -> None:
        """Add a repository context

        Args:
            context: TaskRepoContext to add
        """
        if context.task_id != self.task_id:
            raise ValueError(
                f"Cannot add context for task {context.task_id} to "
                f"ExecutionEnv for task {self.task_id}"
            )

        self.repos[context.repo_id] = context

        # Set as default if first repo or named "default"
        if self.default_repo_id is None or context.name == "default":
            self.default_repo_id = context.repo_id

    def get_repo(self, repo_id: str) -> Optional[TaskRepoContext]:
        """Get repository context by ID

        Args:
            repo_id: Repository ID

        Returns:
            TaskRepoContext or None if not found
        """
        return self.repos.get(repo_id)

    def get_repo_by_name(self, name: str) -> Optional[TaskRepoContext]:
        """Get repository context by name

        Args:
            name: Repository name

        Returns:
            TaskRepoContext or None if not found
        """
        for context in self.repos.values():
            if context.name == name:
                return context
        return None

    def get_default_repo(self) -> Optional[TaskRepoContext]:
        """Get default repository context

        Returns:
            Default TaskRepoContext or None if no repos
        """
        if self.default_repo_id:
            return self.repos.get(self.default_repo_id)
        return None

    def list_repos(self) -> List[TaskRepoContext]:
        """List all repository contexts

        Returns:
            List of TaskRepoContext objects
        """
        return list(self.repos.values())

    def list_writable_repos(self) -> List[TaskRepoContext]:
        """List writable repository contexts

        Returns:
            List of writable TaskRepoContext objects
        """
        return [ctx for ctx in self.repos.values() if ctx.writable]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "repos": {repo_id: ctx.to_dict() for repo_id, ctx in self.repos.items()},
            "default_repo_id": self.default_repo_id,
        }

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"ExecutionEnv(task_id={self.task_id}, "
            f"repos={len(self.repos)}, default={self.default_repo_id})"
        )
