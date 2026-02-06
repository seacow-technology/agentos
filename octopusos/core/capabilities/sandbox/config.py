"""Sandbox Configuration

Phase D1: Configuration model for sandbox execution parameters.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SandboxConfig:
    """
    Configuration for sandbox execution

    This defines the security boundaries and resource limits for
    sandboxed extension execution.

    Backend Options:
    - docker: Docker container isolation (primary implementation)
    - wasm: WASM runtime (future)

    Examples:
        >>> # Default configuration
        >>> config = SandboxConfig()

        >>> # Strict configuration for HIGH risk
        >>> config = SandboxConfig(
        ...     cpu_limit=0.5,
        ...     memory_limit="256m",
        ...     timeout=15,
        ...     network_mode="none",
        ...     allow_tmp=False
        ... )
    """

    # Backend selection
    enabled: bool = True
    backend: str = "docker"  # "docker" or "wasm"

    # Docker-specific configuration
    docker_image: str = "python:3.13-slim"
    cpu_limit: float = 1.0  # CPU cores (fractional allowed)
    memory_limit: str = "512m"  # Memory limit (e.g., "512m", "1g")
    timeout: int = 30  # Execution timeout in seconds
    network_mode: str = "none"  # Docker network mode ("none", "bridge", etc.)

    # Security options
    read_only_root: bool = True  # Mount root filesystem as read-only
    no_new_privileges: bool = True  # Prevent privilege escalation
    drop_all_caps: bool = True  # Drop all Linux capabilities

    # Filesystem isolation
    allow_tmp: bool = True  # Allow /tmp directory (writable)
    readonly_mounts: Optional[List[str]] = field(default_factory=list)  # Additional read-only mounts

    # Environment
    environment_vars: Optional[dict] = field(default_factory=dict)  # Environment variables to pass

    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.backend not in ("docker", "wasm"):
            raise ValueError(f"Invalid backend: {self.backend}. Must be 'docker' or 'wasm'")

        if self.cpu_limit <= 0:
            raise ValueError(f"cpu_limit must be positive, got {self.cpu_limit}")

        if self.timeout <= 0:
            raise ValueError(f"timeout must be positive, got {self.timeout}")

        if self.network_mode not in ("none", "bridge", "host"):
            raise ValueError(f"Invalid network_mode: {self.network_mode}")

    def to_docker_params(self) -> dict:
        """
        Convert configuration to Docker API parameters

        Returns:
            dict: Parameters for Docker container creation
        """
        params = {
            "image": self.docker_image,
            "network_mode": self.network_mode,
            "mem_limit": self.memory_limit,
            "nano_cpus": int(self.cpu_limit * 1e9),  # Convert to nanocpus
            "detach": False,
            "remove": True,  # Auto-remove container after execution
            "security_opt": [],
        }

        # Add security options
        if self.no_new_privileges:
            params["security_opt"].append("no-new-privileges")

        # Add capability drops
        if self.drop_all_caps:
            params["cap_drop"] = ["ALL"]

        # Add read-only root filesystem
        if self.read_only_root:
            params["read_only"] = True

            # If read-only root, we need tmpfs for /tmp if allowed
            if self.allow_tmp:
                params["tmpfs"] = {"/tmp": "rw,noexec,nosuid,size=100m"}

        # Add environment variables
        if self.environment_vars:
            params["environment"] = self.environment_vars

        return params


# Predefined configurations for different risk levels
HIGH_RISK_CONFIG = SandboxConfig(
    cpu_limit=0.5,
    memory_limit="256m",
    timeout=15,
    network_mode="none",
    allow_tmp=True,
    read_only_root=True,
    no_new_privileges=True,
    drop_all_caps=True,
)

MEDIUM_RISK_CONFIG = SandboxConfig(
    cpu_limit=1.0,
    memory_limit="512m",
    timeout=30,
    network_mode="none",
    allow_tmp=True,
    read_only_root=True,
    no_new_privileges=True,
    drop_all_caps=True,
)

LOW_RISK_CONFIG = SandboxConfig(
    cpu_limit=2.0,
    memory_limit="1g",
    timeout=60,
    network_mode="bridge",  # Allow network for low risk
    allow_tmp=True,
    read_only_root=False,
    no_new_privileges=True,
    drop_all_caps=False,
)
