"""
MCP Marketplace Data Models

This module defines the data models for MCP Package declarations and governance previews.
MCP Packages are "declarations", not "permissions" - they describe what an MCP server
provides and recommends for governance, but the final governance decisions are made
by the AgentOS policy engine.

Architecture:
- MCPPackage: Complete MCP metadata for marketplace display
- MCPGovernancePreview: Pre-connection risk assessment and governance preview
- MCPToolDeclaration: Individual tool declaration from MCP manifest
- MCPSideEffect: Side effect types that tools can declare

Key Principles:
- Registry stores only metadata, not code
- Trust Tier and Quota are "suggestions", not "decisions"
- Local registry is versionable and auditable
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class MCPTransportType(str, Enum):
    """MCP transport protocol types"""
    STDIO = "stdio"
    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    SSH = "ssh"


class MCPSideEffect(str, Enum):
    """MCP declared side effect types

    These are standard side effect declarations that MCP packages should use
    to declare what operations their tools perform.
    """
    FILESYSTEM_READ = "filesystem_read"
    FILESYSTEM_WRITE = "filesystem_write"
    FILESYSTEM_DELETE = "filesystem_delete"
    NETWORK_READ = "network_read"
    NETWORK_WRITE = "network_write"
    PAYMENT = "payment"
    DATABASE = "database"
    DATABASE_READ = "database_read"
    DATABASE_WRITE = "database_write"
    SYSTEM_COMMAND = "system_command"
    USER_NOTIFICATION = "user_notification"
    CLOUD_RESOURCE_CREATE = "cloud_resource_create"
    CLOUD_RESOURCE_DELETE = "cloud_resource_delete"


class MCPToolDeclaration(BaseModel):
    """MCP Tool Declaration (from MCP Package manifest)

    This represents a single tool provided by an MCP server,
    including its schema and declared side effects.
    """
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    input_schema: Dict[str, Any] = Field(..., description="JSON Schema for tool inputs")
    side_effects: List[MCPSideEffect] = Field(
        default_factory=list,
        description="Declared side effects for this tool"
    )
    requires_confirmation: bool = Field(
        default=False,
        description="Whether this tool should require user confirmation"
    )


class MCPPackage(BaseModel):
    """MCP Package Complete Declaration

    This is the MCP metadata displayed in the Marketplace.
    Note: This is only a declaration, not the final governance policy.

    The package describes:
    - What the MCP server provides (tools, capabilities)
    - What side effects it declares
    - What connection configuration is needed
    - What governance is recommended (but not enforced)

    Connection Status:
    - is_connected: Whether this package is currently connected to local AgentOS
    - connected_at: When it was connected (ISO timestamp)
    """
    # Basic Information
    package_id: str = Field(..., description="Unique identifier, e.g., 'smithery.ai/github'")
    name: str = Field(..., description="Display name")
    version: str = Field(..., description="Version number")
    author: str = Field(..., description="Author/Provider")
    description: str = Field(..., description="Short description")
    long_description: Optional[str] = Field(None, description="Detailed description")

    # Capability Declaration
    tools: List[MCPToolDeclaration] = Field(
        default_factory=list,
        description="List of tools provided by this MCP"
    )
    declared_side_effects: List[MCPSideEffect] = Field(
        default_factory=list,
        description="All side effects declared by this MCP's tools"
    )

    # Connection Configuration
    transport: MCPTransportType = Field(..., description="Transport protocol")
    connection_template: Dict[str, Any] = Field(
        ...,
        description="Connection config template, e.g., {command: 'npx', args: [...]}"
    )

    # Governance Recommendations (non-mandatory)
    recommended_trust_tier: str = Field(
        ...,
        description="Recommended trust tier T0-T3"
    )
    recommended_quota_profile: str = Field(
        "medium",
        description="Recommended quota profile: tight/medium/loose"
    )
    requires_admin_token: bool = Field(
        False,
        description="Whether admin token is recommended"
    )

    # Metadata
    homepage: Optional[str] = Field(None, description="Homepage URL")
    repository: Optional[str] = Field(None, description="Repository URL")
    license: Optional[str] = Field(None, description="License")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")

    # Status (client-side only)
    is_connected: bool = Field(
        False,
        description="Whether this MCP is connected to local AgentOS"
    )
    connected_at: Optional[str] = Field(
        None,
        description="Connection timestamp (ISO format)"
    )


class MCPGovernancePreview(BaseModel):
    """Governance Preview (pre-connection risk assessment)

    This provides a preview of what governance policies would be applied
    if this MCP package were to be connected. It helps users understand
    the risk level and restrictions before connecting.

    This is generated by analyzing the package declaration and inferring
    the appropriate governance policies based on:
    - Transport type (affects trust tier)
    - Declared side effects (affects risk level)
    - Tool characteristics (affects quota needs)

    Note: This is a preview, not a final decision. The actual governance
    policies are applied by the policy engine at runtime.
    """
    package_id: str = Field(..., description="Package ID this preview is for")

    # Automatic Inference
    inferred_trust_tier: str = Field(
        ...,
        description="Inferred trust tier based on transport type"
    )
    inferred_risk_level: str = Field(
        ...,
        description="Inferred risk level: LOW/MEDIUM/HIGH/CRITICAL"
    )

    # Default Policy
    default_quota: Dict[str, Any] = Field(
        ...,
        description="Default quota that would be applied"
    )
    requires_admin_token_for: List[str] = Field(
        default_factory=list,
        description="What operations require admin token, e.g., ['side_effects', 'all_calls']"
    )

    # Gate Predictions
    gate_warnings: List[str] = Field(
        default_factory=list,
        description="Predicted gate warnings that may be triggered"
    )

    # Audit Requirements
    audit_level: str = Field(
        "standard",
        description="Required audit level: standard/enhanced/forensic"
    )
