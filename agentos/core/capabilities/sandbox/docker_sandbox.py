"""Docker Sandbox Implementation

Phase D1: Docker container-based sandbox for extension execution.
"""

import logging
import json
import tempfile
import os
from datetime import datetime
from typing import Optional

from agentos.core.capabilities.runner_base.base import Invocation, RunResult
from agentos.core.capabilities.sandbox.interface import ISandbox
from agentos.core.capabilities.sandbox.config import SandboxConfig
from agentos.core.capabilities.sandbox.exceptions import (
    SandboxError,
    SandboxUnavailableError,
    SandboxTimeoutError,
    SandboxResourceError,
)

logger = logging.getLogger(__name__)


class DockerSandbox(ISandbox):
    """
    Docker container-based sandbox implementation

    Executes extensions in isolated Docker containers with enforced
    resource limits and security constraints.

    Features:
    - Filesystem isolation (read-only root, tmpfs for /tmp)
    - Network isolation (--network=none by default)
    - CPU/Memory limits
    - Capability dropping (--cap-drop ALL)
    - No new privileges (--security-opt no-new-privileges)

    Red Lines:
    - No fallback to direct execution
    - No host filesystem direct access
    - No shared credentials
    - No privilege escalation

    Usage:
        >>> config = SandboxConfig(
        ...     cpu_limit=0.5,
        ...     memory_limit="256m",
        ...     timeout=15,
        ...     network_mode="none"
        ... )
        >>> sandbox = DockerSandbox(config)
        >>> if sandbox.is_available():
        ...     result = sandbox.execute(invocation, timeout=30)

    Examples:
        >>> # Check availability
        >>> sandbox = DockerSandbox()
        >>> print(sandbox.is_available())
        True

        >>> # Execute with custom config
        >>> from agentos.core.capabilities.sandbox.config import HIGH_RISK_CONFIG
        >>> sandbox = DockerSandbox(config=HIGH_RISK_CONFIG)
        >>> result = sandbox.execute(invocation, timeout=15)
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        """
        Initialize Docker sandbox

        Args:
            config: Sandbox configuration (uses defaults if None)

        Raises:
            ImportError: If docker library is not installed
        """
        super().__init__(config)

        # Lazy import docker to avoid dependency if not used
        try:
            import docker
            self._docker = docker
            self._client = None  # Lazy initialization
        except ImportError as e:
            logger.error("Docker library not installed. Install with: pip install docker")
            raise ImportError(
                "Docker library required for DockerSandbox. "
                "Install with: pip install docker"
            ) from e

    def _get_client(self):
        """Get or create Docker client (lazy initialization)"""
        if self._client is None:
            try:
                self._client = self._docker.from_env()
            except Exception as e:
                logger.error(f"Failed to connect to Docker daemon: {e}")
                raise SandboxUnavailableError(
                    f"Cannot connect to Docker daemon: {e}"
                ) from e
        return self._client

    def is_available(self) -> bool:
        """
        Check if Docker daemon is available

        Returns:
            bool: True if Docker daemon is running and accessible

        Examples:
            >>> sandbox = DockerSandbox()
            >>> if sandbox.is_available():
            ...     print("Docker is ready")
        """
        try:
            client = self._get_client()
            client.ping()
            return True
        except Exception as e:
            logger.debug(f"Docker not available: {e}")
            return False

    def health_check(self) -> dict:
        """
        Perform health check on Docker daemon

        Returns:
            dict: Health status with version info

        Examples:
            >>> sandbox = DockerSandbox()
            >>> health = sandbox.health_check()
            >>> print(health["version"])
        """
        try:
            client = self._get_client()
            client.ping()
            version_info = client.version()

            return {
                "available": True,
                "backend": "docker",
                "version": version_info.get("Version", "unknown"),
                "api_version": version_info.get("ApiVersion", "unknown"),
                "error": None,
            }
        except Exception as e:
            logger.error(f"Docker health check failed: {e}")
            return {
                "available": False,
                "backend": "docker",
                "version": None,
                "error": str(e),
            }

    def execute(self, invocation: Invocation, timeout: int) -> RunResult:
        """
        Execute invocation in Docker container

        Steps:
        1. Verify Docker daemon availability
        2. Pull image if needed (or verify exists)
        3. Create container with security constraints
        4. Execute extension code
        5. Capture output and exit code
        6. Clean up container

        Args:
            invocation: Extension invocation request
            timeout: Execution timeout in seconds

        Returns:
            RunResult: Execution result

        Raises:
            SandboxUnavailableError: Docker not available
            SandboxTimeoutError: Execution timeout
            SandboxError: Other execution errors

        Red Lines:
        - NO host filesystem access
        - NO network access (unless explicitly configured)
        - NO privilege escalation
        - NO credential sharing
        """
        started_at = datetime.now()

        # Check availability
        if not self.is_available():
            raise SandboxUnavailableError(
                "Docker daemon not available. HIGH risk execution blocked."
            )

        logger.info(
            f"[Sandbox] Executing {invocation.extension_id}/{invocation.action_id} "
            f"in Docker container (timeout={timeout}s)"
        )

        client = self._get_client()

        # Create execution script
        execution_script = self._create_execution_script(invocation)

        # Get Docker parameters from config
        container_params = self.config.to_docker_params()

        # Override timeout with invocation timeout
        actual_timeout = min(timeout, self.config.timeout)

        try:
            # Ensure image exists
            self._ensure_image(client, self.config.docker_image)

            # Execute in container
            output, exit_code = self._run_container(
                client=client,
                script=execution_script,
                params=container_params,
                timeout=actual_timeout,
            )

            completed_at = datetime.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            success = exit_code == 0

            logger.info(
                f"[Sandbox] Execution completed: exit_code={exit_code}, "
                f"duration={duration_ms}ms"
            )

            return RunResult(
                success=success,
                output=output,
                error=None if success else f"Container exited with code {exit_code}",
                exit_code=exit_code,
                duration_ms=duration_ms,
                started_at=started_at,
                completed_at=completed_at,
                metadata={
                    "sandbox": "docker",
                    "image": self.config.docker_image,
                    "isolated": True,
                }
            )

        except self._docker.errors.ContainerError as e:
            # Container execution error
            completed_at = datetime.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            logger.error(f"[Sandbox] Container error: {e}")

            return RunResult(
                success=False,
                output=e.stderr.decode() if e.stderr else "",
                error=f"Container execution failed: {e}",
                exit_code=e.exit_status,
                duration_ms=duration_ms,
                started_at=started_at,
                completed_at=completed_at,
                metadata={
                    "sandbox": "docker",
                    "error_type": "container_error",
                }
            )

        except self._docker.errors.APIError as e:
            # Docker API error
            completed_at = datetime.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            logger.error(f"[Sandbox] Docker API error: {e}")

            raise SandboxError(f"Docker API error: {e}") from e

        except Exception as e:
            # Unexpected error
            completed_at = datetime.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            logger.error(f"[Sandbox] Unexpected error: {e}")

            raise SandboxError(f"Sandbox execution failed: {e}") from e

    def _ensure_image(self, client, image_name: str):
        """
        Ensure Docker image exists (pull if needed)

        Args:
            client: Docker client
            image_name: Image name to check/pull
        """
        try:
            client.images.get(image_name)
            logger.debug(f"[Sandbox] Image {image_name} already exists")
        except self._docker.errors.ImageNotFound:
            logger.info(f"[Sandbox] Pulling image {image_name}...")
            try:
                client.images.pull(image_name)
                logger.info(f"[Sandbox] Image {image_name} pulled successfully")
            except Exception as e:
                logger.error(f"[Sandbox] Failed to pull image {image_name}: {e}")
                raise SandboxError(f"Failed to pull Docker image: {e}") from e

    def _run_container(
        self,
        client,
        script: str,
        params: dict,
        timeout: int
    ) -> tuple[str, int]:
        """
        Run container with script

        Args:
            client: Docker client
            script: Python script to execute
            params: Container parameters
            timeout: Timeout in seconds

        Returns:
            tuple: (output, exit_code)

        Raises:
            SandboxTimeoutError: Execution timeout
        """
        # Create temporary directory for script
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "execute.py")
            with open(script_path, "w") as f:
                f.write(script)

            # Add volume mount for script
            volumes = {
                tmpdir: {"bind": "/workspace", "mode": "ro"}
            }
            params["volumes"] = volumes
            params["working_dir"] = "/workspace"

            # Command to execute
            command = ["python3", "/workspace/execute.py"]

            try:
                # Run container
                container = client.containers.run(
                    **params,
                    command=command,
                    stdout=True,
                    stderr=True,
                )

                # Container output is combined stdout+stderr
                output = container.decode() if isinstance(container, bytes) else str(container)
                exit_code = 0

                return output, exit_code

            except self._docker.errors.ContainerError as e:
                # Container exited with non-zero code
                output = e.stderr.decode() if e.stderr else ""
                exit_code = e.exit_status
                return output, exit_code

            except Exception as e:
                logger.error(f"[Sandbox] Container execution error: {e}")
                raise

    def _create_execution_script(self, invocation: Invocation) -> str:
        """
        Create Python script for execution

        This is a placeholder implementation. In a real system, this would:
        1. Load the extension code
        2. Parse the action and arguments
        3. Execute the extension in the container

        Args:
            invocation: Extension invocation

        Returns:
            str: Python script content
        """
        # For MVP, create a simple script that demonstrates isolation
        script = f'''#!/usr/bin/env python3
"""
Sandboxed Execution Script
Extension: {invocation.extension_id}
Action: {invocation.action_id}
Session: {invocation.session_id}
"""

import sys
import json

def main():
    """Execute extension in sandbox"""
    print(f"[Sandbox] Executing {invocation.extension_id}/{invocation.action_id}")
    print(f"[Sandbox] Args: {invocation.args}")
    print(f"[Sandbox] Flags: {invocation.flags}")

    # TODO: Load and execute actual extension code
    # For now, just demonstrate isolation

    print("[Sandbox] Execution completed successfully")
    print("[Sandbox] Result: Extension executed in isolated container")

    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"[Sandbox] Error: {{e}}", file=sys.stderr)
        sys.exit(1)
'''
        return script
