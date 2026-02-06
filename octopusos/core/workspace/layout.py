"""Workspace Layout Specification

Defines workspace root structure and repository path resolution for
multi-repository projects.

Directory Structure:
    projects/
      <project_slug>/
        <repo_relpath_1>/    # e.g., be/
        <repo_relpath_2>/    # e.g., fe/
        .agentos/            # AgentOS metadata

Example:
    projects/
      my-app/
        be/                  # backend repo
        fe/                  # frontend repo
        docs/                # docs repo
        .agentos/
          workspace.json
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from agentos.schemas.project import RepoSpec

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceRoot:
    """Workspace root configuration

    Represents the top-level workspace directory containing all projects.
    """

    root_path: Path

    def __post_init__(self):
        """Validate and normalize root path"""
        self.root_path = Path(self.root_path).expanduser().resolve()

    def get_projects_dir(self) -> Path:
        """Get the projects directory

        Returns:
            Path to projects/ directory
        """
        return self.root_path / "projects"

    def ensure_projects_dir(self) -> Path:
        """Ensure projects directory exists

        Returns:
            Path to projects/ directory
        """
        projects_dir = self.get_projects_dir()
        projects_dir.mkdir(parents=True, exist_ok=True)
        return projects_dir


class WorkspaceLayout:
    """Workspace layout manager

    Manages workspace directory structure and path resolution for
    multi-repository projects.

    Conventions:
    - Workspace root: <workspace_root>/projects/
    - Project root: <workspace_root>/projects/<project_slug>/
    - Repository path: <project_root>/<workspace_relpath>/
    - Metadata: <project_root>/.agentos/
    """

    def __init__(self, workspace_root: Path):
        """Initialize workspace layout

        Args:
            workspace_root: Workspace root directory
        """
        self.workspace_root = WorkspaceRoot(workspace_root)
        logger.info(f"WorkspaceLayout initialized: {self.workspace_root.root_path}")

    def get_project_root(self, project_id: str) -> Path:
        """Get project root directory

        Args:
            project_id: Project identifier (used as directory name)

        Returns:
            Absolute path to project root

        Example:
            /workspace/projects/my-app/
        """
        return self.workspace_root.get_projects_dir() / project_id

    def get_repo_path(self, project_id: str, repo: RepoSpec) -> Path:
        """Get absolute path for a repository

        Args:
            project_id: Project identifier
            repo: Repository specification

        Returns:
            Absolute path to repository workspace

        Example:
            /workspace/projects/my-app/be/
        """
        project_root = self.get_project_root(project_id)

        # Resolve workspace_relpath relative to project root
        repo_path = project_root / repo.workspace_relpath

        # Normalize path (resolve .., ., etc.)
        repo_path = repo_path.resolve()

        return repo_path

    def get_metadata_dir(self, project_id: str) -> Path:
        """Get AgentOS metadata directory for a project

        Args:
            project_id: Project identifier

        Returns:
            Path to .agentos/ metadata directory

        Example:
            /workspace/projects/my-app/.agentos/
        """
        return self.get_project_root(project_id) / ".agentos"

    def ensure_project_root(self, project_id: str) -> Path:
        """Ensure project root directory exists

        Args:
            project_id: Project identifier

        Returns:
            Path to project root
        """
        project_root = self.get_project_root(project_id)
        project_root.mkdir(parents=True, exist_ok=True)

        logger.info(f"Ensured project root: {project_root}")
        return project_root

    def ensure_metadata_dir(self, project_id: str) -> Path:
        """Ensure metadata directory exists

        Args:
            project_id: Project identifier

        Returns:
            Path to metadata directory
        """
        metadata_dir = self.get_metadata_dir(project_id)
        metadata_dir.mkdir(parents=True, exist_ok=True)

        # Create .gitignore to exclude metadata from git
        gitignore = metadata_dir / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("*\n!.gitignore\n")

        logger.info(f"Ensured metadata dir: {metadata_dir}")
        return metadata_dir

    def save_workspace_manifest(self, project_id: str, repos: List[RepoSpec]):
        """Save workspace manifest to metadata directory

        Args:
            project_id: Project identifier
            repos: List of repository specifications
        """
        metadata_dir = self.ensure_metadata_dir(project_id)
        manifest_path = metadata_dir / "workspace.json"

        manifest = {
            "project_id": project_id,
            "workspace_version": "1.0",
            "repositories": [
                {
                    "repo_id": repo.repo_id,
                    "name": repo.name,
                    "workspace_relpath": repo.workspace_relpath,
                    "remote_url": repo.remote_url,
                    "role": repo.role.value,
                    "is_writable": repo.is_writable,
                }
                for repo in repos
            ],
        }

        manifest_path.write_text(json.dumps(manifest, indent=2))
        logger.info(f"Saved workspace manifest: {manifest_path}")

    def load_workspace_manifest(self, project_id: str) -> Optional[Dict]:
        """Load workspace manifest from metadata directory

        Args:
            project_id: Project identifier

        Returns:
            Manifest dictionary or None if not found
        """
        manifest_path = self.get_metadata_dir(project_id) / "workspace.json"

        if not manifest_path.exists():
            return None

        try:
            manifest = json.loads(manifest_path.read_text())
            logger.info(f"Loaded workspace manifest: {manifest_path}")
            return manifest
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load workspace manifest: {e}")
            return None

    def get_path_mapping(self, project_id: str, repos: List[RepoSpec]) -> Dict[str, Path]:
        """Get mapping of repository names to absolute paths

        Args:
            project_id: Project identifier
            repos: List of repository specifications

        Returns:
            Dictionary mapping repo name to absolute path
        """
        return {
            repo.name: self.get_repo_path(project_id, repo)
            for repo in repos
        }

    def is_within_project_root(self, project_id: str, path: Path) -> bool:
        """Check if a path is within the project root

        Args:
            project_id: Project identifier
            path: Path to check

        Returns:
            True if path is within project root
        """
        project_root = self.get_project_root(project_id)

        try:
            # Resolve both paths and check if path is relative to project_root
            resolved_path = path.resolve()
            resolved_root = project_root.resolve()

            return resolved_path.is_relative_to(resolved_root)
        except (ValueError, RuntimeError):
            return False

    def validate_layout(self, project_id: str, repos: List[RepoSpec]) -> "ValidationResult":
        """Validate workspace layout for a project

        Checks:
        - Path conflicts between repositories
        - Paths outside project root
        - Invalid path formats

        Args:
            project_id: Project identifier
            repos: List of repository specifications

        Returns:
            ValidationResult with any conflicts found
        """
        from agentos.core.workspace.validation import ValidationResult, Conflict, ConflictType

        conflicts = []

        # Check for duplicate names
        repo_names = [repo.name for repo in repos]
        if len(repo_names) != len(set(repo_names)):
            conflicts.append(Conflict(
                type=ConflictType.DUPLICATE_NAME,
                message="Duplicate repository names detected",
                details={"names": [name for name in repo_names if repo_names.count(name) > 1]},
            ))

        # Check for path conflicts and invalid paths
        seen_paths = {}
        repo_paths = []

        for repo in repos:
            try:
                repo_path = self.get_repo_path(project_id, repo)
                normalized = repo_path.resolve()

                # Check if path is within project root
                if not self.is_within_project_root(project_id, normalized):
                    conflicts.append(Conflict(
                        type=ConflictType.PATH_OUTSIDE_ROOT,
                        message=f"Repository '{repo.name}' path is outside project root",
                        repo_name=repo.name,
                        path=str(normalized),
                        details={
                            "workspace_relpath": repo.workspace_relpath,
                            "project_root": str(self.get_project_root(project_id)),
                        },
                    ))

                # Check for exact path duplicates
                normalized_str = str(normalized)
                if normalized_str in seen_paths:
                    conflicts.append(Conflict(
                        type=ConflictType.PATH_DUPLICATE,
                        message=f"Repositories '{seen_paths[normalized_str]}' and '{repo.name}' use the same path",
                        repo_name=repo.name,
                        path=normalized_str,
                        details={"other_repo": seen_paths[normalized_str]},
                    ))
                else:
                    seen_paths[normalized_str] = repo.name
                    repo_paths.append((repo.name, normalized))

            except (ValueError, RuntimeError) as e:
                conflicts.append(Conflict(
                    type=ConflictType.INVALID_PATH,
                    message=f"Invalid path for repository '{repo.name}': {e}",
                    repo_name=repo.name,
                    path=repo.workspace_relpath,
                    details={"error": str(e)},
                ))

        # Check for path overlaps (one repo path is parent of another)
        for i, (name1, path1) in enumerate(repo_paths):
            for name2, path2 in repo_paths[i + 1:]:
                try:
                    # Check if path1 is parent of path2 or vice versa
                    if path2.is_relative_to(path1):
                        conflicts.append(Conflict(
                            type=ConflictType.PATH_OVERLAP,
                            message=f"Repository '{name2}' is nested within '{name1}'",
                            repo_name=name2,
                            path=str(path2),
                            details={"parent_repo": name1, "parent_path": str(path1)},
                        ))
                    elif path1.is_relative_to(path2):
                        conflicts.append(Conflict(
                            type=ConflictType.PATH_OVERLAP,
                            message=f"Repository '{name1}' is nested within '{name2}'",
                            repo_name=name1,
                            path=str(path1),
                            details={"parent_repo": name2, "parent_path": str(path2)},
                        ))
                except (ValueError, RuntimeError):
                    # is_relative_to can raise ValueError on different drives (Windows)
                    pass

        return ValidationResult(
            is_valid=len(conflicts) == 0,
            conflicts=conflicts,
        )
