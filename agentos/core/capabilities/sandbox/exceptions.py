"""Sandbox Exception Definitions

Phase D1: Exception hierarchy for sandbox operations.
"""


class SandboxError(Exception):
    """Base exception for sandbox operations"""
    pass


class SandboxUnavailableError(SandboxError):
    """Sandbox backend is not available (e.g., Docker daemon not running)"""
    pass


class SandboxTimeoutError(SandboxError):
    """Sandbox execution exceeded timeout limit"""
    pass


class SandboxResourceError(SandboxError):
    """Sandbox resource limit exceeded or allocation failed"""
    pass


class SandboxIsolationError(SandboxError):
    """Failed to enforce isolation constraints"""
    pass
