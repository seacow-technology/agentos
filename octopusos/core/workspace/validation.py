"""Workspace Validation and Conflict Detection

Provides conflict checking for workspace operations including:
- Directory existence checks
- Remote URL consistency checks
- Dirty repository detection
- Path overlap detection
"""

import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from agentos.schemas.project import RepoSpec

logger = logging.getLogger(__name__)


class ConflictType(str, Enum):
    """Types of workspace conflicts"""

    # Path conflicts
    PATH_EXISTS = "path_exists"  # Directory already exists
    PATH_DUPLICATE = "path_duplicate"  # Two repos use same path
    PATH_OVERLAP = "path_overlap"  # One repo path contains another
    PATH_OUTSIDE_ROOT = "path_outside_root"  # Path is outside project root
    INVALID_PATH = "invalid_path"  # Invalid path format

    # Git conflicts
    REMOTE_MISMATCH = "remote_mismatch"  # Existing git remote differs
    DIRTY_REPO = "dirty_repo"  # Repository has uncommitted changes
    NOT_A_GIT_REPO = "not_a_git_repo"  # Directory exists but not a git repo

    # Metadata conflicts
    DUPLICATE_NAME = "duplicate_name"  # Duplicate repository names
    PROJECT_EXISTS = "project_exists"  # Project already imported with different config


@dataclass
class Conflict:
    """Represents a workspace conflict

    Attributes:
        type: Type of conflict
        message: Human-readable error message
        repo_name: Repository name (if applicable)
        path: File system path involved
        expected_value: Expected value (for mismatches)
        actual_value: Actual value (for mismatches)
        details: Additional conflict details
        suggestions: Suggested remediation actions
    """

    type: ConflictType
    message: str
    repo_name: Optional[str] = None
    path: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    details: Dict = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)

    def format_error(self) -> str:
        """Format conflict as user-friendly error message

        Returns:
            Multi-line formatted error message
        """
        lines = [f"❌ Conflict: {self.message}"]

        if self.repo_name:
            lines.append(f"   Repository: {self.repo_name}")

        if self.path:
            lines.append(f"   Path: {self.path}")

        if self.expected_value:
            lines.append(f"   Expected: {self.expected_value}")

        if self.actual_value:
            lines.append(f"   Actual: {self.actual_value}")

        if self.details:
            for key, value in self.details.items():
                lines.append(f"   {key}: {value}")

        if self.suggestions:
            lines.append("")
            lines.append("   Suggestions:")
            for suggestion in self.suggestions:
                lines.append(f"   - {suggestion}")

        return "\n".join(lines)


@dataclass
class ValidationResult:
    """Result of workspace validation

    Attributes:
        is_valid: True if no conflicts found
        conflicts: List of detected conflicts
        warnings: Non-blocking warnings
    """

    is_valid: bool
    conflicts: List[Conflict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_conflict(self, conflict: Conflict):
        """Add a conflict to the result"""
        self.conflicts.append(conflict)
        self.is_valid = False

    def add_warning(self, message: str):
        """Add a warning to the result"""
        self.warnings.append(message)

    def format_report(self) -> str:
        """Format validation report

        Returns:
            Multi-line formatted report
        """
        lines = []

        if self.is_valid:
            lines.append("✅ Workspace validation passed")
        else:
            lines.append(f"❌ Workspace validation failed ({len(self.conflicts)} conflicts)")

        if self.conflicts:
            lines.append("")
            for conflict in self.conflicts:
                lines.append(conflict.format_error())
                lines.append("")

        if self.warnings:
            lines.append("⚠️  Warnings:")
            for warning in self.warnings:
                lines.append(f"   • {warning}")

        return "\n".join(lines)


class WorkspaceValidator:
    """Workspace validator with conflict detection

    Provides methods to check for various workspace conflicts before
    performing operations like cloning or importing repositories.
    """

    def __init__(self):
        """Initialize workspace validator"""
        pass

    def check_path_exists(self, path: Path, repo: RepoSpec) -> Optional[Conflict]:
        """Check if directory already exists

        Args:
            path: Directory path to check
            repo: Repository specification

        Returns:
            Conflict if directory exists, None otherwise
        """
        if not path.exists():
            return None

        # Directory exists - check if it's empty
        try:
            is_empty = not any(path.iterdir())
        except OSError:
            is_empty = False

        if is_empty:
            # Empty directory is not a conflict
            return None

        return Conflict(
            type=ConflictType.PATH_EXISTS,
            message="Directory already exists and is not empty",
            repo_name=repo.name,
            path=str(path),
            suggestions=[
                f"Remove the directory: rm -rf {path}",
                "Or use --force to overwrite (WARNING: will delete local changes)",
                "Or choose a different workspace path",
            ],
        )

    def check_remote_mismatch(
        self,
        path: Path,
        repo: RepoSpec,
    ) -> Optional[Conflict]:
        """Check if existing git remote differs from expected

        Args:
            path: Repository path to check
            repo: Repository specification with expected remote_url

        Returns:
            Conflict if remote mismatches, None otherwise
        """
        if not path.exists() or not (path / ".git").exists():
            return None

        if not repo.remote_url:
            # No expected remote URL - skip check
            return None

        # Get current remote URL
        try:
            result = subprocess.run(
                ["git", "-C", str(path), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            actual_remote = result.stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # No remote or git command failed
            return None

        # Normalize URLs for comparison (remove trailing .git, normalize protocols)
        expected_norm = self._normalize_git_url(repo.remote_url)
        actual_norm = self._normalize_git_url(actual_remote)

        if expected_norm != actual_norm:
            return Conflict(
                type=ConflictType.REMOTE_MISMATCH,
                message="Existing git remote URL differs from expected",
                repo_name=repo.name,
                path=str(path),
                expected_value=repo.remote_url,
                actual_value=actual_remote,
                suggestions=[
                    f"Remove the directory: rm -rf {path}",
                    "Or use --force to overwrite",
                    "Or update the project config to use existing remote",
                ],
            )

        return None

    def check_dirty_repo(self, path: Path, repo: RepoSpec) -> Optional[Conflict]:
        """Check if repository has uncommitted changes

        Args:
            path: Repository path to check
            repo: Repository specification

        Returns:
            Conflict if repo is dirty, None otherwise
        """
        if not path.exists() or not (path / ".git").exists():
            return None

        try:
            # Check if working tree is clean
            result = subprocess.run(
                ["git", "-C", str(path), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )

            output = result.stdout.strip()

            if output:
                # Repository has uncommitted changes
                return Conflict(
                    type=ConflictType.DIRTY_REPO,
                    message="Repository has uncommitted changes",
                    repo_name=repo.name,
                    path=str(path),
                    details={"uncommitted_files": len(output.split("\n"))},
                    suggestions=[
                        "Commit or stash your changes",
                        "Or use --force to discard local changes (WARNING: destructive)",
                        "Or skip this repository during import",
                    ],
                )

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Failed to check git status for {path}: {e}")
            return None

        return None

    def check_not_a_git_repo(self, path: Path, repo: RepoSpec) -> Optional[Conflict]:
        """Check if directory exists but is not a git repository

        Args:
            path: Directory path to check
            repo: Repository specification

        Returns:
            Conflict if directory exists but is not a git repo, None otherwise
        """
        if not path.exists():
            return None

        # Directory exists - check if it's a git repo
        if not (path / ".git").exists():
            # Check if it's empty
            try:
                is_empty = not any(path.iterdir())
            except OSError:
                is_empty = False

            if not is_empty:
                return Conflict(
                    type=ConflictType.NOT_A_GIT_REPO,
                    message="Directory exists but is not a git repository",
                    repo_name=repo.name,
                    path=str(path),
                    suggestions=[
                        f"Initialize git repo: git -C {path} init",
                        f"Or remove the directory: rm -rf {path}",
                        "Or use --force to overwrite",
                    ],
                )

        return None

    def check_path_overlap(self, repos: List[RepoSpec], layout) -> List[Conflict]:
        """Check for overlapping paths between repositories

        Args:
            repos: List of repository specifications
            layout: WorkspaceLayout instance for path resolution

        Returns:
            List of path overlap conflicts
        """
        conflicts = []
        repo_paths = []

        # Resolve all repository paths
        for repo in repos:
            try:
                # Assuming layout has a project_id - we'll need to pass it
                # For now, use normalized paths
                from pathlib import Path
                normalized = Path(repo.workspace_relpath).resolve()
                repo_paths.append((repo.name, normalized))
            except (ValueError, RuntimeError) as e:
                logger.warning(f"Failed to resolve path for {repo.name}: {e}")
                continue

        # Check each pair for overlaps
        for i, (name1, path1) in enumerate(repo_paths):
            for name2, path2 in repo_paths[i + 1:]:
                try:
                    # Check if one path is a parent of the other
                    if path2.is_relative_to(path1) and path2 != path1:
                        conflicts.append(Conflict(
                            type=ConflictType.PATH_OVERLAP,
                            message=f"Repository '{name2}' is nested within '{name1}'",
                            repo_name=name2,
                            path=str(path2),
                            details={
                                "parent_repo": name1,
                                "parent_path": str(path1),
                            },
                            suggestions=[
                                "Choose non-overlapping workspace paths",
                                "Nested repositories are not supported",
                            ],
                        ))
                    elif path1.is_relative_to(path2) and path1 != path2:
                        conflicts.append(Conflict(
                            type=ConflictType.PATH_OVERLAP,
                            message=f"Repository '{name1}' is nested within '{name2}'",
                            repo_name=name1,
                            path=str(path1),
                            details={
                                "parent_repo": name2,
                                "parent_path": str(path2),
                            },
                            suggestions=[
                                "Choose non-overlapping workspace paths",
                                "Nested repositories are not supported",
                            ],
                        ))
                except (ValueError, RuntimeError):
                    # is_relative_to can raise on different drives
                    pass

        return conflicts

    def validate_workspace(
        self,
        project_id: str,
        repos: List[RepoSpec],
        layout,
        check_existing: bool = True,
    ) -> ValidationResult:
        """Validate entire workspace for a project

        Args:
            project_id: Project identifier
            repos: List of repository specifications
            layout: WorkspaceLayout instance
            check_existing: Check existing directories (default: True)

        Returns:
            ValidationResult with all detected conflicts
        """
        result = ValidationResult(is_valid=True)

        # Use layout's validation for path conflicts
        layout_result = layout.validate_layout(project_id, repos)
        result.conflicts.extend(layout_result.conflicts)
        if not layout_result.is_valid:
            result.is_valid = False

        # Check existing filesystem state
        if check_existing:
            for repo in repos:
                repo_path = layout.get_repo_path(project_id, repo)

                # Check if path exists
                conflict = self.check_path_exists(repo_path, repo)
                if conflict:
                    result.add_conflict(conflict)

                # Check remote mismatch
                conflict = self.check_remote_mismatch(repo_path, repo)
                if conflict:
                    result.add_conflict(conflict)

                # Check dirty repo
                conflict = self.check_dirty_repo(repo_path, repo)
                if conflict:
                    result.add_conflict(conflict)

                # Check not a git repo
                conflict = self.check_not_a_git_repo(repo_path, repo)
                if conflict:
                    result.add_conflict(conflict)

        return result

    def check_idempotency(
        self,
        project_id: str,
        new_repos: List[RepoSpec],
        existing_repos: Optional[List[RepoSpec]],
    ) -> ValidationResult:
        """Check if import is idempotent (same config as existing)

        Args:
            project_id: Project identifier
            new_repos: New repository specifications
            existing_repos: Existing repository specifications (None if no project)

        Returns:
            ValidationResult indicating if import can proceed idempotently
        """
        result = ValidationResult(is_valid=True)

        if existing_repos is None:
            # No existing project - import is valid
            return result

        # Compare repository configurations
        existing_map = {repo.name: repo for repo in existing_repos}
        new_map = {repo.name: repo for repo in new_repos}

        # Check for added repos
        added = set(new_map.keys()) - set(existing_map.keys())
        if added:
            result.add_warning(f"New repositories will be added: {', '.join(added)}")

        # Check for removed repos
        removed = set(existing_map.keys()) - set(new_map.keys())
        if removed:
            result.add_conflict(Conflict(
                type=ConflictType.PROJECT_EXISTS,
                message="Repositories from existing project will be removed",
                details={"removed_repos": list(removed)},
                suggestions=[
                    "Update project config to include all existing repositories",
                    "Or manually remove repositories before re-importing",
                ],
            ))

        # Check for modified repos
        for name in set(existing_map.keys()) & set(new_map.keys()):
            existing = existing_map[name]
            new = new_map[name]

            differences = []

            if existing.remote_url != new.remote_url:
                differences.append(f"remote_url: {existing.remote_url} -> {new.remote_url}")

            if existing.workspace_relpath != new.workspace_relpath:
                differences.append(f"path: {existing.workspace_relpath} -> {new.workspace_relpath}")

            if existing.role != new.role:
                differences.append(f"role: {existing.role.value} -> {new.role.value}")

            if differences:
                result.add_conflict(Conflict(
                    type=ConflictType.PROJECT_EXISTS,
                    message=f"Repository '{name}' configuration differs from existing",
                    repo_name=name,
                    details={"differences": differences},
                    suggestions=[
                        "Update project config to match existing configuration",
                        "Or remove project and re-import with new config",
                    ],
                ))

        return result

    @staticmethod
    def _normalize_git_url(url: str) -> str:
        """Normalize git URL for comparison

        Args:
            url: Git URL to normalize

        Returns:
            Normalized URL
        """
        # Remove trailing .git
        url = url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]

        # Normalize SSH vs HTTPS
        # git@github.com:user/repo -> github.com/user/repo
        # https://github.com/user/repo -> github.com/user/repo

        if url.startswith("git@"):
            # SSH format: git@github.com:user/repo
            url = url[4:]  # Remove git@
            url = url.replace(":", "/", 1)  # Replace first : with /

        if url.startswith("https://"):
            url = url[8:]  # Remove https://

        if url.startswith("http://"):
            url = url[7:]  # Remove http://

        return url.lower()
