"""Path Filtering for Task Repository Access

This module provides path filtering capabilities to restrict file access
within repository scopes. It integrates with TaskRepoContext to enforce
access boundaries at runtime.

Key Features:
1. Glob pattern matching (**, *, ?, etc.)
2. Exclusion patterns (! prefix)
3. Directory matching
4. Efficient pattern compilation and caching

Created for Phase 4: .gitignore and change boundary control
"""

import fnmatch
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class PathFilter:
    """Path filter with glob pattern matching

    Supports glob patterns with ** for recursive matching.
    Supports exclusion patterns with ! prefix.

    Examples:
        # Include all Python files
        PathFilter(["**/*.py"])

        # Include src directory, exclude tests
        PathFilter(["src/**", "!src/tests/**"])

        # Include multiple patterns
        PathFilter(["src/**/*.py", "lib/**/*.py", "!**/*_test.py"])

    Attributes:
        patterns: List of glob patterns (positive and negative)
        _includes: Compiled positive patterns
        _excludes: Compiled negative patterns
    """

    patterns: List[str]
    _includes: Optional[List[str]] = None
    _excludes: Optional[List[str]] = None

    def __post_init__(self):
        """Compile patterns on initialization"""
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile patterns into include and exclude lists"""
        includes = []
        excludes = []

        for pattern in self.patterns:
            pattern = pattern.strip()
            if not pattern:
                continue

            # Check for exclusion prefix
            if pattern.startswith("!"):
                # Exclusion pattern
                excludes.append(pattern[1:].strip())
            else:
                # Inclusion pattern
                includes.append(pattern)

        self._includes = includes
        self._excludes = excludes

        logger.debug(
            f"Compiled PathFilter: {len(includes)} includes, {len(excludes)} excludes"
        )

    def is_allowed(self, file_path: str | Path) -> bool:
        """Check if a file path is allowed by this filter

        Algorithm:
        1. If no include patterns, deny by default
        2. Check if path matches any include pattern (allow)
        3. Check if path matches any exclude pattern (deny)
        4. Return final decision

        Args:
            file_path: File path to check (relative or absolute)

        Returns:
            True if path is allowed, False otherwise
        """
        if not self._includes:
            # No include patterns means deny all
            return False

        # Normalize path (convert to string, forward slashes)
        path_str = self._normalize_path(file_path)

        # Deny empty paths
        if not path_str:
            return False

        # Check includes first
        is_included = False
        for pattern in self._includes:
            if self._match_pattern(path_str, pattern):
                is_included = True
                break

        if not is_included:
            return False

        # Check excludes
        for pattern in self._excludes:
            if self._match_pattern(path_str, pattern):
                logger.debug(f"Path {path_str} excluded by pattern {pattern}")
                return False

        return True

    def filter_files(self, file_list: List[str]) -> List[str]:
        """Filter a list of file paths

        Args:
            file_list: List of file paths

        Returns:
            Filtered list of file paths
        """
        return [f for f in file_list if self.is_allowed(f)]

    def get_allowed_count(self, file_list: List[str]) -> int:
        """Count how many files in the list are allowed

        Args:
            file_list: List of file paths

        Returns:
            Number of allowed files
        """
        return sum(1 for f in file_list if self.is_allowed(f))

    def _normalize_path(self, file_path: str | Path) -> str:
        """Normalize path for pattern matching

        Converts Path to string, uses forward slashes.

        Args:
            file_path: File path to normalize

        Returns:
            Normalized path string
        """
        if isinstance(file_path, Path):
            # Use as_posix() to get forward slashes on all platforms
            path_str = file_path.as_posix()
        else:
            # Replace backslashes with forward slashes
            path_str = str(file_path).replace("\\", "/")

        # Return empty string as-is (for validation)
        if not path_str:
            return ""

        return path_str

    def _match_pattern(self, path: str, pattern: str) -> bool:
        """Match a path against a glob pattern

        Supports:
        - * (matches any characters except /)
        - ** (matches any characters including /)
        - ? (matches single character)
        - [abc] (character set)
        - Directory patterns (pattern/ matches directory and contents)

        Args:
            path: Normalized path string
            pattern: Glob pattern

        Returns:
            True if path matches pattern
        """
        # Handle directory patterns (trailing /)
        if pattern.endswith("/"):
            # Match directory and all contents
            dir_pattern = pattern.rstrip("/")
            if path.startswith(dir_pattern + "/") or path == dir_pattern:
                return True

        # Use pathlib.PurePath.match() for glob matching
        # This properly handles ** patterns
        from pathlib import PurePath

        try:
            pure_path = PurePath(path)
            # PurePath.match() matches from the right side, so we need to check carefully
            # For patterns like "src/**/*.py", we need to ensure it matches the full path structure

            # If pattern contains /**/, it's a recursive pattern
            if "**" in pattern:
                # Use PurePath.match which handles ** correctly
                return pure_path.match(pattern)
            else:
                # For non-recursive patterns, use fnmatch with path segment matching
                # * should not match /
                import re

                # Convert pattern to regex
                regex_pattern = pattern

                # Escape regex special chars
                for char in ['.', '+', '(', ')', '{', '}', '[', ']', '^', '$', '|', '\\']:
                    regex_pattern = regex_pattern.replace(char, '\\' + char)

                # Replace * with [^/]*
                regex_pattern = regex_pattern.replace("*", "[^/]*")

                # Replace ? with [^/]
                regex_pattern = regex_pattern.replace("?", "[^/]")

                # Anchor
                regex_pattern = f"^{regex_pattern}$"

                return bool(re.match(regex_pattern, path))

        except Exception as e:
            # Fall back to fnmatch
            logger.debug(f"Pattern matching failed for '{pattern}' on '{path}': {e}, falling back to fnmatch")
            return fnmatch.fnmatch(path, pattern)

    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        return {
            "patterns": self.patterns,
            "includes": self._includes,
            "excludes": self._excludes,
        }

    def __repr__(self) -> str:
        """String representation"""
        return f"PathFilter(patterns={self.patterns})"


class PathFilterBuilder:
    """Builder for creating PathFilter instances

    Provides a fluent API for constructing path filters.

    Example:
        filter = (PathFilterBuilder()
            .include("src/**/*.py")
            .include("lib/**/*.py")
            .exclude("**/*_test.py")
            .exclude("**/test_*.py")
            .build())
    """

    def __init__(self):
        """Initialize builder"""
        self._patterns: List[str] = []

    def include(self, pattern: str) -> "PathFilterBuilder":
        """Add an inclusion pattern

        Args:
            pattern: Glob pattern to include

        Returns:
            Self for chaining
        """
        self._patterns.append(pattern)
        return self

    def exclude(self, pattern: str) -> "PathFilterBuilder":
        """Add an exclusion pattern

        Args:
            pattern: Glob pattern to exclude (! prefix added automatically)

        Returns:
            Self for chaining
        """
        if not pattern.startswith("!"):
            pattern = f"!{pattern}"
        self._patterns.append(pattern)
        return self

    def include_all(self) -> "PathFilterBuilder":
        """Include all files (match everything)

        Returns:
            Self for chaining
        """
        self._patterns.append("**/*")
        return self

    def build(self) -> PathFilter:
        """Build the PathFilter

        Returns:
            PathFilter instance
        """
        return PathFilter(patterns=self._patterns.copy())


def create_path_filter(patterns: List[str]) -> PathFilter:
    """Factory function for creating PathFilter

    Args:
        patterns: List of glob patterns

    Returns:
        PathFilter instance
    """
    return PathFilter(patterns=patterns)


def create_full_access_filter() -> PathFilter:
    """Create a path filter that allows all files

    Returns:
        PathFilter instance with full access
    """
    return PathFilter(patterns=["**/*"])


def create_readonly_filter(allowed_patterns: List[str]) -> PathFilter:
    """Create a read-only path filter

    Args:
        allowed_patterns: List of patterns to allow for reading

    Returns:
        PathFilter instance
    """
    return PathFilter(patterns=allowed_patterns)
