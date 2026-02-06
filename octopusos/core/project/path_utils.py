"""Path Validation Utilities

Security utilities for validating file paths and preventing path traversal attacks.

Created for Task #3 Phase 2: Core Service Implementation
"""

import os
from pathlib import Path
from typing import Tuple


def validate_absolute_path(path: str) -> Tuple[bool, str]:
    """Validate that a path is absolute and safe

    Args:
        path: Path to validate

    Returns:
        Tuple of (is_valid, error_message)
            - is_valid: True if path is valid, False otherwise
            - error_message: Error message if invalid, empty string if valid

    Security checks:
        1. Path must be absolute
        2. Path must not contain null bytes
        3. Path must not contain path traversal patterns (..)
        4. Path must be normalizable
    """
    if not path:
        return False, "Path cannot be empty"

    # Check for null bytes
    if "\x00" in path:
        return False, "Path cannot contain null bytes"

    try:
        # Convert to Path object
        path_obj = Path(path)

        # Check if path is absolute
        if not path_obj.is_absolute():
            return False, "Path must be absolute"

        # Normalize the path
        normalized = path_obj.resolve()

        # Check for path traversal by comparing resolved path with original
        # If ".." components were present, the resolved path will be different
        original_parts = path_obj.parts
        normalized_parts = normalized.parts

        # Check if any part is ".."
        if ".." in original_parts:
            return False, "Path cannot contain '..' components"

        return True, ""

    except (ValueError, OSError) as e:
        return False, f"Invalid path: {str(e)}"


def validate_path_exists(path: str) -> Tuple[bool, str]:
    """Validate that a path exists

    Args:
        path: Path to validate

    Returns:
        Tuple of (exists, error_message)
            - exists: True if path exists, False otherwise
            - error_message: Error message if not exists, empty string if exists
    """
    if not path:
        return False, "Path cannot be empty"

    try:
        path_obj = Path(path)
        if not path_obj.exists():
            return False, "Path does not exist"
        return True, ""
    except (ValueError, OSError) as e:
        return False, f"Cannot check path existence: {str(e)}"


def validate_relative_path(workdir: str) -> Tuple[bool, str]:
    """Validate that a workdir is a safe relative path

    Args:
        workdir: Relative path to validate (e.g., "src", "./api", "services/backend")

    Returns:
        Tuple of (is_valid, error_message)
            - is_valid: True if path is valid, False otherwise
            - error_message: Error message if invalid, empty string if valid

    Security checks:
        1. Path must not be absolute
        2. Path must not contain null bytes
        3. Path must not contain path traversal patterns (..)
        4. Path must not escape the base directory
    """
    if not workdir:
        # Empty workdir is valid (means project root)
        return True, ""

    # Check for null bytes
    if "\x00" in workdir:
        return False, "Path cannot contain null bytes"

    try:
        # Convert to Path object
        path_obj = Path(workdir)

        # Check if path is absolute (not allowed for workdir)
        if path_obj.is_absolute():
            return False, "Workdir must be a relative path"

        # Check for ".." components
        if ".." in path_obj.parts:
            return False, "Workdir cannot contain '..' components"

        # Additional check: normalize and ensure it doesn't escape
        # We create a fake base and check if the resolved path is still under it
        fake_base = Path("/fake/base")
        resolved = (fake_base / path_obj).resolve()

        # Check if resolved path is still under fake_base
        try:
            resolved.relative_to(fake_base)
        except ValueError:
            return False, "Workdir would escape base directory"

        return True, ""

    except (ValueError, OSError) as e:
        return False, f"Invalid workdir: {str(e)}"


def validate_artifact_path(kind: str, path: str) -> Tuple[bool, str]:
    """Validate artifact path based on kind

    Args:
        kind: Artifact kind (file/dir/url/log/report)
        path: Path or URL to validate

    Returns:
        Tuple of (is_valid, error_message)
            - is_valid: True if path is valid, False otherwise
            - error_message: Error message if invalid, empty string if valid
    """
    if not path:
        return False, "Path cannot be empty"

    # URL validation
    if kind == "url":
        # Basic URL validation
        if not (path.startswith("http://") or path.startswith("https://")):
            return False, "URL must start with http:// or https://"
        return True, ""

    # File/directory path validation
    if kind in ("file", "dir", "log", "report"):
        # Check for null bytes
        if "\x00" in path:
            return False, "Path cannot contain null bytes"

        try:
            path_obj = Path(path)

            # Path can be absolute or relative, but no ".." allowed
            if ".." in path_obj.parts:
                return False, "Path cannot contain '..' components"

            return True, ""

        except (ValueError, OSError) as e:
            return False, f"Invalid path: {str(e)}"

    return False, f"Unknown artifact kind: {kind}"


def normalize_path(path: str) -> Path:
    """Normalize a path for consistent handling

    Args:
        path: Path to normalize

    Returns:
        Normalized Path object

    Raises:
        ValueError: If path is invalid
    """
    if not path:
        raise ValueError("Path cannot be empty")

    try:
        path_obj = Path(path)
        # Expand user home directory if present
        if "~" in path:
            path_obj = path_obj.expanduser()
        # Resolve to absolute path
        return path_obj.resolve()
    except (ValueError, OSError) as e:
        raise ValueError(f"Cannot normalize path: {str(e)}")
