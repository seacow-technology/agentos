"""
Capability Runner - Main orchestrator for extension capability execution

This is the entry point for executing extension capabilities. It:
1. Receives a CommandRoute from the Slash Command Router
2. Selects the appropriate executor based on runner type
3. Executes the capability with proper context
4. Returns a formatted result to the user
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

from .exceptions import ExecutionError, CapabilityError
from .executors import (
    BaseExecutor,
    ExecToolExecutor,
    AnalyzeResponseExecutor,
    AnalyzeSchemaExecutor,
)
from .models import (
    CommandRoute,
    ExecutionContext,
    CapabilityResult,
)

logger = logging.getLogger(__name__)


class CapabilityRunner:
    """
    Main capability execution orchestrator

    Responsibilities:
    - Route commands to appropriate executors
    - Manage execution context
    - Handle errors gracefully
    - Format results for user display
    - Log execution for audit
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        llm_client=None
    ):
        """
        Initialize capability runner

        Args:
            base_dir: Base directory for AgentOS (defaults to cwd)
            llm_client: LLM client for analysis capabilities
        """
        self.base_dir = Path(base_dir or Path.cwd())

        # Initialize executors
        self.executors: Dict[str, BaseExecutor] = {
            "exec": ExecToolExecutor(),
            "analyze.response": AnalyzeResponseExecutor(llm_client),
            "analyze.schema": AnalyzeSchemaExecutor(),
        }

        logger.info(
            f"CapabilityRunner initialized with {len(self.executors)} executors"
        )

    def execute(
        self,
        route: CommandRoute,
        context: ExecutionContext
    ) -> CapabilityResult:
        """
        Execute an extension capability

        This is the main entry point for capability execution.

        Process:
        1. Validate inputs
        2. Get appropriate executor
        3. Execute capability
        4. Format result for display
        5. Log execution

        Args:
            route: Parsed command route from Slash Router
            context: Execution context with session info

        Returns:
            CapabilityResult with formatted output

        Raises:
            CapabilityError: If execution fails critically
        """
        started_at = datetime.now()

        logger.info(
            "Executing capability",
            extra={
                "extension_id": route.extension_id,
                "command": route.command_name,
                "action": route.action_id,
                "runner": route.runner,
                "session_id": context.session_id
            }
        )

        try:
            # Get executor for this runner type
            executor = self.get_executor(route.runner)

            if not executor:
                raise ExecutionError(
                    f"No executor found for runner type: {route.runner}"
                )

            # Execute capability
            result = executor.execute(route, context)

            # Convert to CapabilityResult
            capability_result = CapabilityResult(
                success=result.success,
                output=result.output,
                error=result.error,
                metadata=result.metadata,
                started_at=started_at,
                completed_at=datetime.now()
            )

            # Log execution
            self._log_execution(route, context, capability_result)

            return capability_result

        except Exception as e:
            logger.error(
                f"Capability execution failed: {route.command_name}",
                extra={
                    "error": str(e),
                    "extension_id": route.extension_id
                },
                exc_info=True
            )

            # Return error result
            error_result = CapabilityResult(
                success=False,
                output="",
                error=self._format_error(e),
                metadata={
                    "error_type": type(e).__name__,
                    "extension_id": route.extension_id,
                    "command": route.command_name
                },
                started_at=started_at,
                completed_at=datetime.now()
            )

            self._log_execution(route, context, error_result)

            return error_result

    def get_executor(self, runner_type: str) -> Optional[BaseExecutor]:
        """
        Get the appropriate executor for a runner type

        Args:
            runner_type: Runner type (e.g., "exec.postman_cli", "analyze.response")

        Returns:
            Executor instance or None if not found
        """
        # Check for exact match first
        if runner_type in self.executors:
            return self.executors[runner_type]

        # Check for prefix match (e.g., "exec.postman_cli" -> "exec")
        for prefix, executor in self.executors.items():
            if runner_type.startswith(prefix):
                # Verify executor supports this runner
                if executor.supports_runner(runner_type):
                    return executor

        logger.warning(f"No executor found for runner type: {runner_type}")
        return None

    def register_executor(self, name: str, executor: BaseExecutor) -> None:
        """
        Register a custom executor

        Args:
            name: Executor name/prefix
            executor: Executor instance
        """
        self.executors[name] = executor
        logger.info(f"Registered custom executor: {name}")

    def _format_error(self, error: Exception) -> str:
        """
        Format an error for user display

        Args:
            error: Exception

        Returns:
            Formatted error message
        """
        error_type = type(error).__name__
        error_msg = str(error)

        # Provide user-friendly messages
        if "ToolNotFoundError" in error_type:
            return (
                f"{error_msg}\n\n"
                "Hint: Make sure the extension is installed correctly. "
                "You may need to reinstall the extension."
            )
        elif "TimeoutError" in error_type:
            return (
                f"{error_msg}\n\n"
                "Hint: The command took too long. Try increasing the timeout "
                "or simplifying the operation."
            )
        elif "SecurityError" in error_type:
            return (
                f"{error_msg}\n\n"
                "Hint: This operation violates security policies. "
                "Check the command and work directory."
            )
        else:
            return f"{error_msg}"

    def _log_execution(
        self,
        route: CommandRoute,
        context: ExecutionContext,
        result: CapabilityResult
    ) -> None:
        """
        Log capability execution for audit

        Args:
            route: Command route
            context: Execution context
            result: Capability result
        """
        log_entry = {
            "event": "capability_executed",
            "extension_id": route.extension_id,
            "command": route.command_name,
            "action": route.action_id,
            "runner": route.runner,
            "session_id": context.session_id,
            "user_id": context.user_id,
            "success": result.success,
            "duration_seconds": result.duration_seconds,
            "error": result.error if not result.success else None,
        }

        if result.success:
            logger.info("Capability executed successfully", extra=log_entry)
        else:
            logger.error("Capability execution failed", extra=log_entry)

    def get_stats(self) -> Dict[str, any]:
        """
        Get runner statistics

        Returns:
            Dictionary with statistics
        """
        return {
            "executor_count": len(self.executors),
            "executors": list(self.executors.keys()),
            "base_dir": str(self.base_dir)
        }


# Global runner instance (optional)
_runner_instance: Optional[CapabilityRunner] = None


def get_capability_runner(
    base_dir: Optional[Path] = None,
    llm_client=None
) -> CapabilityRunner:
    """
    Get or create the global capability runner instance

    Args:
        base_dir: Base directory for AgentOS
        llm_client: LLM client for analysis

    Returns:
        CapabilityRunner instance
    """
    global _runner_instance

    if _runner_instance is None:
        _runner_instance = CapabilityRunner(base_dir, llm_client)

    return _runner_instance
