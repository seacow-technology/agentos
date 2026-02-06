"""
Tool Router - Routes tool invocations to appropriate executors

This module provides the ToolRouter class that dispatches tool invocations
to the correct executor based on the tool's source type (Extension or MCP).

Features:
- Unified invocation interface
- Source-based routing (extension vs MCP)
- Error handling and result normalization
- Integration with policy engine (PR-3)

Example:
    from agentos.core.capabilities import CapabilityRegistry, ToolRouter
    from agentos.core.capabilities.capability_models import ToolInvocation

    registry = CapabilityRegistry(ext_registry)
    router = ToolRouter(registry)

    invocation = ToolInvocation(
        invocation_id="inv_123",
        tool_id="ext:tools.postman:get",
        inputs={"url": "https://api.example.com"},
        actor="user@example.com",
        timestamp=datetime.now()
    )

    result = await router.invoke_tool("ext:tools.postman:get", invocation)
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Optional

from agentos.core.capabilities.registry import CapabilityRegistry
from agentos.core.capabilities.capability_models import (
    ToolInvocation,
    ToolResult,
    ToolSource,
    PolicyDecision,
)
from agentos.core.capabilities.audit import (
    emit_tool_invocation_start,
    emit_tool_invocation_end,
    emit_provenance_snapshot,
)
from agentos.core.capabilities.policy import ToolPolicyEngine
from agentos.core.capabilities.governance_models.provenance import (
    ProvenanceStamp,
    get_current_env,
)

logger = logging.getLogger(__name__)


class ToolRouterError(Exception):
    """Base exception for tool router errors"""
    pass


class ToolNotFoundError(ToolRouterError):
    """Raised when a tool is not found"""
    pass


class PolicyViolationError(ToolRouterError):
    """Raised when a tool invocation violates policy"""
    pass


class ToolRouter:
    """
    Tool invocation router

    Routes tool invocations to the appropriate executor based on source type.
    Handles policy checks, auditing, and result normalization.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        policy_engine: Optional[ToolPolicyEngine] = None,
        quota_manager: Optional['QuotaManager'] = None
    ):
        """
        Initialize tool router

        Args:
            registry: CapabilityRegistry instance
            policy_engine: ToolPolicyEngine instance (optional, for PR-3)
            quota_manager: QuotaManager instance (optional, for PR-A)
        """
        self.registry = registry

        # Import QuotaManager here to avoid circular import
        if quota_manager is None:
            from agentos.core.capabilities.quota_manager import QuotaManager
            quota_manager = QuotaManager()

        self.quota_manager = quota_manager
        self.policy_engine = policy_engine or ToolPolicyEngine(quota_manager=quota_manager)

    async def invoke_tool(
        self,
        tool_id: str,
        invocation: ToolInvocation,
        admin_token: Optional[str] = None
    ) -> ToolResult:
        """
        Invoke a tool by ID with complete security gate checks

        Security flow:
        1. Get tool descriptor
        2. Run 6-layer policy gate checks
        3. Emit before audit
        4. Execute tool
        5. Emit after audit

        Args:
            tool_id: Tool identifier
            invocation: ToolInvocation request
            admin_token: Admin token for high-risk operations (optional)

        Returns:
            ToolResult

        Raises:
            ToolNotFoundError: If tool not found
            PolicyViolationError: If policy check fails
            ToolRouterError: For other errors
        """
        start_time = time.time()
        started_at = datetime.now()
        tool = None  # Initialize for error handling

        try:
            # Step 1: Get tool descriptor
            tool = self.registry.get_tool(tool_id)
            if not tool:
                raise ToolNotFoundError(f"Tool not found: {tool_id}")

            # Step 1.5: Generate Provenance Stamp (PR-C)
            provenance = ProvenanceStamp(
                capability_id=tool.tool_id,
                tool_id=tool.name,
                capability_type=tool.source_type.value,
                source_id=tool.source_id,
                source_version=tool.source_version,
                execution_env=get_current_env(),
                trust_tier=tool.trust_tier.value,
                timestamp=datetime.now(),
                invocation_id=invocation.invocation_id,
                task_id=invocation.task_id,
                project_id=invocation.project_id,
                spec_hash=invocation.spec_hash
            )

            # Step 2: Policy check (6-layer gates)
            allowed, reason, decision = self.policy_engine.check_allowed(
                tool, invocation, admin_token
            )

            # Step 3: Handle policy violation
            if not allowed:
                from agentos.core.capabilities.audit import emit_policy_violation
                emit_policy_violation(invocation, tool, decision, reason)

                # Return error result with provenance
                duration_ms = int((time.time() - start_time) * 1000)
                return ToolResult(
                    invocation_id=invocation.invocation_id,
                    success=False,
                    payload=None,
                    declared_side_effects=[],
                    error=f"Policy violation: {reason}",
                    duration_ms=duration_ms,
                    started_at=started_at,
                    completed_at=datetime.now(),
                    provenance=provenance
                )

            # Step 4: Emit before audit
            from agentos.core.capabilities.audit import (
                emit_tool_invocation_start,
                emit_tool_invocation_end
            )
            emit_tool_invocation_start(invocation, tool)

            # Step 5: Update quota - increment concurrent count
            quota_id = f"tool:{tool_id}"
            self.quota_manager.update_quota(quota_id, 0, 0, increment_concurrent=1)

            # Step 6: Route to appropriate executor
            try:
                if tool.source_type == ToolSource.EXTENSION:
                    result = await self._invoke_extension_tool(tool_id, invocation)
                elif tool.source_type == ToolSource.MCP:
                    result = await self._invoke_mcp_tool(tool_id, invocation)
                else:
                    raise ToolRouterError(f"Unknown source type: {tool.source_type}")
            finally:
                # Step 7: Update quota - decrement concurrent count and add runtime
                duration_ms = int((time.time() - start_time) * 1000)
                self.quota_manager.update_quota(
                    quota_id,
                    runtime_ms=duration_ms,
                    increment_concurrent=-1
                )

            # Step 8: Add timing information and provenance
            result.duration_ms = duration_ms
            result.started_at = started_at
            result.completed_at = datetime.now()
            result.provenance = provenance

            # Step 9: Emit after audit (including provenance snapshot)
            emit_tool_invocation_end(result, tool, invocation.task_id)
            emit_provenance_snapshot(provenance)

            logger.info(f"Tool invocation completed: {tool_id} in {duration_ms}ms")
            return result

        except ToolNotFoundError as e:
            # Tool not found error
            duration_ms = int((time.time() - start_time) * 1000)
            error_result = ToolResult(
                invocation_id=invocation.invocation_id,
                success=False,
                payload=None,
                declared_side_effects=[],
                error=str(e),
                duration_ms=duration_ms,
                started_at=started_at,
                completed_at=datetime.now()
            )
            # Don't emit audit for tool not found
            raise

        except ToolRouterError as e:
            # Known router errors
            duration_ms = int((time.time() - start_time) * 1000)
            error_result = ToolResult(
                invocation_id=invocation.invocation_id,
                success=False,
                payload=None,
                declared_side_effects=[],
                error=str(e),
                duration_ms=duration_ms,
                started_at=started_at,
                completed_at=datetime.now()
            )
            # Emit audit if we have tool info
            if tool:
                from agentos.core.capabilities.audit import emit_tool_invocation_end
                emit_tool_invocation_end(error_result, tool, invocation.task_id)
            raise

        except Exception as e:
            # Unexpected errors
            logger.error(f"Unexpected error invoking tool {tool_id}: {e}", exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            error_result = ToolResult(
                invocation_id=invocation.invocation_id,
                success=False,
                payload=None,
                declared_side_effects=[],
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
                started_at=started_at,
                completed_at=datetime.now()
            )
            # Emit audit if we have tool info
            if tool:
                from agentos.core.capabilities.audit import emit_tool_invocation_end
                emit_tool_invocation_end(error_result, tool, invocation.task_id)
            raise ToolRouterError(f"Failed to invoke tool: {e}") from e

    async def _invoke_extension_tool(
        self,
        tool_id: str,
        invocation: ToolInvocation
    ) -> ToolResult:
        """
        Invoke an extension tool

        This is a placeholder implementation for PR-1.
        Full implementation will integrate with the existing extension runner.

        Args:
            tool_id: Tool identifier
            invocation: ToolInvocation request

        Returns:
            ToolResult
        """
        logger.info(f"Invoking extension tool: {tool_id}")

        # TODO PR-1: Integrate with existing extension runner
        # For now, return a placeholder result
        # The full implementation will:
        # 1. Parse tool_id to get extension_id and command
        # 2. Load extension capability
        # 3. Execute via CapabilityRunner
        # 4. Convert ExecutionResult to ToolResult

        try:
            # Parse tool_id: "ext:<extension_id>:<command>"
            parts = tool_id.split(":")
            if len(parts) < 3:
                raise ToolRouterError(f"Invalid extension tool_id format: {tool_id}")

            extension_id = parts[1]
            command_name = parts[2]

            # TODO: Integrate with CapabilityRunner
            # For now, create a mock result
            result = ToolResult(
                invocation_id=invocation.invocation_id,
                success=True,
                payload={
                    "message": f"Extension tool {command_name} invoked",
                    "extension_id": extension_id,
                    "inputs": invocation.inputs
                },
                declared_side_effects=[],
                duration_ms=0,  # Will be set by caller
                metadata={
                    "source": "extension",
                    "extension_id": extension_id
                }
            )

            logger.info(f"Extension tool invocation successful: {tool_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to invoke extension tool {tool_id}: {e}", exc_info=True)
            return ToolResult(
                invocation_id=invocation.invocation_id,
                success=False,
                payload=None,
                error=str(e),
                duration_ms=0  # Will be set by caller
            )

    async def _invoke_mcp_tool(
        self,
        tool_id: str,
        invocation: ToolInvocation
    ) -> ToolResult:
        """
        Invoke an MCP tool

        Args:
            tool_id: Tool identifier (format: mcp:<server_id>:<tool_name>)
            invocation: ToolInvocation request

        Returns:
            ToolResult
        """
        start_time = datetime.now()

        try:
            logger.info(f"Invoking MCP tool: {tool_id}")

            # Parse tool_id: mcp:<server_id>:<tool_name>
            parts = tool_id.split(":", 2)
            if len(parts) != 3 or parts[0] != "mcp":
                raise ValueError(f"Invalid MCP tool_id format: {tool_id}")

            server_id = parts[1]
            tool_name = parts[2]

            logger.debug(f"MCP server: {server_id}, tool: {tool_name}")

            # Get MCP client from registry
            client = self.registry.mcp_clients.get(server_id)
            if not client:
                raise RuntimeError(f"MCP server not connected: {server_id}")

            if not client.is_alive():
                raise RuntimeError(f"MCP server not alive: {server_id}")

            # Import adapter
            from agentos.core.mcp import MCPAdapter

            # Call tool
            mcp_result = await client.call_tool(tool_name, invocation.inputs)

            # Calculate duration
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # Convert result
            adapter = MCPAdapter()
            result = adapter.mcp_result_to_tool_result(
                invocation_id=invocation.invocation_id,
                mcp_result=mcp_result,
                duration_ms=duration_ms
            )

            logger.info(
                f"MCP tool invocation completed: {tool_id} "
                f"(success={result.success}, duration={duration_ms}ms)"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to invoke MCP tool {tool_id}: {e}", exc_info=True)
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return ToolResult(
                invocation_id=invocation.invocation_id,
                success=False,
                payload=None,
                declared_side_effects=[],
                error=str(e),
                duration_ms=duration_ms
            )

    def sync_invoke_tool(
        self,
        tool_id: str,
        invocation: ToolInvocation
    ) -> ToolResult:
        """
        Synchronous wrapper for invoke_tool

        This is provided for compatibility with synchronous code.
        Uses asyncio.run() internally.

        Args:
            tool_id: Tool identifier
            invocation: ToolInvocation request

        Returns:
            ToolResult
        """
        import asyncio
        return asyncio.run(self.invoke_tool(tool_id, invocation))
