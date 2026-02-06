"""Container-based sandbox with Docker/Podman support."""

import shutil
from pathlib import Path
from typing import Optional, Literal
from enum import Enum

from agentos.core.infra.container_client import (
    ContainerClient,
    ContainerClientFactory,
    ContainerEngine
)
from agentos.core.infra.tool_executor import ToolExecutor


class ContainerSandbox:
    """
    Container-based sandbox for isolated execution.
    
    Features:
    - Auto-detect Docker/Podman
    - Automatic fallback to worktree
    - Read-only repository mount
    - Isolated execution environment
    """
    
    def __init__(
        self,
        repo_path: Path,
        prefer_engine: Optional[Literal["docker", "podman"]] = None
    ):
        """
        Initialize container sandbox.
        
        Args:
            repo_path: Repository path to mount
            prefer_engine: Preferred container engine (None = auto-detect)
        """
        self.repo_path = Path(repo_path)
        self.container_id: Optional[str] = None
        self.engine = ContainerClientFactory.detect_engine(prefer_engine)
        self.container_client = ContainerClient(self.engine) if self.engine != ContainerEngine.NONE else None
        self.fallback_sandbox: Optional["Sandbox"] = None
    
    
    def create(
        self,
        run_id: str,
        image: str = "python:3.13-slim",
        working_dir: str = "/workspace"
    ) -> Optional[str]:
        """
        Create container sandbox.
        
        Args:
            run_id: Execution run ID
            image: Container image to use
            working_dir: Working directory in container
        
        Returns:
            Container ID if successful, None if fallback needed
        """
        if self.engine == ContainerEngine.NONE or not self.container_client:
            return self._create_fallback(run_id)
        
        try:
            # Create container with read-only repo mount
            volumes = {
                str(self.repo_path): {
                    'bind': working_dir,
                    'mode': 'ro'
                }
            }
            
            self.container_id = self.container_client.create_container(
                name=f"agentos_{run_id}",
                image=image,
                volumes=volumes,
                working_dir=working_dir,
                auto_remove=True
            )
            return self.container_id
            
        except Exception as e:
            print(f"Container creation failed: {e}, falling back to worktree")
            return self._create_fallback(run_id)
    
    def _create_fallback(self, run_id: str) -> Optional[str]:
        """Create fallback worktree sandbox."""
        from .sandbox import Sandbox
        
        self.fallback_sandbox = Sandbox(self.repo_path)
        worktree_path = self.fallback_sandbox.create_worktree(run_id)
        return f"worktree:{worktree_path}"
    
    def execute(
        self,
        command: list[str],
        timeout: Optional[int] = None
    ) -> tuple[int, str, str]:
        """
        Execute command in sandbox.
        
        Args:
            command: Command to execute
            timeout: Timeout in seconds
        
        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        if self.container_id and not self.container_id.startswith("worktree:") and self.container_client:
            # Execute in container
            return self.container_client.exec_command(self.container_id, command, timeout)
        
        elif self.fallback_sandbox:
            # Execute in worktree - 使用 ToolExecutor 执行任意命令
            # 这是系统边界：需要执行用户提供的命令
            try:
                returncode, stdout, stderr = ToolExecutor.execute_command(
                    command,
                    cwd=self.fallback_sandbox.worktree_path,
                    timeout=timeout,
                    capture_output=True
                )
                return returncode, stdout, stderr
            except Exception as e:
                return 1, "", str(e)
        
        else:
            return 1, "", "Sandbox not initialized"
    
    def cleanup(self) -> None:
        """Clean up sandbox resources."""
        if self.container_id and not self.container_id.startswith("worktree:") and self.container_client:
            self.container_client.stop_container(self.container_id, timeout=10)
        
        if self.fallback_sandbox:
            self.fallback_sandbox.remove_worktree()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
    
    def get_sandbox_type(self) -> str:
        """Get sandbox type for audit logging."""
        if self.container_id:
            if self.container_id.startswith("worktree:"):
                return "worktree_fallback"
            else:
                return f"container_{self.engine.value}"
        return "none"
    
    def is_high_risk_allowed(self) -> bool:
        """Check if high-risk operations are allowed."""
        # High-risk operations only allowed in container
        return (
            self.container_id is not None and 
            not self.container_id.startswith("worktree:")
        )


def create_sandbox(
    repo_path: Path,
    run_id: str,
    prefer_engine: Optional[str] = None,
    image: str = "python:3.13-slim"
) -> ContainerSandbox:
    """
    Create and initialize a sandbox.
    
    Args:
        repo_path: Repository path
        run_id: Execution run ID
        prefer_engine: Preferred container engine
        image: Container image
    
    Returns:
        Initialized ContainerSandbox
    """
    sandbox = ContainerSandbox(repo_path, prefer_engine=prefer_engine)
    sandbox.create(run_id, image=image)
    return sandbox


def check_container_available() -> dict[str, bool]:
    """
    Check which container engines are available.
    
    Returns:
        Dictionary of engine availability
    """
    availability = {}
    
    for engine in ["docker", "podman"]:
        client = ContainerClient(ContainerEngine(engine))
        availability[engine] = client.check_available()
    
    return availability
