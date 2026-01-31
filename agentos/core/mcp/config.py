"""
MCP Server Configuration Management

This module handles loading and managing MCP server configurations from YAML files.
Supports configuration validation, filtering, and access controls.

Configuration file format (YAML):
    mcp_servers:
      - id: server-id
        enabled: true
        transport: stdio
        command: ["node", "server.js"]
        allow_tools: ["tool1", "tool2"]  # empty = allow all
        deny_side_effect_tags: ["payments"]
        env: {"KEY": "value"}
        timeout_ms: 30000
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# Default configuration path
DEFAULT_CONFIG_PATH = Path.home() / ".agentos" / "mcp_servers.yaml"


class MCPServerConfig(BaseModel):
    """
    Configuration for a single MCP server

    Attributes:
        id: Unique server identifier
        enabled: Whether the server is enabled
        transport: Transport protocol (currently only "stdio")
        command: Command to start the server
        allow_tools: Whitelist of allowed tools (empty = allow all)
        deny_side_effect_tags: Blacklist of side effect tags
        env: Environment variables for the server process
        timeout_ms: Default timeout for operations
    """

    id: str = Field(
        description="Unique server identifier"
    )
    enabled: bool = Field(
        default=True,
        description="Whether the server is enabled"
    )
    transport: str = Field(
        default="stdio",
        description="Transport protocol (stdio, tcp, ssh, https, http)"
    )
    command: List[str] = Field(
        description="Command to start the server"
    )
    allow_tools: List[str] = Field(
        default_factory=list,
        description="Whitelist of allowed tools (empty = allow all)"
    )
    deny_side_effect_tags: List[str] = Field(
        default_factory=list,
        description="Blacklist of side effect tags to deny"
    )
    env: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables for the server process"
    )
    timeout_ms: int = Field(
        default=30000,
        description="Default timeout for operations in milliseconds"
    )

    @field_validator("transport")
    @classmethod
    def validate_transport(cls, v):
        """Validate transport protocol"""
        allowed = ["stdio", "tcp", "ssh", "https", "http"]
        if v.lower() not in allowed:
            logger.warning(
                f"Transport {v} not in standard list {allowed}. "
                f"This may affect trust tier inference."
            )
        return v

    @field_validator("command")
    @classmethod
    def validate_command(cls, v):
        """Validate command is not empty"""
        if not v:
            raise ValueError("Command cannot be empty")
        return v

    @field_validator("timeout_ms")
    @classmethod
    def validate_timeout(cls, v):
        """Validate timeout is positive"""
        if v <= 0:
            raise ValueError("Timeout must be positive")
        return v


class MCPConfigManager:
    """
    MCP server configuration manager

    Loads and manages MCP server configurations from YAML files.
    Provides filtering and access methods for server configurations.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager

        Args:
            config_path: Path to configuration file (default: ~/.agentos/mcp_servers.yaml)
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._configs: Dict[str, MCPServerConfig] = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            logger.warning(
                f"MCP config file not found: {self.config_path}. "
                f"No MCP servers will be available. "
                f"Create a config file at {self.config_path} to enable MCP integration."
            )
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "mcp_servers" not in data:
                logger.warning(f"No 'mcp_servers' section found in {self.config_path}")
                return

            servers = data["mcp_servers"]
            if not isinstance(servers, list):
                logger.error("'mcp_servers' must be a list")
                return

            # Parse each server config
            for server_data in servers:
                try:
                    config = MCPServerConfig(**server_data)
                    self._configs[config.id] = config
                    logger.info(f"Loaded MCP server config: {config.id} (enabled={config.enabled})")
                except Exception as e:
                    logger.error(f"Failed to parse server config: {e}", exc_info=True)
                    continue

            logger.info(f"Loaded {len(self._configs)} MCP server configurations")

        except Exception as e:
            logger.error(f"Failed to load MCP config from {self.config_path}: {e}", exc_info=True)

    def load_config(self) -> List[MCPServerConfig]:
        """
        Load all server configurations

        Returns:
            List of all server configurations
        """
        return list(self._configs.values())

    def get_server_config(self, server_id: str) -> Optional[MCPServerConfig]:
        """
        Get configuration for a specific server

        Args:
            server_id: Server identifier

        Returns:
            MCPServerConfig or None if not found
        """
        config = self._configs.get(server_id)
        if config:
            logger.debug(f"Found config for server: {server_id}")
        else:
            logger.debug(f"No config found for server: {server_id}")
        return config

    def get_enabled_servers(self) -> List[MCPServerConfig]:
        """
        Get all enabled server configurations

        Returns:
            List of enabled server configurations
        """
        enabled = [cfg for cfg in self._configs.values() if cfg.enabled]
        logger.debug(f"Found {len(enabled)} enabled MCP servers")
        return enabled

    def reload(self):
        """Reload configuration from file"""
        logger.info("Reloading MCP server configuration")
        self._configs.clear()
        self._load_config()

    def is_tool_allowed(self, server_id: str, tool_name: str) -> bool:
        """
        Check if a tool is allowed by server configuration

        Args:
            server_id: Server identifier
            tool_name: Tool name

        Returns:
            True if tool is allowed, False otherwise
        """
        config = self.get_server_config(server_id)
        if not config:
            return False

        # Empty allow_tools list means all tools are allowed
        if not config.allow_tools:
            return True

        return tool_name in config.allow_tools

    def is_side_effect_denied(self, server_id: str, side_effects: List[str]) -> bool:
        """
        Check if any side effect is denied by server configuration

        Args:
            server_id: Server identifier
            side_effects: List of side effect tags

        Returns:
            True if any side effect is denied, False otherwise
        """
        config = self.get_server_config(server_id)
        if not config:
            return True  # Deny if server not found

        # Check if any side effect is in the deny list
        return any(effect in config.deny_side_effect_tags for effect in side_effects)
