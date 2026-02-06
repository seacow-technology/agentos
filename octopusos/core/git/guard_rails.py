"""Change Boundary Guard Rails

This module provides pre-commit style validation for file changes.
It enforces security boundaries to prevent accidental commits of:
- Sensitive files (.env, credentials, secrets)
- Protected system files (.git/, AgentOS config)
- Files outside path_filters scope

Key Features:
1. Forbidden file pattern detection
2. Path filter boundary enforcement
3. Actionable error messages with hints
4. Integration with TaskRepoContext

Created for Phase 4: .gitignore and change boundary control
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from agentos.core.task.repo_context import TaskRepoContext

logger = logging.getLogger(__name__)


@dataclass
class Violation:
    """Represents a single validation violation

    Attributes:
        file_path: Path to the violating file
        rule: Rule that was violated
        message: Human-readable violation message
        severity: Violation severity (error, warning)
        hint: Optional hint for fixing the violation
    """

    file_path: str
    rule: str
    message: str
    severity: str = "error"  # error, warning
    hint: Optional[str] = None

    def format_error(self) -> str:
        """Format violation as user-friendly error message"""
        icon = "❌" if self.severity == "error" else "⚠️"
        lines = [
            f"{icon} {self.message}",
            f"   File: {self.file_path}",
            f"   Rule: {self.rule}",
        ]

        if self.hint:
            lines.append(f"   Hint: {self.hint}")

        return "\n".join(lines)


@dataclass
class ValidationResult:
    """Result of change validation

    Attributes:
        is_valid: True if all validations passed
        violations: List of violations found
        checked_files: Number of files checked
        warnings: List of warning messages
    """

    is_valid: bool
    violations: List[Violation] = field(default_factory=list)
    checked_files: int = 0
    warnings: List[str] = field(default_factory=list)

    def add_violation(self, violation: Violation) -> None:
        """Add a violation to the result"""
        self.violations.append(violation)
        if violation.severity == "error":
            self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning message"""
        self.warnings.append(message)

    def format_report(self) -> str:
        """Format validation result as user-friendly report"""
        if self.is_valid and not self.warnings:
            return f"✅ All {self.checked_files} files passed validation"

        lines = []

        if self.violations:
            lines.append(f"Found {len(self.violations)} violations:\n")
            for violation in self.violations:
                lines.append(violation.format_error())
                lines.append("")

        if self.warnings:
            lines.append(f"Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  ⚠️  {warning}")

        return "\n".join(lines)


class ChangeGuardRails:
    """Validates file changes against security and access rules

    This class provides pre-commit style checks to prevent:
    1. Modifying forbidden files (credentials, .git/, etc.)
    2. Writing outside path_filters scope
    3. Committing sensitive information

    It integrates with TaskRepoContext to enforce task-level boundaries.
    """

    # Default forbidden file patterns (case-insensitive)
    DEFAULT_FORBIDDEN_PATTERNS = [
        # Git internals
        r"\.git/.*",
        r"\.gitconfig$",

        # Environment and secrets
        r"\.env$",
        r"\.env\..*",  # .env.local, .env.production, etc.
        r"secrets\.ya?ml$",
        r"credentials\.json$",
        r"credentials\.ya?ml$",
        r".*\.pem$",
        r".*\.key$",
        r".*\.p12$",
        r".*\.pfx$",
        r"id_rsa$",
        r"id_ed25519$",

        # AgentOS config (protected unless explicitly allowed)
        r"\.agentos/config\.ya?ml$",
        r"\.agentos/credentials\.db$",

        # CI/CD secrets
        r"\.github/.*secret.*",
        r"\.gitlab-ci\.yml.*secret.*",

        # Cloud credentials
        r"gcloud-key\.json$",
        r"aws-credentials\.json$",
        r"azure-credentials\.json$",

        # Database credentials
        r"\.pgpass$",
        r"\.my\.cnf$",

        # Kubernetes secrets
        r".*-secret\.ya?ml$",
        r"kubeconfig$",
    ]

    def __init__(
        self,
        forbidden_patterns: Optional[List[str]] = None,
        allow_patterns: Optional[List[str]] = None,
    ):
        """Initialize guard rails

        Args:
            forbidden_patterns: Custom forbidden file patterns (regex)
            allow_patterns: Patterns to explicitly allow (overrides forbidden)
        """
        self.forbidden_patterns = forbidden_patterns or self.DEFAULT_FORBIDDEN_PATTERNS
        self.allow_patterns = allow_patterns or []

        # Compile regex patterns
        self._forbidden_regex = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.forbidden_patterns
        ]
        self._allow_regex = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.allow_patterns
        ]

        logger.debug(
            f"Initialized ChangeGuardRails: "
            f"{len(self.forbidden_patterns)} forbidden, "
            f"{len(self.allow_patterns)} allowed"
        )

    def validate_changes(
        self,
        repo_context: TaskRepoContext,
        changed_files: List[str],
    ) -> ValidationResult:
        """Validate a list of changed files against all rules

        Checks:
        1. Files are within path_filters scope
        2. Files are not in forbidden patterns list
        3. Files pass security checks

        Args:
            repo_context: Task repository context
            changed_files: List of file paths (relative to repo)

        Returns:
            ValidationResult with violations and warnings
        """
        result = ValidationResult(is_valid=True, checked_files=len(changed_files))

        for file_path in changed_files:
            # Check 1: Path filter scope
            if not repo_context.is_path_allowed(file_path):
                result.add_violation(
                    Violation(
                        file_path=file_path,
                        rule="path_filter",
                        message=f"File is outside allowed scope for task {repo_context.task_id}",
                        severity="error",
                        hint=f"Task scope: {repo_context.scope.value}, "
                        f"filters: {repo_context.path_filters}",
                    )
                )
                continue

            # Check 2: Forbidden patterns
            violations = self.check_forbidden_patterns([file_path])
            for violation in violations:
                result.add_violation(violation)

            # Check 3: Security checks (e.g., detect hardcoded secrets)
            # Note: This is a placeholder for future enhancements
            # Could integrate with tools like truffleHog or detect-secrets

        return result

    def check_forbidden_patterns(self, changed_files: List[str]) -> List[Violation]:
        """Check if any files match forbidden patterns

        Args:
            changed_files: List of file paths to check

        Returns:
            List of violations
        """
        violations = []

        for file_path in changed_files:
            # Normalize path (forward slashes, handle backslashes on Windows)
            if isinstance(file_path, Path):
                normalized_path = file_path.as_posix()
            else:
                # Convert backslashes to forward slashes
                normalized_path = str(file_path).replace("\\", "/")

            # Check if explicitly allowed (allow patterns override forbidden)
            is_allowed = False
            for allow_regex in self._allow_regex:
                if allow_regex.search(normalized_path):
                    is_allowed = True
                    logger.debug(f"File {file_path} explicitly allowed")
                    break

            if is_allowed:
                continue

            # Check against forbidden patterns
            for forbidden_regex in self._forbidden_regex:
                if forbidden_regex.search(normalized_path):
                    violations.append(
                        Violation(
                            file_path=file_path,
                            rule="forbidden_file",
                            message=f"Cannot modify protected file: {file_path}",
                            severity="error",
                            hint=self._get_forbidden_file_hint(file_path),
                        )
                    )
                    break

        return violations

    def is_file_forbidden(self, file_path: str) -> bool:
        """Check if a single file is forbidden

        Args:
            file_path: File path to check

        Returns:
            True if file is forbidden
        """
        violations = self.check_forbidden_patterns([file_path])
        return len(violations) > 0

    def get_forbidden_files(self, file_list: List[str]) -> List[str]:
        """Get list of forbidden files from a file list

        Args:
            file_list: List of file paths

        Returns:
            List of forbidden file paths
        """
        violations = self.check_forbidden_patterns(file_list)
        return [v.file_path for v in violations]

    def _get_forbidden_file_hint(self, file_path: str) -> str:
        """Get helpful hint for forbidden file violation

        Args:
            file_path: Path to forbidden file

        Returns:
            Hint message
        """
        normalized = file_path.lower()

        if ".git/" in normalized or ".gitconfig" in normalized:
            return "Modifying Git internals is not allowed. Use git commands instead."

        if ".env" in normalized or "secret" in normalized or "credential" in normalized:
            return (
                "This file contains sensitive information. "
                "Use environment variables or a secure vault instead."
            )

        if ".pem" in normalized or ".key" in normalized:
            return (
                "Private keys should never be committed. "
                "Use SSH agent or credential management tools."
            )

        if ".agentos/" in normalized:
            return (
                "AgentOS configuration files are protected. "
                "Modify them through agentos CLI instead."
            )

        return "This file is protected by security policies."

    def add_forbidden_pattern(self, pattern: str) -> None:
        """Add a custom forbidden pattern

        Args:
            pattern: Regex pattern to add
        """
        self.forbidden_patterns.append(pattern)
        self._forbidden_regex.append(re.compile(pattern, re.IGNORECASE))
        logger.debug(f"Added forbidden pattern: {pattern}")

    def add_allow_pattern(self, pattern: str) -> None:
        """Add a custom allow pattern

        Allow patterns override forbidden patterns.

        Args:
            pattern: Regex pattern to add
        """
        self.allow_patterns.append(pattern)
        self._allow_regex.append(re.compile(pattern, re.IGNORECASE))
        logger.debug(f"Added allow pattern: {pattern}")


def create_default_guard_rails() -> ChangeGuardRails:
    """Create guard rails with default settings

    Returns:
        ChangeGuardRails instance
    """
    return ChangeGuardRails()


def create_strict_guard_rails() -> ChangeGuardRails:
    """Create guard rails with strict security settings

    Adds extra patterns for maximum security.

    Returns:
        ChangeGuardRails instance with strict rules
    """
    strict_patterns = ChangeGuardRails.DEFAULT_FORBIDDEN_PATTERNS + [
        # Additional strict patterns
        r".*password.*",
        r".*token.*",
        r".*api[_-]?key.*",
        r".*private.*\.key$",
        r"\.npmrc$",
        r"\.pypirc$",
    ]

    return ChangeGuardRails(forbidden_patterns=strict_patterns)
