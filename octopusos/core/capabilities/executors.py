"""
Capability executors

Base class and concrete implementations for different runner types.
"""

import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from .exceptions import ExecutionError, ToolNotFoundError
from .models import (
    CommandRoute,
    ExecutionContext,
    ExecutionResult,
)
from .response_store import get_response_store
from .tool_executor import ToolExecutor
from .permissions import Permission, get_permission_checker

logger = logging.getLogger(__name__)


class BaseExecutor(ABC):
    """
    Base class for capability executors

    Each executor implements a specific runner type (exec, analyze, etc.)
    """

    @abstractmethod
    def execute(
        self,
        route: CommandRoute,
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Execute a capability

        Args:
            route: Command route with execution details
            context: Execution context

        Returns:
            ExecutionResult with output and metadata
        """
        pass

    @abstractmethod
    def supports_runner(self, runner: str) -> bool:
        """
        Check if this executor supports a runner type

        Args:
            runner: Runner type string (e.g., "exec.postman_cli")

        Returns:
            True if supported, False otherwise
        """
        pass


class ExecToolExecutor(BaseExecutor):
    """
    Execute command-line tools (exec.xxx runner type)

    Handles runner types like:
    - exec.postman_cli
    - exec.curl
    - exec.ffmpeg
    """

    RUNNER_PREFIX = "exec."

    def __init__(self, tool_executor: Optional[ToolExecutor] = None):
        """
        Initialize executor

        Args:
            tool_executor: Tool executor instance (created if not provided)
        """
        self.tool_executor = tool_executor or ToolExecutor()
        self.response_store = get_response_store()

    def supports_runner(self, runner: str) -> bool:
        """Check if runner starts with 'exec.'"""
        return runner.startswith(self.RUNNER_PREFIX)

    def execute(
        self,
        route: CommandRoute,
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Execute a command-line tool

        Process:
        1. Check permissions (exec_shell required for tool execution)
        2. Extract tool name from runner (exec.postman_cli -> postman)
        3. Build command arguments from route
        4. Execute tool in controlled environment
        5. Store response for potential follow-up commands
        6. Return formatted result

        Args:
            route: Command route
            context: Execution context

        Returns:
            ExecutionResult
        """
        # Step 1: Check permissions before execution
        declared_permissions = getattr(route, 'permissions', [])
        if not declared_permissions:
            # Try to get from metadata
            declared_permissions = route.metadata.get('permissions', [])

        if declared_permissions:
            checker = get_permission_checker()
            granted, reason = checker.has_all_permissions(
                ext_id=route.extension_id,
                permissions=[Permission.EXEC_SHELL],
                declared_permissions=declared_permissions
            )

            if not granted:
                error_msg = f"Permission denied: {reason}"
                logger.error(
                    f"Extension execution denied: {route.extension_id}",
                    extra={
                        "extension_id": route.extension_id,
                        "action": route.action_id,
                        "reason": reason,
                        "required_permission": "exec_shell",
                        "audit_event": "EXT_RUN_DENIED"
                    }
                )
                return ExecutionResult(
                    success=False,
                    output="",
                    error=error_msg,
                    metadata={
                        "denial_reason": reason,
                        "required_permission": "exec_shell"
                    }
                )

        # Step 2: Extract tool name from runner
        tool_name = self._extract_tool_name(route.runner)

        logger.info(
            f"Executing tool: {tool_name}",
            extra={
                "extension_id": route.extension_id,
                "action": route.action_id,
                "runner": route.runner
            }
        )

        # Build command arguments
        # route.action_id = "get"
        # route.args = ["https://api.example.com"]
        # -> postman get https://api.example.com
        command_args = [route.action_id] + route.args

        # Add flags if present
        for flag_name, flag_value in route.flags.items():
            if isinstance(flag_value, bool):
                if flag_value:
                    command_args.append(f"--{flag_name}")
            else:
                command_args.extend([f"--{flag_name}", str(flag_value)])

        # Execute tool
        try:
            result = self.tool_executor.execute_tool(
                tool_name=tool_name,
                args=command_args,
                work_dir=context.work_dir,
                timeout=context.timeout
            )

            # Store last response for potential follow-up commands
            if result.success and result.stdout:
                self._save_last_response(
                    context.session_id,
                    result.stdout,
                    {
                        "extension_id": route.extension_id,
                        "command": route.command_name,
                        "action": route.action_id,
                        "tool": tool_name
                    }
                )

            # Return result
            return ExecutionResult(
                success=result.success,
                output=result.output,
                error=result.stderr if not result.success else None,
                metadata={
                    "exit_code": result.exit_code,
                    "duration_ms": result.duration_ms,
                    "command": result.command,
                    "tool": tool_name
                },
                raw_data=result
            )

        except ToolNotFoundError as e:
            logger.error(f"Tool not found: {tool_name}", exc_info=True)
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                metadata={"tool": tool_name}
            )

        except Exception as e:
            logger.error(
                f"Tool execution failed: {tool_name}",
                exc_info=True
            )
            return ExecutionResult(
                success=False,
                output="",
                error=f"Execution failed: {str(e)}",
                metadata={"tool": tool_name}
            )

    def _extract_tool_name(self, runner: str) -> str:
        """
        Extract tool name from runner string

        Examples:
            exec.postman_cli -> postman
            exec.curl -> curl
            exec.ffmpeg -> ffmpeg

        Args:
            runner: Runner string

        Returns:
            Tool name
        """
        if not runner.startswith(self.RUNNER_PREFIX):
            raise ValueError(f"Invalid runner format: {runner}")

        tool_spec = runner[len(self.RUNNER_PREFIX):]

        # Handle suffixes like _cli, _tool
        tool_name = tool_spec.replace("_cli", "").replace("_tool", "")

        return tool_name

    def _save_last_response(
        self,
        session_id: str,
        response: str,
        metadata: dict
    ) -> None:
        """
        Save the last response for a session

        Args:
            session_id: Session identifier
            response: Response content
            metadata: Response metadata
        """
        try:
            self.response_store.save(session_id, response, metadata)
            logger.debug(
                f"Saved last response for session {session_id} "
                f"({len(response)} bytes)"
            )
        except Exception as e:
            logger.warning(
                f"Failed to save last response: {e}",
                exc_info=True
            )


class AnalyzeResponseExecutor(BaseExecutor):
    """
    Analyze output using LLM (analyze.response runner type)

    Handles analysis of previous command outputs or provided data.
    """

    RUNNER_TYPE = "analyze.response"

    def __init__(self, llm_client=None):
        """
        Initialize executor

        Args:
            llm_client: LLM client for analysis (optional)
        """
        self.llm_client = llm_client
        self.response_store = get_response_store()

    def supports_runner(self, runner: str) -> bool:
        """Check if runner is 'analyze.response'"""
        return runner == self.RUNNER_TYPE

    def execute(
        self,
        route: CommandRoute,
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Analyze response using LLM

        Process:
        1. Get content to analyze (last_response or provided data)
        2. Build analysis prompt with usage documentation
        3. Call LLM for analysis
        4. Return formatted result

        Args:
            route: Command route
            context: Execution context

        Returns:
            ExecutionResult
        """
        logger.info(
            "Analyzing response with LLM",
            extra={
                "extension_id": route.extension_id,
                "action": route.action_id
            }
        )

        # Get content to analyze
        content = self._get_content_to_analyze(route, context)

        if not content:
            return ExecutionResult(
                success=False,
                output="",
                error=(
                    "No content to analyze. Either run a command first or "
                    "provide data to analyze."
                )
            )

        # Build analysis prompt
        prompt = self._build_analysis_prompt(
            content=content,
            usage_doc=context.usage_doc,
            action_description=route.description or "Analyze the response"
        )

        # Call LLM for analysis
        try:
            if self.llm_client is None:
                # If no LLM client, provide a simple analysis
                analysis = self._simple_analysis(content)
            else:
                analysis = self.llm_client.complete(prompt)

            return ExecutionResult(
                success=True,
                output=analysis,
                metadata={
                    "analyzed_content_length": len(content),
                    "analysis_type": "llm" if self.llm_client else "simple"
                }
            )

        except Exception as e:
            logger.error("Analysis failed", exc_info=True)
            return ExecutionResult(
                success=False,
                output="",
                error=f"Analysis failed: {str(e)}"
            )

    def _get_content_to_analyze(
        self,
        route: CommandRoute,
        context: ExecutionContext
    ) -> Optional[str]:
        """
        Get the content to analyze

        Args:
            route: Command route
            context: Execution context

        Returns:
            Content string or None
        """
        # Check if "last_response" is in args
        if "last_response" in route.args or "last" in route.args:
            content = self.response_store.get(context.session_id)
            if content:
                logger.debug(
                    f"Retrieved last response for analysis "
                    f"({len(content)} bytes)"
                )
                return content
            else:
                logger.warning(
                    f"No last response found for session {context.session_id}"
                )
                return None

        # Otherwise, use provided args as content
        if route.args:
            content = " ".join(route.args)
            logger.debug(f"Using provided content for analysis ({len(content)} bytes)")
            return content

        # Check if context has last_response
        if context.last_response:
            return context.last_response

        return None

    def _build_analysis_prompt(
        self,
        content: str,
        usage_doc: Optional[str],
        action_description: str
    ) -> str:
        """
        Build LLM prompt for analysis

        Args:
            content: Content to analyze
            usage_doc: Usage documentation from extension
            action_description: Description of the analysis task

        Returns:
            Formatted prompt
        """
        prompt = f"""You are helping the user understand an API response or data structure.

Task: {action_description}

"""

        if usage_doc:
            prompt += f"""Usage Guide:
{usage_doc}

"""

        prompt += f"""Content to analyze:
```
{content}
```

Please explain:
1. The structure and format of this response
2. Key fields and their meanings
3. Any notable patterns or insights
4. Potential issues or warnings (if any)

Be concise but thorough. Focus on what's most useful for the user.
"""

        return prompt

    def _simple_analysis(self, content: str) -> str:
        """
        Provide a simple analysis without LLM

        Args:
            content: Content to analyze

        Returns:
            Analysis string
        """
        lines = content.split("\n")
        char_count = len(content)
        line_count = len(lines)

        # Try to detect format
        format_type = "text"
        if content.strip().startswith("{") or content.strip().startswith("["):
            format_type = "JSON"
        elif content.strip().startswith("<"):
            format_type = "XML/HTML"

        analysis = f"""Response Analysis:

Format: {format_type}
Size: {char_count} characters, {line_count} lines

"""

        # Add first few lines as preview
        preview_lines = min(10, line_count)
        analysis += f"Preview (first {preview_lines} lines):\n"
        analysis += "\n".join(lines[:preview_lines])

        if line_count > preview_lines:
            analysis += f"\n\n... ({line_count - preview_lines} more lines)"

        return analysis


class AnalyzeSchemaExecutor(BaseExecutor):
    """
    Analyze JSON schema (analyze.schema runner type)

    For future implementation.
    """

    RUNNER_TYPE = "analyze.schema"

    def supports_runner(self, runner: str) -> bool:
        """Check if runner is 'analyze.schema'"""
        return runner == self.RUNNER_TYPE

    def execute(
        self,
        route: CommandRoute,
        context: ExecutionContext
    ) -> ExecutionResult:
        """Execute schema analysis"""
        return ExecutionResult(
            success=False,
            output="",
            error="Schema analysis is not yet implemented"
        )
