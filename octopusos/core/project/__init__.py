"""Project management module

Handles multi-repository project bindings and workspace management.
"""

from .compat import (
    SingleRepoCompatAdapter,
    check_compatibility_warnings,
    ensure_default_repo,
    get_project_workspace_path,
    migrate_project_to_multi_repo,
)
from .repository import (
    ProjectRepository,
    RepoContext,
    RepoRegistry,
)
# v0.31 Services
from .service import ProjectService
from .repo_service import RepoService
from .errors import (
    ProjectError,
    RepoError,
    ProjectNotFoundError,
    ProjectNameConflictError,
    ProjectHasTasksError,
    RepoNotFoundError,
    RepoNameConflictError,
    RepoNotInProjectError,
    InvalidPathError,
    PathNotFoundError,
)

__all__ = [
    "ProjectRepository",
    "RepoContext",
    "RepoRegistry",
    # Compatibility layer
    "SingleRepoCompatAdapter",
    "get_project_workspace_path",
    "ensure_default_repo",
    "check_compatibility_warnings",
    "migrate_project_to_multi_repo",
    # v0.31 Services
    "ProjectService",
    "RepoService",
    # Errors
    "ProjectError",
    "RepoError",
    "ProjectNotFoundError",
    "ProjectNameConflictError",
    "ProjectHasTasksError",
    "RepoNotFoundError",
    "RepoNameConflictError",
    "RepoNotInProjectError",
    "InvalidPathError",
    "PathNotFoundError",
]
