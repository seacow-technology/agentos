"""Sandbox Interface Definition

Phase D1: Abstract interface for sandbox implementations.
"""

from abc import ABC, abstractmethod
from typing import Optional

from agentos.core.capabilities.runner_base.base import Invocation, RunResult
from agentos.core.capabilities.sandbox.config import SandboxConfig


class ISandbox(ABC):
    """
    Abstract interface for sandbox implementations

    Defines the contract that all sandbox backends must implement.
    Sandbox implementations provide runtime isolation for extension execution.

    Implementations:
    - DockerSandbox: Docker container-based isolation
    - WASMSandbox: WASM runtime isolation (future)

    Red Lines:
    - Sandbox must enforce strict isolation
    - Sandbox failure must NOT fallback to direct execution
    - All resource limits must be enforced

    Usage:
        >>> sandbox = DockerSandbox(config=SandboxConfig())
        >>> if sandbox.is_available():
        ...     result = sandbox.execute(invocation, timeout=30)
        ... else:
        ...     # Block execution - do NOT fallback
        ...     raise SandboxUnavailableError("Cannot execute HIGH risk without sandbox")
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        """
        Initialize sandbox

        Args:
            config: Sandbox configuration (uses defaults if None)
        """
        self.config = config or SandboxConfig()

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if sandbox backend is available

        Returns:
            bool: True if sandbox can be used for execution

        Examples:
            >>> sandbox = DockerSandbox()
            >>> if sandbox.is_available():
            ...     print("Docker daemon is running")
            ... else:
            ...     print("Docker daemon not available")
        """
        pass

    @abstractmethod
    def execute(self, invocation: Invocation, timeout: int) -> RunResult:
        """
        Execute invocation in sandbox

        This method runs the extension code in an isolated environment
        with enforced resource limits and security constraints.

        Args:
            invocation: Extension invocation request
            timeout: Execution timeout in seconds

        Returns:
            RunResult: Execution result with output and status

        Raises:
            SandboxUnavailableError: Sandbox backend not available
            SandboxTimeoutError: Execution exceeded timeout
            SandboxResourceError: Resource limits exceeded
            SandboxError: Other sandbox-related errors

        Red Lines:
        - MUST enforce filesystem isolation
        - MUST enforce network isolation (if configured)
        - MUST enforce resource limits
        - MUST NOT expose host credentials
        - MUST clean up resources after execution

        Examples:
            >>> sandbox = DockerSandbox()
            >>> invocation = Invocation(
            ...     extension_id="tools.untrusted",
            ...     action_id="run",
            ...     session_id="session-123",
            ...     user_id="user-456"
            ... )
            >>> result = sandbox.execute(invocation, timeout=30)
            >>> print(f"Exit code: {result.exit_code}")
        """
        pass

    @abstractmethod
    def health_check(self) -> dict:
        """
        Perform health check on sandbox backend

        Returns:
            dict: Health status information
                - available: bool
                - backend: str
                - version: Optional[str]
                - error: Optional[str]

        Examples:
            >>> sandbox = DockerSandbox()
            >>> health = sandbox.health_check()
            >>> if health["available"]:
            ...     print(f"Backend version: {health['version']}")
        """
        pass
