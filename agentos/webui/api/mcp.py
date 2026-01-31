"""
MCP Management API - Observability and control for MCP servers

Provides endpoints for managing MCP servers, browsing tools, and testing
tool invocations through the unified capability system.

Part of PR-4: WebUI MCP Management Page & API

Features:
- List MCP servers with status and health
- Browse MCP tools with filtering
- Test tool invocations with full security gates
- Refresh MCP server connections
- Health monitoring

All tool calls go through the complete security gate system (ToolRouter).
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from agentos.core.capabilities.registry import CapabilityRegistry
from agentos.core.capabilities.router import ToolRouter
from agentos.webui.api.time_format import iso_z
from agentos.core.capabilities.capability_models import (
    ToolInvocation,
    ExecutionMode,
    RiskLevel,
)
from agentos.webui.api.contracts import ReasonCode, success, error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

# Global instances (will be initialized via dependency injection)
_capability_registry: Optional[CapabilityRegistry] = None
_tool_router: Optional[ToolRouter] = None


# ============================================
# Dependency Injection
# ============================================

def get_capability_registry() -> CapabilityRegistry:
    """Get or create CapabilityRegistry instance"""
    global _capability_registry
    if _capability_registry is None:
        from agentos.core.extensions.registry import ExtensionRegistry
        ext_registry = ExtensionRegistry()
        _capability_registry = CapabilityRegistry(ext_registry)
        logger.info("CapabilityRegistry initialized for MCP API")
    return _capability_registry


def get_tool_router() -> ToolRouter:
    """Get or create ToolRouter instance"""
    global _tool_router
    if _tool_router is None:
        registry = get_capability_registry()
        _tool_router = ToolRouter(registry)
        logger.info("ToolRouter initialized for MCP API")
    return _tool_router


# ============================================
# Request/Response Models
# ============================================

class MCPServerStatusResponse(BaseModel):
    """MCP server status information"""
    id: str = Field(description="Server identifier")
    enabled: bool = Field(description="Whether server is enabled")
    status: str = Field(description="Connection status: connected/disconnected/error")
    health: str = Field(description="Health status: healthy/degraded/unhealthy")
    last_seen: Optional[str] = Field(None, description="Last successful communication timestamp")
    tool_count: int = Field(description="Number of tools available from this server")
    error_message: Optional[str] = Field(None, description="Error message if status is error")


class MCPToolResponse(BaseModel):
    """MCP tool information"""
    tool_id: str = Field(description="Tool identifier (mcp:server:tool)")
    server_id: str = Field(description="MCP server identifier")
    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    risk_level: str = Field(description="Risk level: LOW/MED/HIGH/CRITICAL")
    side_effects: List[str] = Field(description="Declared side effects")
    requires_admin_token: bool = Field(description="Whether admin token is required")
    input_schema: Dict[str, Any] = Field(description="JSON Schema for tool inputs")


class MCPToolCallRequest(BaseModel):
    """Tool invocation request"""
    tool_id: str = Field(description="Tool identifier (mcp:server:tool)")
    inputs: Dict[str, Any] = Field(description="Tool input parameters")
    project_id: str = Field(description="Project ID (required for auditing)")
    task_id: Optional[str] = Field(None, description="Task ID (optional)")
    admin_token: Optional[str] = Field(None, description="Admin token for high-risk operations")


class MCPToolCallResponse(BaseModel):
    """Tool invocation result"""
    success: bool = Field(description="Whether invocation succeeded")
    invocation_id: str = Field(description="Unique invocation identifier")
    payload: Any = Field(description="Tool output payload")
    error: Optional[str] = Field(None, description="Error message if failed")
    duration_ms: int = Field(description="Execution duration in milliseconds")
    declared_side_effects: List[str] = Field(description="Side effects that occurred")


class RefreshResponse(BaseModel):
    """Server refresh result"""
    message: str = Field(description="Result message")
    refreshed_count: int = Field(description="Number of servers refreshed")


class HealthResponse(BaseModel):
    """MCP subsystem health"""
    status: str = Field(description="Overall status: healthy/degraded/unhealthy")
    connected_servers: int = Field(description="Number of connected MCP servers")
    available_tools: int = Field(description="Total number of available MCP tools")


# ============================================
# API Endpoints
# ============================================

@router.get("/servers", response_model=List[MCPServerStatusResponse])
async def list_mcp_servers(
    registry: CapabilityRegistry = Depends(get_capability_registry)
):
    """
    List all MCP servers with their status and health

    Returns server connection status, health metrics, and tool counts.
    This endpoint provides observability into the MCP subsystem.

    Returns:
        List of server status objects
    """
    try:
        logger.info("Listing MCP servers")

        # Get MCP config manager
        if not registry.mcp_config_manager:
            logger.warning("MCP config manager not initialized")
            return []

        # Get all configured servers
        all_servers = registry.mcp_config_manager.load_config()
        logger.debug(f"Found {len(all_servers)} configured MCP servers")

        server_statuses = []

        for server_config in all_servers:
            # Get client if connected
            client = registry.mcp_clients.get(server_config.id)

            # Determine status
            if not server_config.enabled:
                status = "disabled"
                health = "n/a"
                last_seen = None
                error_message = None
            elif client and client.is_alive():
                status = "connected"
                health = "healthy"
                last_seen = iso_z(datetime.now())
                error_message = None
            elif client and not client.is_alive():
                status = "disconnected"
                health = "unhealthy"
                last_seen = None
                error_message = "Connection lost"
            else:
                status = "disconnected"
                health = "unhealthy"
                last_seen = None
                error_message = "Not connected"

            # Count tools from this server
            try:
                from agentos.core.capabilities.capability_models import ToolSource
                all_tools = registry.list_tools(
                    source_types=[ToolSource.MCP],
                    enabled_only=False
                )
                tool_count = len([t for t in all_tools if t.source_id == server_config.id])
            except Exception as e:
                logger.error(f"Failed to count tools for {server_config.id}: {e}")
                tool_count = 0

            server_statuses.append(MCPServerStatusResponse(
                id=server_config.id,
                enabled=server_config.enabled,
                status=status,
                health=health,
                last_seen=last_seen,
                tool_count=tool_count,
                error_message=error_message
            ))

        logger.info(f"Returning status for {len(server_statuses)} MCP servers")
        return server_statuses

    except Exception as e:
        logger.error(f"Failed to list MCP servers: {e}", exc_info=True)
        raise error(
            "Failed to list MCP servers",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.post("/servers/refresh", response_model=RefreshResponse)
async def refresh_mcp_servers(
    registry: CapabilityRegistry = Depends(get_capability_registry)
):
    """
    Refresh MCP server connections and tool listings

    Triggers a refresh of the capability cache, which:
    - Reconnects to all enabled MCP servers
    - Re-fetches tool listings
    - Updates the tool cache

    Returns:
        Refresh result with count of refreshed servers
    """
    try:
        logger.info("Refreshing MCP servers")

        # Force cache refresh (this will reconnect MCP servers)
        registry.refresh()

        # Count connected servers
        connected_count = len([
            client for client in registry.mcp_clients.values()
            if client.is_alive()
        ])

        logger.info(f"Refresh complete: {connected_count} servers connected")

        return RefreshResponse(
            message=f"Successfully refreshed {connected_count} MCP servers",
            refreshed_count=connected_count
        )

    except Exception as e:
        logger.error(f"Failed to refresh MCP servers: {e}", exc_info=True)
        raise error(
            "Failed to refresh MCP servers",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.get("/tools", response_model=List[MCPToolResponse])
async def list_mcp_tools(
    server_id: Optional[str] = None,
    risk_level_max: Optional[str] = None,
    registry: CapabilityRegistry = Depends(get_capability_registry)
):
    """
    List all MCP tools with optional filtering

    Query Parameters:
    - server_id: Filter by specific MCP server
    - risk_level_max: Maximum risk level (LOW/MED/HIGH/CRITICAL)

    Returns:
        List of MCP tools
    """
    try:
        logger.info(f"Listing MCP tools (server_id={server_id}, risk_max={risk_level_max})")

        # Parse risk level filter
        risk_filter = None
        if risk_level_max:
            try:
                risk_filter = RiskLevel(risk_level_max.upper())
            except ValueError:
                raise error(
                    f"Invalid risk level: {risk_level_max}",
                    reason_code=ReasonCode.INVALID_INPUT,
                    hint="Valid levels: LOW, MED, HIGH, CRITICAL",
                    http_status=400
                )

        # Get MCP tools from registry
        from agentos.core.capabilities.capability_models import ToolSource
        tools = registry.list_tools(
            source_types=[ToolSource.MCP],
            risk_level_max=risk_filter,
            enabled_only=False  # Include disabled for observability
        )

        # Filter by server_id if specified
        if server_id:
            tools = [t for t in tools if t.source_id == server_id]

        # Convert to response format
        tool_responses = []
        for tool in tools:
            tool_responses.append(MCPToolResponse(
                tool_id=tool.tool_id,
                server_id=tool.source_id,
                name=tool.name,
                description=tool.description,
                risk_level=tool.risk_level.value,
                side_effects=tool.side_effect_tags,
                requires_admin_token=tool.requires_admin_token,
                input_schema=tool.input_schema
            ))

        logger.info(f"Returning {len(tool_responses)} MCP tools")
        return tool_responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list MCP tools: {e}", exc_info=True)
        raise error(
            "Failed to list MCP tools",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.post("/call", response_model=MCPToolCallResponse)
async def call_mcp_tool(
    request: MCPToolCallRequest,
    router_instance: ToolRouter = Depends(get_tool_router)
):
    """
    Test call an MCP tool with full security gates

    This endpoint allows testing MCP tool invocations through the WebUI.
    All calls go through the complete 6-layer security gate system:

    1. Tool Enablement Gate
    2. Risk Level Gate
    3. Side Effect Gate
    4. Project Binding Gate
    5. Spec Freezing Gate (if task_id provided)
    6. Admin Token Gate (for CRITICAL risk tools)

    Request Body:
    - tool_id: Tool identifier (mcp:server:tool)
    - inputs: Tool input parameters
    - project_id: Project ID (required for auditing)
    - task_id: Task ID (optional, for task-bound calls)
    - admin_token: Admin token (required for CRITICAL risk tools)

    Returns:
        Tool invocation result with success status and payload
    """
    try:
        logger.info(f"MCP tool call request: {request.tool_id}")

        # Validate tool_id format
        if not request.tool_id.startswith("mcp:"):
            raise error(
                "Invalid tool_id format",
                reason_code=ReasonCode.INVALID_INPUT,
                hint="Tool ID must start with 'mcp:' for MCP tools",
                http_status=400
            )

        # Create invocation
        invocation = ToolInvocation(
            invocation_id=f"inv_{uuid.uuid4().hex[:12]}",
            tool_id=request.tool_id,
            inputs=request.inputs,
            actor="webui_test_user",  # Test actor for WebUI calls
            project_id=request.project_id,
            task_id=request.task_id,
            mode=ExecutionMode.EXECUTION,
            timestamp=datetime.now()
        )

        # Route through tool router (includes all security gates)
        logger.debug(f"Routing invocation through ToolRouter: {invocation.invocation_id}")
        result = await router_instance.invoke_tool(
            tool_id=request.tool_id,
            invocation=invocation,
            admin_token=request.admin_token
        )

        # Convert to response format
        response = MCPToolCallResponse(
            success=result.success,
            invocation_id=result.invocation_id,
            payload=result.payload,
            error=result.error,
            duration_ms=result.duration_ms,
            declared_side_effects=result.declared_side_effects
        )

        if result.success:
            logger.info(f"MCP tool call succeeded: {request.tool_id}")
        else:
            logger.warning(f"MCP tool call failed: {request.tool_id} - {result.error}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to call MCP tool: {e}", exc_info=True)
        raise error(
            f"Failed to call MCP tool: {str(e)}",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.get("/health", response_model=HealthResponse)
async def mcp_health_check(
    registry: CapabilityRegistry = Depends(get_capability_registry)
):
    """
    MCP subsystem health check

    Provides overall health status of the MCP integration:
    - Number of connected servers
    - Number of available tools
    - Overall health status

    Returns:
        Health status object
    """
    try:
        logger.debug("MCP health check requested")

        # Count connected servers
        connected_count = 0
        if registry.mcp_config_manager:
            for server_config in registry.mcp_config_manager.get_enabled_servers():
                client = registry.mcp_clients.get(server_config.id)
                if client and client.is_alive():
                    connected_count += 1

        # Count available tools
        from agentos.core.capabilities.capability_models import ToolSource
        mcp_tools = registry.list_tools(
            source_types=[ToolSource.MCP],
            enabled_only=True
        )
        tool_count = len(mcp_tools)

        # Determine overall health
        if connected_count == 0:
            status = "unhealthy"
        elif tool_count == 0:
            status = "degraded"
        else:
            status = "healthy"

        logger.debug(
            f"MCP health: {status} "
            f"({connected_count} servers, {tool_count} tools)"
        )

        return HealthResponse(
            status=status,
            connected_servers=connected_count,
            available_tools=tool_count
        )

    except Exception as e:
        logger.error(f"MCP health check failed: {e}", exc_info=True)
        # Return unhealthy status instead of raising
        return HealthResponse(
            status="unhealthy",
            connected_servers=0,
            available_tools=0
        )
