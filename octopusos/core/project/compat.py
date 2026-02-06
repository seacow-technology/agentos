"""Compatibility Layer for Single-Repo to Multi-Repo Migration

This module provides backward compatibility adapters to ensure existing
single-repo project code continues to work without modification while
transitioning to the new multi-repo architecture.

Key principles:
1. Zero breaking changes for existing single-repo projects
2. Automatic API mapping (old API → new API)
3. Deprecation warnings for multi-repo projects using single-repo APIs
4. Gradual migration path with clear guidance
"""

import logging
import warnings
from pathlib import Path
from typing import Any, Dict, Optional

from agentos.schemas.project import Project, RepoSpec

logger = logging.getLogger(__name__)


class SingleRepoCompatAdapter:
    """Compatibility adapter for single-repo project access patterns

    Provides backward-compatible property accessors that delegate to the
    new multi-repo API while maintaining the old single-repo interface.

    Usage:
        # Old code (still works):
        project_path = project.path

        # New behavior (automatic under the hood):
        project_path = project.get_default_repo().workspace_relpath
    """

    def __init__(self, project: Project):
        """Initialize adapter for a project

        Args:
            project: Project instance to adapt
        """
        self.project = project

    @property
    def workspace_path(self) -> Optional[str]:
        """Get workspace path (backward compatible accessor)

        Returns:
            Path to the default repository's workspace, or legacy path field

        Behavior:
        - Single-repo: Returns default repo's workspace path
        - Multi-repo: Issues deprecation warning, returns default repo path
        - No repos: Returns legacy project.path if available
        """
        # Check if this is a multi-repo project
        if self.project.is_multi_repo():
            warnings.warn(
                "Accessing workspace_path on a multi-repo project is deprecated. "
                "Use project.get_default_repo().workspace_relpath or iterate over "
                "project.repos for multi-repo projects.",
                DeprecationWarning,
                stacklevel=2
            )
            logger.warning(
                f"Multi-repo project '{self.project.id}' accessed via single-repo API. "
                "Consider updating code to use multi-repo methods."
            )

        # Try to get from default repo
        default_repo = self.project.get_default_repo()
        if default_repo:
            return default_repo.workspace_relpath

        # Fallback to legacy path field
        return self.project.path

    @property
    def is_writable(self) -> bool:
        """Check if the default repository is writable

        Returns:
            True if default repo is writable, False otherwise
        """
        if self.project.is_multi_repo():
            warnings.warn(
                "Checking is_writable on a multi-repo project is deprecated. "
                "Check individual repositories using repo.is_writable.",
                DeprecationWarning,
                stacklevel=2
            )

        default_repo = self.project.get_default_repo()
        if default_repo:
            return default_repo.is_writable

        # Default to True for legacy projects
        return True

    @property
    def remote_url(self) -> Optional[str]:
        """Get remote URL (backward compatible accessor)

        Returns:
            Remote URL of the default repository
        """
        if self.project.is_multi_repo():
            warnings.warn(
                "Accessing remote_url on a multi-repo project is deprecated. "
                "Use project.get_default_repo().remote_url or iterate over project.repos.",
                DeprecationWarning,
                stacklevel=2
            )

        default_repo = self.project.get_default_repo()
        if default_repo:
            return default_repo.remote_url

        return None

    @property
    def default_branch(self) -> str:
        """Get default branch name

        Returns:
            Default branch of the default repository, defaults to 'main'
        """
        if self.project.is_multi_repo():
            warnings.warn(
                "Accessing default_branch on a multi-repo project is deprecated. "
                "Use project.get_default_repo().default_branch.",
                DeprecationWarning,
                stacklevel=2
            )

        default_repo = self.project.get_default_repo()
        if default_repo:
            return default_repo.default_branch

        return "main"

    def get_absolute_path(self, workspace_root: Path) -> Optional[Path]:
        """Get absolute path to the default repository workspace

        Args:
            workspace_root: Root path for project workspaces

        Returns:
            Absolute path to default repository workspace
        """
        default_repo = self.project.get_default_repo()
        if not default_repo:
            # Fallback to legacy path
            if self.project.path:
                return Path(self.project.path).resolve()
            return None

        # Resolve relative path from workspace root
        return (workspace_root / default_repo.workspace_relpath).resolve()


def get_project_workspace_path(
    project: Project,
    workspace_root: Optional[Path] = None
) -> Optional[Path]:
    """Get workspace path for a project (compatibility function)

    This is a helper function to maintain backward compatibility with code
    that expects a single workspace path per project.

    Args:
        project: Project instance
        workspace_root: Optional workspace root path

    Returns:
        Path to the default repository workspace

    Example:
        # Old code pattern:
        project_path = Path(project.path)

        # New code pattern (backward compatible):
        project_path = get_project_workspace_path(project, workspace_root)
    """
    adapter = SingleRepoCompatAdapter(project)

    if workspace_root:
        return adapter.get_absolute_path(workspace_root)

    # Return relative path as string
    path_str = adapter.workspace_path
    if path_str:
        return Path(path_str)

    return None


def ensure_default_repo(project: Project) -> RepoSpec:
    """Ensure project has a default repository (migration helper)

    This function helps migrate legacy single-repo projects that only have
    a 'path' field to the new multi-repo model by creating a default repository.

    Args:
        project: Project instance

    Returns:
        The default repository spec (either existing or newly created)

    Raises:
        ValueError: If project has no repos and no legacy path field

    Example:
        # Migrate legacy project to multi-repo
        project = load_project(project_id)
        default_repo = ensure_default_repo(project)
    """
    # Check if project already has repos
    if project.has_repos():
        default_repo = project.get_default_repo()
        if default_repo:
            return default_repo

    # Try to create from legacy path field
    if not project.path:
        raise ValueError(
            f"Project '{project.id}' has no repositories and no legacy path field. "
            "Cannot create default repository."
        )

    logger.info(
        f"Creating default repository for legacy project '{project.id}' "
        f"from path: {project.path}"
    )

    # Create default repository from legacy path
    from ulid import ULID

    default_repo = RepoSpec(
        repo_id=str(ULID()),
        project_id=project.id,
        name="default",
        workspace_relpath=".",
        remote_url=None,
        default_branch="main",
        is_writable=True,
        metadata={"migrated_from_legacy_path": project.path}
    )

    # Add to project (note: caller needs to persist this)
    project.repos.append(default_repo)

    return default_repo


def check_compatibility_warnings(project: Project) -> list[str]:
    """Check project for potential compatibility issues

    Analyzes a project and returns a list of warnings about deprecated
    usage patterns or potential issues with the multi-repo migration.

    Args:
        project: Project to check

    Returns:
        List of warning messages (empty if no issues)

    Example:
        warnings = check_compatibility_warnings(project)
        for warning in warnings:
            logger.warning(warning)
    """
    warnings_list = []

    # Check for legacy path field on multi-repo projects
    if project.is_multi_repo() and project.path:
        warnings_list.append(
            f"Project '{project.id}' is multi-repo but still has legacy 'path' field. "
            "Consider removing it after migration is complete."
        )

    # Check for projects with no repos
    if not project.has_repos():
        if project.path:
            warnings_list.append(
                f"Project '{project.id}' has no repositories bound. "
                f"Using legacy path: {project.path}. "
                "Consider migrating to multi-repo model."
            )
        else:
            warnings_list.append(
                f"Project '{project.id}' has no repositories and no legacy path. "
                "This project is not functional."
            )

    # Check for duplicate repo names
    if project.has_repos():
        repo_names = [repo.name for repo in project.repos]
        duplicates = [name for name in set(repo_names) if repo_names.count(name) > 1]
        if duplicates:
            warnings_list.append(
                f"Project '{project.id}' has duplicate repository names: {duplicates}"
            )

    return warnings_list


def migrate_project_to_multi_repo(
    project: Project,
    project_repository: Any,  # ProjectRepository type
    workspace_root: Path,
    create_default_repo: bool = True
) -> tuple[bool, list[str]]:
    """Migrate a legacy single-repo project to multi-repo model

    This function performs the actual migration by:
    1. Creating a default repository from project.path if needed
    2. Persisting the repository to database
    3. Validating the migration

    Args:
        project: Project to migrate
        project_repository: ProjectRepository instance for persistence
        workspace_root: Root path for workspace resolution
        create_default_repo: Whether to create default repo if missing

    Returns:
        Tuple of (success: bool, messages: list[str])

    Example:
        from agentos.core.project.repository import ProjectRepository

        repo_crud = ProjectRepository(db_path)
        success, messages = migrate_project_to_multi_repo(
            project, repo_crud, Path("/workspace")
        )
    """
    messages = []

    # Check if already migrated
    if project.has_repos():
        messages.append(f"Project '{project.id}' already has repositories. No migration needed.")
        return True, messages

    # Check if can migrate
    if not project.path and not create_default_repo:
        messages.append(
            f"Project '{project.id}' has no path field and create_default_repo=False. "
            "Cannot migrate."
        )
        return False, messages

    try:
        # Create default repository
        default_repo = ensure_default_repo(project)
        messages.append(
            f"Created default repository: {default_repo.repo_id} "
            f"at workspace_relpath='{default_repo.workspace_relpath}'"
        )

        # Persist to database
        project_repository.add_repo(default_repo)
        messages.append(f"Persisted default repository to database")

        # Validate
        loaded_repo = project_repository.get_repo(project.id, default_repo.repo_id)
        if not loaded_repo:
            messages.append("ERROR: Failed to verify persisted repository")
            return False, messages

        messages.append(f"✓ Project '{project.id}' successfully migrated to multi-repo model")
        return True, messages

    except Exception as e:
        messages.append(f"ERROR: Migration failed: {e}")
        logger.exception(f"Failed to migrate project '{project.id}'")
        return False, messages
