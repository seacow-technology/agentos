"""
Capability Registry - Unified tool discovery from Extension and MCP sources

This module provides the CapabilityRegistry class that merges tools from
Extension capabilities and MCP servers into a unified interface for discovery
and querying.

Features:
- Unified tool listing from multiple sources
- Risk-based filtering
- Side-effect filtering
- Caching with TTL
- Graceful degradation when sources fail

Example:
    from agentos.core.extensions.registry import ExtensionRegistry
    from agentos.core.capabilities.registry import CapabilityRegistry

    ext_registry = ExtensionRegistry()
    cap_registry = CapabilityRegistry(ext_registry)

    # List all tools
    all_tools = cap_registry.list_tools()

    # Filter by risk level
    safe_tools = cap_registry.list_tools(risk_level_max=RiskLevel.MED)

    # Get specific tool
    tool = cap_registry.get_tool("ext:tools.postman:get")
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from agentos.core.extensions.registry import ExtensionRegistry
from agentos.core.extensions.models import CapabilityType, ExtensionCapability
from agentos.core.capabilities.capability_models import (
    ToolDescriptor,
    RiskLevel,
    SideEffect,
    ToolSource,
    TrustTier,
)

logger = logging.getLogger(__name__)

# Cache TTL in seconds
CACHE_TTL_SECONDS = 60


class CapabilityRegistry:
    """
    Unified capability registry for Extensions and MCP

    This registry provides a single interface for discovering and querying
    tools from multiple sources (Extensions and MCP servers).
    """

    def __init__(
        self,
        extension_registry: ExtensionRegistry,
        mcp_config_path: Optional[Path] = None
    ):
        """
        Initialize capability registry

        Args:
            extension_registry: ExtensionRegistry instance
            mcp_config_path: Path to MCP configuration file (optional)
        """
        self.extension_registry = extension_registry
        self.mcp_config_path = mcp_config_path

        # MCP integration
        self.mcp_clients: Dict[str, 'MCPClient'] = {}
        self.mcp_config_manager: Optional['MCPConfigManager'] = None
        self._init_mcp_config()

        # Cache
        self._cache: Dict[str, ToolDescriptor] = {}
        self._cache_timestamp: float = 0

    def _init_mcp_config(self):
        """Initialize MCP configuration manager"""
        try:
            from agentos.core.mcp import MCPConfigManager
            self.mcp_config_manager = MCPConfigManager(self.mcp_config_path)
            logger.info("MCP configuration manager initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize MCP config manager: {e}")
            self.mcp_config_manager = None

    def list_tools(
        self,
        source_types: Optional[List[ToolSource]] = None,
        risk_level_max: Optional[RiskLevel] = None,
        exclude_side_effects: Optional[List[str]] = None,
        enabled_only: bool = True
    ) -> List[ToolDescriptor]:
        """
        List all available tools

        Args:
            source_types: Filter by source types (extension/mcp), None for all
            risk_level_max: Maximum risk level to include
            exclude_side_effects: Side effects to exclude
            enabled_only: Only return tools from enabled sources

        Returns:
            List of ToolDescriptor objects
        """
        # Refresh cache if needed
        self._refresh_cache_if_needed()

        # Start with all cached tools
        tools = list(self._cache.values())

        # Filter by source type
        if source_types:
            tools = [t for t in tools if t.source_type in source_types]

        # Filter by enabled status
        if enabled_only:
            tools = [t for t in tools if t.enabled]

        # Filter by risk level
        if risk_level_max:
            risk_order = [RiskLevel.LOW, RiskLevel.MED, RiskLevel.HIGH, RiskLevel.CRITICAL]
            max_index = risk_order.index(risk_level_max)
            tools = [t for t in tools if risk_order.index(t.risk_level) <= max_index]

        # Filter by side effects
        if exclude_side_effects:
            tools = [
                t for t in tools
                if not any(effect in t.side_effect_tags for effect in exclude_side_effects)
            ]

        logger.debug(f"Listed {len(tools)} tools (filters applied)")
        return tools

    def get_tool(self, tool_id: str) -> Optional[ToolDescriptor]:
        """
        Get tool descriptor by ID

        Args:
            tool_id: Tool identifier (e.g., "ext:tools.postman:get")

        Returns:
            ToolDescriptor or None if not found
        """
        # Refresh cache if needed
        self._refresh_cache_if_needed()

        tool = self._cache.get(tool_id)
        if tool:
            logger.debug(f"Found tool: {tool_id}")
        else:
            logger.debug(f"Tool not found: {tool_id}")

        return tool

    def search_tools(self, query: str) -> List[ToolDescriptor]:
        """
        Search tools by name or description

        Args:
            query: Search query string

        Returns:
            List of matching ToolDescriptor objects
        """
        # Refresh cache if needed
        self._refresh_cache_if_needed()

        query_lower = query.lower()
        results = [
            tool for tool in self._cache.values()
            if query_lower in tool.name.lower() or query_lower in tool.description.lower()
        ]

        logger.debug(f"Search '{query}' found {len(results)} tools")
        return results

    def refresh(self):
        """Force refresh of tool cache"""
        logger.info("Force refreshing capability cache")
        self._refresh_cache()

    async def refresh_async(self):
        """
        Force refresh of tool cache (async version)

        **Why this method exists:**

        This method is necessary to avoid event loop conflicts when refreshing
        the registry in an async context. The sync version (refresh()) uses
        ThreadPoolExecutor + asyncio.run() which creates a new event loop,
        causing MCP client communication to fail.

        Historical bug:
        - MCP client's _read_loop() runs in event loop A
        - ThreadPoolExecutor creates event loop B for refresh
        - tools/list request sent in loop B
        - Server response arrives in loop A
        - Loop B times out waiting for response (40.90s)

        This async version operates in the current event loop, avoiding the
        conflict entirely.

        Usage:
            # In async context (correct)
            await registry.refresh_async()

            # In sync context (correct)
            registry.refresh()

        See tests/core/capabilities/test_registry_async.py for regression tests.
        """
        logger.info("Force refreshing capability cache (async)")
        await self._refresh_cache_async()

    def _refresh_cache_if_needed(self):
        """Refresh cache if TTL expired"""
        current_time = time.time()
        if current_time - self._cache_timestamp > CACHE_TTL_SECONDS:
            self._refresh_cache()

    def _refresh_cache(self):
        """Refresh tool cache from all sources"""
        logger.debug("Refreshing capability cache")
        new_cache: Dict[str, ToolDescriptor] = {}

        # Load from Extension registry
        try:
            extension_tools = self._load_extension_tools()
            for tool in extension_tools:
                new_cache[tool.tool_id] = tool
            logger.debug(f"Loaded {len(extension_tools)} tools from extensions")
        except Exception as e:
            logger.error(f"Failed to load extension tools: {e}", exc_info=True)
            # Graceful degradation: continue without extension tools

        # Load from MCP servers
        try:
            if self.mcp_config_manager:
                # Check if MCP clients are already connected
                # If so, reuse existing MCP tools from cache to avoid event loop issues
                if self.mcp_clients:
                    logger.debug(f"Reusing {len(self.mcp_clients)} existing MCP clients")
                    # Extract MCP tools from current cache
                    mcp_tools_from_cache = [
                        tool for tool in self._cache.values()
                        if tool.source.type == 'mcp'
                    ]
                    for tool in mcp_tools_from_cache:
                        new_cache[tool.tool_id] = tool
                    logger.debug(f"Reused {len(mcp_tools_from_cache)} tools from MCP cache")
                else:
                    # No MCP clients yet, need to load
                    # Check if we're already in an event loop
                    try:
                        loop = asyncio.get_running_loop()
                        # We're in an event loop, but we can't call async function directly
                        # Skip MCP loading in sync context and log warning
                        logger.warning(
                            "Cannot load MCP tools in sync refresh within async context. "
                            "MCP tools should be loaded explicitly via await registry._load_mcp_tools()"
                        )
                    except RuntimeError:
                        # No event loop, safe to use asyncio.run()
                        mcp_tools = asyncio.run(self._load_mcp_tools())
                        for tool in mcp_tools:
                            new_cache[tool.tool_id] = tool
                        logger.debug(f"Loaded {len(mcp_tools)} tools from MCP")
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}", exc_info=True)
            # Graceful degradation: continue without MCP tools

        self._cache = new_cache
        self._cache_timestamp = time.time()
        logger.info(f"Cache refreshed: {len(self._cache)} tools available")

    async def _refresh_cache_async(self):
        """
        Refresh tool cache from all sources (async version)

        This is the internal async implementation that loads tools from:
        1. Extension registry (sync call)
        2. MCP servers (async call via await self._load_mcp_tools())

        Key difference from _refresh_cache():
        - Uses `await self._load_mcp_tools()` instead of asyncio.run()
        - Operates in current event loop (no nested loop creation)
        - Safe to call from async context

        This method prevents the event loop conflict bug where:
        - asyncio.run() creates a new event loop
        - MCP client communication becomes deadlocked
        - Timeout occurs after 40.90s
        """
        logger.debug("Refreshing capability cache (async)")
        new_cache: Dict[str, ToolDescriptor] = {}

        # Load from Extension registry
        try:
            extension_tools = self._load_extension_tools()
            for tool in extension_tools:
                new_cache[tool.tool_id] = tool
            logger.debug(f"Loaded {len(extension_tools)} tools from extensions")
        except Exception as e:
            logger.error(f"Failed to load extension tools: {e}", exc_info=True)
            # Graceful degradation: continue without extension tools

        # Load from MCP servers
        try:
            if self.mcp_config_manager:
                mcp_tools = await self._load_mcp_tools()
                for tool in mcp_tools:
                    new_cache[tool.tool_id] = tool
                logger.debug(f"Loaded {len(mcp_tools)} tools from MCP")
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}", exc_info=True)
            # Graceful degradation: continue without MCP tools

        self._cache = new_cache
        self._cache_timestamp = time.time()
        logger.info(f"Cache refreshed: {len(self._cache)} tools available")

    def _load_extension_tools(self) -> List[ToolDescriptor]:
        """
        Load tools from Extension registry

        Returns:
            List of ToolDescriptor objects from extensions
        """
        tools: List[ToolDescriptor] = []

        # Get all extensions
        extensions = self.extension_registry.list_extensions()

        for extension in extensions:
            # Process each capability
            for capability in extension.capabilities:
                # Only process slash_command and tool capabilities
                if capability.type in (CapabilityType.SLASH_COMMAND, CapabilityType.TOOL):
                    try:
                        tool_descriptors = self._extension_capability_to_tools(
                            extension_id=extension.id,
                            extension_name=extension.name,
                            capability=capability,
                            permissions=extension.permissions_required,
                            enabled=extension.enabled
                        )
                        tools.extend(tool_descriptors)
                    except Exception as e:
                        logger.warning(
                            f"Failed to convert capability {capability.name} "
                            f"from extension {extension.id}: {e}"
                        )

        return tools

    def _extension_capability_to_tools(
        self,
        extension_id: str,
        extension_name: str,
        capability: ExtensionCapability,
        permissions: List[str],
        enabled: bool
    ) -> List[ToolDescriptor]:
        """
        Convert Extension capability to ToolDescriptor(s)

        An extension capability may map to multiple tools (e.g., /postman with
        multiple actions like get, post, etc.)

        Args:
            extension_id: Extension ID
            extension_name: Extension name
            capability: ExtensionCapability object
            permissions: Required permissions from manifest
            enabled: Whether the extension is enabled

        Returns:
            List of ToolDescriptor objects
        """
        tools: List[ToolDescriptor] = []

        # Get capability config
        config = capability.config or {}

        # For slash commands, we might have multiple actions
        # For now, create a single tool descriptor per capability
        # TODO: Parse commands.yaml to get individual actions

        # Generate tool_id
        tool_id = f"ext:{extension_id}:{capability.name}"

        # Determine risk level
        risk_level = self._determine_risk_level(capability, permissions)

        # Determine side effects
        side_effects = self._determine_side_effects(capability, permissions)

        # Build input schema
        # TODO: Parse from commands.yaml or capability config
        input_schema = config.get("input_schema", {
            "type": "object",
            "properties": {},
            "required": []
        })

        tool = ToolDescriptor(
            tool_id=tool_id,
            name=capability.name,
            description=capability.description,
            input_schema=input_schema,
            output_schema=None,  # TODO: Add if available
            risk_level=risk_level,
            side_effect_tags=side_effects,
            requires_admin_token=risk_level == RiskLevel.CRITICAL,
            source_type=ToolSource.EXTENSION,
            source_id=extension_id,
            timeout_ms=config.get("timeout_ms", 300000),
            permissions_required=permissions,
            enabled=enabled,
            trust_tier=TrustTier.T0  # Extension 默认最高信任
        )

        tools.append(tool)
        logger.debug(f"Created tool descriptor: {tool_id} (risk={risk_level})")

        return tools

    def _determine_risk_level(
        self,
        capability: ExtensionCapability,
        permissions: List[str]
    ) -> RiskLevel:
        """
        Determine risk level for a capability

        Risk level logic:
        - CRITICAL: payments, cloud resource management
        - HIGH: write/delete operations, network access
        - MED: read operations with network
        - LOW: read-only local operations

        Args:
            capability: ExtensionCapability object
            permissions: Required permissions

        Returns:
            RiskLevel enum value
        """
        name_lower = capability.name.lower()
        desc_lower = capability.description.lower()

        # CRITICAL: Financial or cloud operations
        if "payment" in permissions or "cloud" in permissions:
            return RiskLevel.CRITICAL

        # HIGH: Write/delete operations or dangerous keywords
        dangerous_keywords = ["write", "delete", "remove", "update", "modify", "exec"]
        if any(keyword in name_lower or keyword in desc_lower for keyword in dangerous_keywords):
            return RiskLevel.HIGH

        # HIGH: Network access
        if "network" in permissions:
            return RiskLevel.HIGH

        # MED: Default for most operations
        return RiskLevel.MED

    def _determine_side_effects(
        self,
        capability: ExtensionCapability,
        permissions: List[str]
    ) -> List[str]:
        """
        Determine side effects for a capability

        Args:
            capability: ExtensionCapability object
            permissions: Required permissions

        Returns:
            List of side effect tags
        """
        effects: List[str] = []

        name_lower = capability.name.lower()
        desc_lower = capability.description.lower()

        # Filesystem effects
        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["write", "create", "save"]):
            effects.append(SideEffect.FS_WRITE.value)

        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["delete", "remove", "rm"]):
            effects.append(SideEffect.FS_DELETE.value)

        if "read" in name_lower or "read" in desc_lower:
            effects.append(SideEffect.FS_READ.value)

        # Network effects
        if "network" in permissions or any(keyword in name_lower or keyword in desc_lower
                                            for keyword in ["http", "api", "request", "fetch"]):
            effects.append(SideEffect.NETWORK_HTTP.value)

        # System effects
        if any(keyword in name_lower or keyword in desc_lower
               for keyword in ["exec", "command", "run", "execute"]):
            effects.append(SideEffect.SYSTEM_EXEC.value)

        # Cloud effects
        if "cloud" in permissions:
            if any(keyword in name_lower or keyword in desc_lower
                   for keyword in ["create", "provision"]):
                effects.append(SideEffect.CLOUD_RESOURCE_CREATE.value)
            if any(keyword in name_lower or keyword in desc_lower
                   for keyword in ["delete", "destroy", "terminate"]):
                effects.append(SideEffect.CLOUD_RESOURCE_DELETE.value)

        # Payment effects
        if "payment" in permissions:
            effects.append(SideEffect.PAYMENTS.value)

        return effects

    async def _load_mcp_tools(self) -> List[ToolDescriptor]:
        """
        Load tools from MCP servers

        Connects to all enabled MCP servers and collects their tools,
        converting them to ToolDescriptor format with appropriate filtering.

        Returns:
            List of ToolDescriptor objects from MCP servers
        """
        if not self.mcp_config_manager:
            return []

        tools: List[ToolDescriptor] = []

        # Import MCP components
        try:
            from agentos.core.mcp import MCPClient, MCPAdapter
        except ImportError as e:
            logger.error(f"Failed to import MCP components: {e}")
            return []

        adapter = MCPAdapter()

        # Get all enabled servers
        enabled_servers = self.mcp_config_manager.get_enabled_servers()
        logger.info(f"Loading tools from {len(enabled_servers)} MCP servers")

        for server_config in enabled_servers:
            try:
                logger.debug(f"Loading tools from MCP server: {server_config.id}")

                # Get or create client
                client = self.mcp_clients.get(server_config.id)
                if not client:
                    client = MCPClient(server_config)
                    await client.connect()
                    self.mcp_clients[server_config.id] = client
                elif not client.is_alive():
                    # Reconnect if not alive
                    logger.warning(f"MCP client not alive, reconnecting: {server_config.id}")
                    await client.connect()

                # List tools
                mcp_tools = await client.list_tools()
                logger.info(f"Found {len(mcp_tools)} tools from MCP server: {server_config.id}")

                # Convert and filter tools
                for mcp_tool in mcp_tools:
                    try:
                        # Convert to ToolDescriptor
                        descriptor = adapter.mcp_tool_to_descriptor(
                            server_id=server_config.id,
                            mcp_tool=mcp_tool,
                            server_config=server_config
                        )

                        # Apply allow_tools filter
                        if server_config.allow_tools:
                            if descriptor.name not in server_config.allow_tools:
                                logger.debug(
                                    f"Tool {descriptor.name} not in allow_tools, skipping"
                                )
                                continue

                        # Apply deny_side_effect_tags filter
                        if any(tag in descriptor.side_effect_tags
                               for tag in server_config.deny_side_effect_tags):
                            logger.debug(
                                f"Tool {descriptor.name} has denied side effects, skipping"
                            )
                            continue

                        tools.append(descriptor)
                        logger.debug(f"Added MCP tool: {descriptor.tool_id}")

                    except Exception as e:
                        logger.warning(
                            f"Failed to convert MCP tool {mcp_tool.get('name', 'unknown')}: {e}"
                        )
                        continue

            except Exception as e:
                logger.error(
                    f"Failed to load tools from MCP server {server_config.id}: {e}",
                    exc_info=True
                )
                # Graceful degradation: continue with other servers
                continue

        logger.info(f"Successfully loaded {len(tools)} tools from MCP servers")
        return tools

    async def disconnect_mcp_clients(self):
        """
        Disconnect all MCP clients

        Should be called during shutdown to gracefully close connections.
        """
        logger.info(f"Disconnecting {len(self.mcp_clients)} MCP clients")

        for server_id, client in self.mcp_clients.items():
            try:
                await client.disconnect()
                logger.debug(f"Disconnected MCP client: {server_id}")
            except Exception as e:
                logger.error(f"Error disconnecting MCP client {server_id}: {e}")

        self.mcp_clients.clear()
        logger.info("All MCP clients disconnected")
