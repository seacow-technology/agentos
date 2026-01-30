"""
Shell Runner Configuration

Defines configuration model for shell command execution security.

Part of PR-E4: ShellRunner
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class ShellConfig:
    """
    Configuration for shell command execution

    Defines security boundaries and resource limits for shell commands.

    Example:
        >>> config = ShellConfig(
        ...     allowed_commands=["echo {message}", "date +%Y-%m-%d"],
        ...     work_dir=Path("/tmp/extensions/tools.test"),
        ...     timeout_sec=30,
        ...     max_output_size=10240
        ... )
    """
    # Command allowlist (required)
    allowed_commands: List[str]

    # Working directory (required)
    work_dir: Path

    # Timeouts and limits
    timeout_sec: int = 60  # Maximum execution time
    max_output_size: int = 10240  # Maximum output size in bytes (10KB)

    # Environment control
    env_whitelist: List[str] = field(default_factory=lambda: [
        "PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR"
    ])
    env_extras: Dict[str, str] = field(default_factory=dict)  # Additional env vars

    # Extension context
    extension_id: Optional[str] = None
    extension_version: Optional[str] = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration after initialization"""
        # Ensure work_dir is Path
        if not isinstance(self.work_dir, Path):
            self.work_dir = Path(self.work_dir)

        # Validate allowed_commands is not empty
        if not self.allowed_commands:
            raise ValueError("allowed_commands cannot be empty")

        # Validate timeouts are positive
        if self.timeout_sec <= 0:
            raise ValueError(f"timeout_sec must be positive, got {self.timeout_sec}")

        if self.max_output_size <= 0:
            raise ValueError(f"max_output_size must be positive, got {self.max_output_size}")

        # Validate work_dir exists
        if not self.work_dir.exists():
            raise ValueError(f"work_dir does not exist: {self.work_dir}")

        if not self.work_dir.is_dir():
            raise ValueError(f"work_dir is not a directory: {self.work_dir}")

    @classmethod
    def from_manifest(
        cls,
        manifest: Dict[str, Any],
        work_dir: Path,
        extension_id: str
    ) -> "ShellConfig":
        """
        Create ShellConfig from extension manifest

        Args:
            manifest: Extension manifest dictionary
            work_dir: Extension working directory
            extension_id: Extension ID

        Returns:
            ShellConfig instance

        Raises:
            ValueError: If manifest is invalid

        Example:
            >>> manifest = {
            ...     "capabilities": [{
            ...         "type": "tool",
            ...         "runner": "exec.shell",
            ...         "allowed_commands": ["echo {msg}", "date"],
            ...         "timeout_sec": 30
            ...     }]
            ... }
            >>> config = ShellConfig.from_manifest(
            ...     manifest,
            ...     work_dir=Path("/tmp/ext"),
            ...     extension_id="tools.test"
            ... )
        """
        # Find shell capability in manifest
        shell_capability = None
        for cap in manifest.get("capabilities", []):
            if cap.get("runner") in ("shell", "exec.shell"):
                shell_capability = cap
                break

        if not shell_capability:
            raise ValueError(f"No shell capability found in manifest for {extension_id}")

        # Extract allowed commands
        allowed_commands = shell_capability.get("allowed_commands")
        if not allowed_commands:
            raise ValueError(
                f"Shell capability must declare 'allowed_commands' in manifest for {extension_id}"
            )

        if not isinstance(allowed_commands, list):
            raise ValueError(
                f"'allowed_commands' must be a list in manifest for {extension_id}"
            )

        # Extract optional configuration
        timeout_sec = shell_capability.get("timeout_sec", 60)
        max_output_size = shell_capability.get("max_output_size", 10240)
        env_extras = shell_capability.get("env_extras", {})

        # Get extension version
        extension_version = manifest.get("version", "unknown")

        return cls(
            allowed_commands=allowed_commands,
            work_dir=work_dir,
            timeout_sec=timeout_sec,
            max_output_size=max_output_size,
            env_extras=env_extras,
            extension_id=extension_id,
            extension_version=extension_version
        )

    def is_command_allowed(self, command_template: str) -> bool:
        """
        Check if command template is in allowlist

        Args:
            command_template: Command template to check

        Returns:
            True if command is allowed

        Example:
            >>> config = ShellConfig(
            ...     allowed_commands=["echo {msg}"],
            ...     work_dir=Path("/tmp")
            ... )
            >>> assert config.is_command_allowed("echo {msg}") is True
            >>> assert config.is_command_allowed("rm -rf /") is False
        """
        return command_template in self.allowed_commands

    def get_env_dict(self) -> Dict[str, str]:
        """
        Get environment variable dictionary for subprocess

        Returns only whitelisted variables plus extras.

        Returns:
            Dictionary of environment variables

        Example:
            >>> import os
            >>> os.environ["PATH"] = "/usr/bin"
            >>> config = ShellConfig(
            ...     allowed_commands=["echo hi"],
            ...     work_dir=Path("/tmp"),
            ...     env_extras={"API_KEY": "secret"}
            ... )
            >>> env = config.get_env_dict()
            >>> assert "PATH" in env
            >>> assert "API_KEY" in env
        """
        import os

        env = {}

        # Add whitelisted environment variables
        for var in self.env_whitelist:
            if var in os.environ:
                env[var] = os.environ[var]

        # Add extra environment variables
        env.update(self.env_extras)

        return env

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary

        Returns:
            Dictionary representation
        """
        return {
            "allowed_commands": self.allowed_commands,
            "work_dir": str(self.work_dir),
            "timeout_sec": self.timeout_sec,
            "max_output_size": self.max_output_size,
            "env_whitelist": self.env_whitelist,
            "env_extras": self.env_extras,
            "extension_id": self.extension_id,
            "extension_version": self.extension_version,
            "metadata": self.metadata
        }

    def __repr__(self) -> str:
        return (
            f"ShellConfig(extension={self.extension_id}, "
            f"commands={len(self.allowed_commands)}, "
            f"timeout={self.timeout_sec}s)"
        )
