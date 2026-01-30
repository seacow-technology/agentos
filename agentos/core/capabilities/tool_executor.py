"""
Tool executor for running command-line tools in a controlled environment

Provides sandboxed execution with:
- Working directory isolation
- PATH restrictions
- Environment variable whitelisting
- Timeout control
- Output capture
"""

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional, Dict, Any

from .exceptions import ToolNotFoundError, TimeoutError, SecurityError, ExecutionError
from .models import ToolExecutionResult

# Task #3: Planning Guard integration
from agentos.core.task.planning_guard import get_planning_guard
from agentos.core.task.errors import PlanningSideEffectForbiddenError

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Execute command-line tools in a controlled environment

    Features:
    - Tool path resolution (.agentos/tools/, system PATH)
    - Working directory enforcement
    - Environment variable whitelisting
    - Timeout control
    - Output capture (stdout/stderr)
    """

    # Directories to search for tools
    TOOL_SEARCH_PATHS = [
        Path(".agentos/tools"),
        Path(".agentos/bin"),
    ]

    # Default environment variables to allow
    DEFAULT_ENV_WHITELIST = [
        "PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR",
        "SHELL", "PWD", "TERM"
    ]

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        env_whitelist: Optional[List[str]] = None,
        task_context: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize tool executor

        Args:
            base_dir: Base directory for resolving paths (defaults to cwd)
            env_whitelist: List of environment variables to allow
            task_context: Optional task context (task_id, mode_id, etc.) for planning guard
        """
        self.base_dir = Path(base_dir or os.getcwd())
        self.env_whitelist = env_whitelist or self.DEFAULT_ENV_WHITELIST
        self.task_context = task_context or {}
        self.planning_guard = get_planning_guard()

    def execute_tool(
        self,
        tool_name: str,
        args: List[str],
        work_dir: Path,
        timeout: int = 300,
        env_extra: Optional[Dict[str, str]] = None,
        skip_planning_guard: bool = False
    ) -> ToolExecutionResult:
        """
        Execute a command-line tool in a controlled environment

        Task #3: Planning Guard integrated - shell execution is forbidden in planning phase
        Task #10: Added skip_planning_guard parameter with audit logging

        Args:
            tool_name: Name of the tool to execute (e.g., "postman", "curl")
            args: Command arguments
            work_dir: Working directory for execution
            timeout: Timeout in seconds
            env_extra: Additional environment variables to set
            skip_planning_guard: Skip planning guard check (default False)
                                WARNING: Bypassing guard will be logged

        Returns:
            ToolExecutionResult with execution details

        Raises:
            ToolNotFoundError: If tool executable not found
            TimeoutError: If execution exceeds timeout
            SecurityError: If security policy violation detected
            ExecutionError: If execution fails unexpectedly
            PlanningSideEffectForbiddenError: If called in planning phase
        """
        # Task #10: Audit if planning guard is being skipped
        if skip_planning_guard:
            task_id = self.task_context.get("task_id")
            logger.warning(
                "Planning guard bypassed for tool execution",
                extra={
                    "task_id": task_id,
                    "tool_name": tool_name,
                    "caller": "tool_executor.execute_tool",
                    "reason": "skip_planning_guard=True",
                    "level": "WARN"
                }
            )

        # Task #3: Planning Guard - Check if shell execution is allowed
        # Task #10: Skip check if explicitly requested (but already audited above)
        if not skip_planning_guard:
            try:
                self.planning_guard.assert_operation_allowed(
                    operation_type="shell",
                    operation_name="subprocess.run",
                    task_state=self.task_context.get("task_state"),
                    current_stage=self.task_context.get("current_stage"),
                    mode_id=self.task_context.get("mode_id"),
                    metadata={"tool_name": tool_name, "args": args}
                )
            except PlanningSideEffectForbiddenError as e:
                logger.error(f"Planning guard blocked shell execution: {e.message}")
                raise

        # Resolve tool path
        tool_path = self._resolve_tool_path(tool_name)

        if not tool_path:
            raise ToolNotFoundError(
                f"{tool_name} not found. "
                f"Please ensure the extension is installed correctly."
            )

        # Validate work directory
        work_dir = Path(work_dir).resolve()
        if not self._is_safe_work_dir(work_dir):
            raise SecurityError(
                f"Work directory {work_dir} is not safe or does not exist"
            )

        # Ensure work directory exists
        work_dir.mkdir(parents=True, exist_ok=True)

        # Build command
        command = [str(tool_path)] + args
        command_str = " ".join(command)

        logger.info(
            f"Executing tool: {tool_name}",
            extra={
                "tool": tool_name,
                "command": command_str,
                "work_dir": str(work_dir),
                "timeout": timeout
            }
        )

        # Prepare environment
        env = self._build_environment(env_extra)

        # Execute
        start_time = time.time()

        try:
            result = subprocess.run(
                command,
                cwd=work_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            duration_ms = int((time.time() - start_time) * 1000)

            execution_result = ToolExecutionResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
                command=command_str
            )

            logger.info(
                f"Tool execution completed: {tool_name}",
                extra={
                    "exit_code": result.returncode,
                    "duration_ms": duration_ms,
                    "success": execution_result.success
                }
            )

            return execution_result

        except subprocess.TimeoutExpired as e:
            duration_ms = int((time.time() - start_time) * 1000)

            logger.error(
                f"Tool execution timeout: {tool_name}",
                extra={
                    "timeout": timeout,
                    "duration_ms": duration_ms
                }
            )

            raise TimeoutError(
                f"Command timed out after {timeout} seconds: {command_str}"
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)

            logger.error(
                f"Tool execution failed: {tool_name}",
                extra={
                    "error": str(e),
                    "duration_ms": duration_ms
                },
                exc_info=True
            )

            raise ExecutionError(f"Failed to execute {tool_name}: {e}")

    def _resolve_tool_path(self, tool_name: str) -> Optional[Path]:
        """
        Resolve the full path to a tool executable

        Search order:
        1. .agentos/tools/<tool_name>
        2. .agentos/bin/<tool_name>
        3. System PATH

        Args:
            tool_name: Name of the tool

        Returns:
            Path to the tool or None if not found
        """
        # Check AgentOS tool directories first
        for search_path in self.TOOL_SEARCH_PATHS:
            tool_dir = self.base_dir / search_path
            if tool_dir.exists():
                tool_path = tool_dir / tool_name
                if tool_path.exists() and tool_path.is_file():
                    # Check if executable
                    if os.access(tool_path, os.X_OK):
                        logger.debug(f"Found tool at: {tool_path}")
                        return tool_path

        # Check system PATH
        system_tool = shutil.which(tool_name)
        if system_tool:
            logger.debug(f"Found tool in system PATH: {system_tool}")
            return Path(system_tool)

        logger.warning(f"Tool not found: {tool_name}")
        return None

    def _is_safe_work_dir(self, work_dir: Path) -> bool:
        """
        Check if a working directory is safe to use

        Args:
            work_dir: Path to check

        Returns:
            True if safe, False otherwise
        """
        work_dir = work_dir.resolve()

        # Must be absolute
        if not work_dir.is_absolute():
            return False

        # Allow temp directories (for testing and demos)
        import tempfile
        temp_dir = Path(tempfile.gettempdir()).resolve()
        try:
            work_dir.relative_to(temp_dir)
            return True
        except ValueError:
            pass

        # Also allow /tmp directly (macOS symlink)
        try:
            work_dir.relative_to(Path("/tmp").resolve())
            return True
        except ValueError:
            pass

        # Must be under .agentos/ or user's home directory
        agentos_dir = self.base_dir / ".agentos"

        try:
            # Try to resolve relative to .agentos
            work_dir.relative_to(agentos_dir)
            return True
        except ValueError:
            pass

        # Check if under home directory (for user-specified paths)
        try:
            home = Path.home()
            work_dir.relative_to(home)
            return True
        except ValueError:
            pass

        return False

    def _build_environment(
        self,
        env_extra: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Build a restricted environment for tool execution

        Args:
            env_extra: Additional environment variables to set

        Returns:
            Environment dictionary
        """
        env = {}

        # Copy whitelisted variables from current environment
        for var_name in self.env_whitelist:
            if var_name in os.environ:
                env[var_name] = os.environ[var_name]

        # Add tool paths to PATH
        tool_paths = [
            str(self.base_dir / path)
            for path in self.TOOL_SEARCH_PATHS
            if (self.base_dir / path).exists()
        ]

        if tool_paths:
            existing_path = env.get("PATH", "")
            env["PATH"] = ":".join(tool_paths + [existing_path])

        # Add extra variables
        if env_extra:
            env.update(env_extra)

        return env

    def check_tool_exists(self, tool_name: str) -> bool:
        """
        Check if a tool is available

        Args:
            tool_name: Name of the tool

        Returns:
            True if tool exists, False otherwise
        """
        return self._resolve_tool_path(tool_name) is not None

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a tool

        Args:
            tool_name: Name of the tool

        Returns:
            Dictionary with tool information or None if not found
        """
        tool_path = self._resolve_tool_path(tool_name)

        if not tool_path:
            return None

        return {
            "name": tool_name,
            "path": str(tool_path),
            "exists": tool_path.exists(),
            "executable": os.access(tool_path, os.X_OK),
            "size_bytes": tool_path.stat().st_size if tool_path.exists() else 0,
        }
