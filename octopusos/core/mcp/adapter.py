"""
MCP Adapter - Converts MCP tools to ToolDescriptor format

This module adapts MCP tool schemas and results to the unified Capability
abstraction layer. It handles:
- Converting MCP tool schemas to ToolDescriptor
- Inferring risk levels and side effects
- Converting MCP results to ToolResult

Strategy:
- Risk inference based on tool name, description, and schema
- Side effect inference based on keywords and patterns
- Configurable filtering based on server configuration
"""

import logging
from typing import Any, Dict, List, Optional

from agentos.core.capabilities.capability_models import (
    ToolDescriptor,
    ToolResult,
    RiskLevel,
    ToolSource,
    SideEffect,
    TrustTier,
)
from agentos.core.mcp.config import MCPServerConfig

logger = logging.getLogger(__name__)


class MCPAdapter:
    """
    MCP tool adapter

    Converts MCP tool schemas and results to the unified Capability format.
    Provides intelligent inference of risk levels and side effects.
    """

    def __init__(self):
        """Initialize adapter"""
        pass

    def mcp_tool_to_descriptor(
        self,
        server_id: str,
        mcp_tool: Dict[str, Any],
        server_config: MCPServerConfig
    ) -> ToolDescriptor:
        """
        Convert MCP tool schema to ToolDescriptor

        Args:
            server_id: MCP server ID
            mcp_tool: MCP tool schema from list_tools()
            server_config: Server configuration

        Returns:
            ToolDescriptor instance

        Example MCP tool schema:
            {
                "name": "read_file",
                "description": "Read contents of a file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"}
                    },
                    "required": ["path"]
                }
            }
        """
        tool_name = mcp_tool.get("name", "unknown")
        description = mcp_tool.get("description", "")
        input_schema = mcp_tool.get("inputSchema", {})

        # Generate tool_id: mcp:<server_id>:<tool_name>
        tool_id = f"mcp:{server_id}:{tool_name}"

        # Infer risk level
        risk_level = self.infer_risk_level(tool_name, description, input_schema)

        # Infer side effects
        side_effects = self.infer_side_effects(tool_name, description, input_schema)

        # Check if tool requires admin approval (CRITICAL risk)
        requires_admin = risk_level == RiskLevel.CRITICAL

        # Automatically infer trust_tier based on server configuration
        trust_tier = self._infer_trust_tier(server_config)

        # Create descriptor
        descriptor = ToolDescriptor(
            tool_id=tool_id,
            name=tool_name,
            description=description,
            input_schema=input_schema,
            output_schema=None,  # MCP doesn't provide output schemas
            risk_level=risk_level,
            side_effect_tags=side_effects,
            requires_admin_token=requires_admin,
            source_type=ToolSource.MCP,
            source_id=server_id,
            timeout_ms=server_config.timeout_ms,
            permissions_required=[],  # MCP doesn't have explicit permissions
            enabled=server_config.enabled,
            trust_tier=trust_tier
        )

        logger.debug(
            f"Converted MCP tool to descriptor: {tool_id} "
            f"(risk={risk_level}, side_effects={side_effects})"
        )

        return descriptor

    def infer_risk_level(
        self,
        tool_name: str,
        tool_description: str,
        input_schema: Dict
    ) -> RiskLevel:
        """
        Infer risk level from tool metadata

        Strategy:
        - CRITICAL: payment, charge, delete (cloud/db), key operations
        - HIGH: write, delete (files), modify, exec, create resources
        - MED: http requests, moderate operations
        - LOW: read-only operations, get, list, search

        Args:
            tool_name: Tool name
            tool_description: Tool description
            input_schema: Tool input schema

        Returns:
            RiskLevel
        """
        name_lower = tool_name.lower()
        desc_lower = tool_description.lower()

        # CRITICAL: Financial, dangerous deletions, key management
        critical_keywords = [
            "payment", "charge", "bill", "purchase", "transaction",
            "key_write", "secret", "credential",
            "delete_database", "drop_table", "destroy"
        ]
        if any(keyword in name_lower or keyword in desc_lower for keyword in critical_keywords):
            logger.debug(f"Tool {tool_name} classified as CRITICAL risk")
            return RiskLevel.CRITICAL

        # HIGH: Write/modify operations, execution, resource creation
        high_keywords = [
            "write", "delete", "remove", "modify", "update",
            "exec", "execute", "run", "command",
            "create", "provision", "deploy"
        ]
        if any(keyword in name_lower or keyword in desc_lower for keyword in high_keywords):
            # Exception: write_log, update_cache etc. might be lower risk
            safe_high_keywords = ["log", "cache", "temp", "session"]
            if not any(safe in name_lower or safe in desc_lower for safe in safe_high_keywords):
                logger.debug(f"Tool {tool_name} classified as HIGH risk")
                return RiskLevel.HIGH

        # LOW: Read-only operations
        low_keywords = [
            "read", "get", "list", "search", "find", "query",
            "show", "display", "view", "fetch"
        ]
        if any(keyword in name_lower or keyword in desc_lower for keyword in low_keywords):
            logger.debug(f"Tool {tool_name} classified as LOW risk")
            return RiskLevel.LOW

        # MED: Default for uncertain operations
        logger.debug(f"Tool {tool_name} classified as MED risk (default)")
        return RiskLevel.MED

    def infer_side_effects(
        self,
        tool_name: str,
        tool_description: str,
        input_schema: Dict
    ) -> List[str]:
        """
        Infer side effect tags from tool metadata

        Strategy:
        - Analyze tool name and description for keywords
        - Map keywords to side effect categories
        - Return all applicable side effects

        Args:
            tool_name: Tool name
            tool_description: Tool description
            input_schema: Tool input schema

        Returns:
            List of side effect tags
        """
        effects: List[str] = []
        name_lower = tool_name.lower()
        desc_lower = tool_description.lower()

        # Filesystem effects
        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["write", "create", "save", "put"]):
            if any(keyword in name_lower or keyword in desc_lower
                   for keyword in ["file", "directory", "folder", "disk"]):
                effects.append(SideEffect.FS_WRITE.value)

        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["delete", "remove", "rm", "unlink"]):
            if any(keyword in name_lower or keyword in desc_lower
                   for keyword in ["file", "directory", "folder"]):
                effects.append(SideEffect.FS_DELETE.value)

        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["read", "get", "load"]):
            if any(keyword in name_lower or keyword in desc_lower
                   for keyword in ["file", "directory", "folder", "disk"]):
                effects.append(SideEffect.FS_READ.value)

        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["chmod", "chown", "permission"]):
            effects.append(SideEffect.FS_CHMOD.value)

        # Network effects
        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["http", "https", "api", "request", "fetch", "curl", "get", "post"]):
            # Only add if not already classified as file operation
            if SideEffect.FS_READ.value not in effects:
                effects.append(SideEffect.NETWORK_HTTP.value)

        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["socket", "tcp", "udp", "connect"]):
            effects.append(SideEffect.NETWORK_SOCKET.value)

        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["dns", "resolve", "lookup"]):
            effects.append(SideEffect.NETWORK_DNS.value)

        # Cloud effects
        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["key_read", "secret_read", "credential_read"]):
            effects.append(SideEffect.CLOUD_KEY_READ.value)

        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["key_write", "secret_write", "credential_write"]):
            effects.append(SideEffect.CLOUD_KEY_WRITE.value)

        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["create", "provision", "deploy"]):
            if any(keyword in name_lower or keyword in desc_lower
                   for keyword in ["resource", "cloud", "instance", "server"]):
                effects.append(SideEffect.CLOUD_RESOURCE_CREATE.value)

        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["delete", "destroy", "terminate"]):
            if any(keyword in name_lower or keyword in desc_lower
                   for keyword in ["resource", "cloud", "instance", "server"]):
                effects.append(SideEffect.CLOUD_RESOURCE_DELETE.value)

        # Financial effects
        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["payment", "charge", "bill", "purchase", "transaction"]):
            effects.append(SideEffect.PAYMENTS.value)

        # System effects
        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["exec", "execute", "run", "command", "shell", "bash"]):
            effects.append(SideEffect.SYSTEM_EXEC.value)

        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["env", "environment", "setenv"]):
            effects.append(SideEffect.SYSTEM_ENV.value)

        # Database effects
        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["query", "select"]):
            if any(keyword in name_lower or keyword in desc_lower
                   for keyword in ["database", "db", "sql", "table"]):
                effects.append(SideEffect.DATABASE_READ.value)

        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["insert", "update", "upsert"]):
            if any(keyword in name_lower or keyword in desc_lower
                   for keyword in ["database", "db", "sql", "table"]):
                effects.append(SideEffect.DATABASE_WRITE.value)

        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["delete", "drop", "truncate"]):
            if any(keyword in name_lower or keyword in desc_lower
                   for keyword in ["database", "db", "sql", "table"]):
                effects.append(SideEffect.DATABASE_DELETE.value)

        logger.debug(f"Tool {tool_name} inferred side effects: {effects}")
        return effects

    def _infer_trust_tier(self, server_config: MCPServerConfig) -> TrustTier:
        """
        根据 MCP 服务器配置推断信任层级

        规则:
        - stdio (local) → T1 (本地 MCP)
        - stdio + http/https command → T3 (Cloud MCP)
        - tcp/ssh (remote) → T2 (远程 MCP)
        - https/http (cloud) → T3 (Cloud MCP)

        Args:
            server_config: MCP server configuration

        Returns:
            TrustTier: 推断的信任层级
        """
        transport = server_config.transport.lower()

        if transport == "stdio":
            # 本地 stdio，检查命令是否为本地
            command = server_config.command[0] if server_config.command else ""
            if command.startswith("http"):
                logger.debug(
                    f"MCP server {server_config.id} uses stdio with HTTP command, "
                    f"classified as T3 (Cloud MCP)"
                )
                return TrustTier.T3  # Cloud
            logger.debug(
                f"MCP server {server_config.id} uses stdio with local command, "
                f"classified as T1 (Local MCP)"
            )
            return TrustTier.T1  # Local

        elif transport in ("tcp", "ssh"):
            logger.debug(
                f"MCP server {server_config.id} uses {transport} transport, "
                f"classified as T2 (Remote MCP)"
            )
            return TrustTier.T2  # Remote

        elif transport in ("https", "http"):
            logger.debug(
                f"MCP server {server_config.id} uses {transport} transport, "
                f"classified as T3 (Cloud MCP)"
            )
            return TrustTier.T3  # Cloud

        else:
            # 未知传输协议，默认为 T2（中等信任）
            logger.warning(
                f"Unknown transport {transport} for server {server_config.id}, "
                f"defaulting to T2 (Remote MCP)"
            )
            return TrustTier.T2

    def mcp_result_to_tool_result(
        self,
        invocation_id: str,
        mcp_result: Dict[str, Any],
        duration_ms: int
    ) -> ToolResult:
        """
        Convert MCP execution result to ToolResult

        Args:
            invocation_id: Invocation identifier
            mcp_result: MCP tool execution result
            duration_ms: Execution duration

        Returns:
            ToolResult instance

        Example MCP result:
            {
                "content": [
                    {
                        "type": "text",
                        "text": "File contents here"
                    }
                ],
                "isError": false
            }
        """
        # Check for error
        is_error = mcp_result.get("isError", False)

        # Extract content
        content = mcp_result.get("content", [])

        # Build payload from content
        payload = self._extract_payload_from_content(content)

        # Extract error message if present
        error = None
        if is_error:
            error = self._extract_error_from_content(content)

        # Create result
        result = ToolResult(
            invocation_id=invocation_id,
            success=not is_error,
            payload=payload,
            declared_side_effects=[],  # MCP doesn't report side effects
            error=error,
            duration_ms=duration_ms,
            metadata={
                "source": "mcp",
                "raw_content": content
            }
        )

        logger.debug(
            f"Converted MCP result to ToolResult: "
            f"success={result.success}, duration={duration_ms}ms"
        )

        return result

    def _extract_payload_from_content(self, content: List[Dict[str, Any]]) -> Any:
        """
        Extract payload from MCP content array

        MCP returns content as an array of typed objects.
        This method extracts the most relevant representation.

        Args:
            content: MCP content array

        Returns:
            Extracted payload
        """
        if not content:
            return None

        # If single text item, return the text
        if len(content) == 1 and content[0].get("type") == "text":
            return content[0].get("text")

        # If multiple items, return structured data
        payload = []
        for item in content:
            item_type = item.get("type", "unknown")

            if item_type == "text":
                payload.append({"type": "text", "text": item.get("text")})
            elif item_type == "image":
                payload.append({
                    "type": "image",
                    "data": item.get("data"),
                    "mimeType": item.get("mimeType")
                })
            elif item_type == "resource":
                payload.append({
                    "type": "resource",
                    "uri": item.get("uri"),
                    "text": item.get("text")
                })
            else:
                payload.append({"type": item_type, "data": item})

        return payload if len(payload) > 1 else payload[0] if payload else None

    def _extract_error_from_content(self, content: List[Dict[str, Any]]) -> str:
        """
        Extract error message from MCP content

        Args:
            content: MCP content array

        Returns:
            Error message string
        """
        messages = []
        for item in content:
            if item.get("type") == "text":
                messages.append(item.get("text", ""))

        return " ".join(messages) if messages else "Unknown MCP error"
