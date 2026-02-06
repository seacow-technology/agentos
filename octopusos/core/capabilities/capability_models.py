"""
Data models for the unified Capability abstraction layer

This module defines the core data models for the capability system that unifies
Extension and MCP tools into a consistent interface for discovery, invocation,
and auditing.

Models:
- ToolDescriptor: Unified tool description from any source
- ToolInvocation: Request to execute a tool
- ToolResult: Result from tool execution
- SideEffect: Enumeration of possible side effects
- RiskLevel: Tool risk classification
- ToolSource: Source type enumeration
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from agentos.core.capabilities.governance_models.provenance import ProvenanceStamp


class ToolSource(str, Enum):
    """Source type for a capability"""
    EXTENSION = "extension"
    MCP = "mcp"


class RiskLevel(str, Enum):
    """Risk level classification for tools"""
    LOW = "LOW"           # Read-only operations, no side effects
    MED = "MED"           # Limited side effects, reversible
    HIGH = "HIGH"         # Significant side effects (write/delete files, network)
    CRITICAL = "CRITICAL"  # Dangerous operations (payments, cloud resources)


class TrustTier(str, Enum):
    """
    信任层级

    定义能力来源的信任级别，自动应用不同的治理强度。
    Trust tier is the "default governance strength", not permission or enable/disable.

    Tiers:
    - T0: Local Extension (highest trust, most permissive)
    - T1: Local MCP (same host, high trust)
    - T2: Remote MCP (LAN/private, moderate trust)
    - T3: Cloud MCP (internet, lowest trust, most restrictive)
    """
    T0 = "local_extension"    # Local Extension (最高信任)
    T1 = "local_mcp"          # Local MCP (same host)
    T2 = "remote_mcp"         # Remote MCP (LAN/private)
    T3 = "cloud_mcp"          # Cloud MCP (internet, 最低信任)


class SideEffect(str, Enum):
    """Enumeration of possible side effects from tool execution"""

    # Filesystem operations
    FS_READ = "fs.read"
    FS_WRITE = "fs.write"
    FS_DELETE = "fs.delete"
    FS_CHMOD = "fs.chmod"

    # Network operations
    NETWORK_HTTP = "network.http"
    NETWORK_SOCKET = "network.socket"
    NETWORK_DNS = "network.dns"

    # Cloud operations
    CLOUD_KEY_READ = "cloud.key_read"
    CLOUD_KEY_WRITE = "cloud.key_write"
    CLOUD_RESOURCE_CREATE = "cloud.resource_create"
    CLOUD_RESOURCE_DELETE = "cloud.resource_delete"

    # Financial operations
    PAYMENTS = "payments"

    # System operations
    SYSTEM_EXEC = "system.exec"
    SYSTEM_ENV = "system.env"

    # Database operations
    DATABASE_READ = "database.read"
    DATABASE_WRITE = "database.write"
    DATABASE_DELETE = "database.delete"


class ExecutionMode(str, Enum):
    """Execution mode for tool invocation"""
    PLANNING = "planning"    # Tool is being invoked during planning phase
    EXECUTION = "execution"  # Tool is being executed for real


class ToolDescriptor(BaseModel):
    """
    Unified tool descriptor

    This represents a tool capability from any source (Extension or MCP),
    providing a consistent interface for discovery and metadata.

    Tool ID Format:
    - Extension: "ext:<extension_id>:<command_name>"
    - MCP: "mcp:<server_name>:<tool_name>"

    Examples:
    - "ext:tools.postman:get"
    - "mcp:filesystem:read_file"
    """
    tool_id: str = Field(
        description="Unique tool identifier (format: 'ext:<ext_id>:<cmd>' or 'mcp:<server>:<tool>')"
    )
    name: str = Field(
        description="Human-readable tool name"
    )
    description: str = Field(
        description="Tool description"
    )
    input_schema: Dict[str, Any] = Field(
        description="JSON Schema for tool inputs"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON Schema for tool outputs (optional)"
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.MED,
        description="Risk level classification"
    )
    side_effect_tags: List[str] = Field(
        default_factory=list,
        description="List of side effect tags (e.g., ['fs.write', 'network'])"
    )
    requires_admin_token: bool = Field(
        default=False,
        description="Whether this tool requires admin approval"
    )
    source_type: ToolSource = Field(
        description="Source type (extension or mcp)"
    )
    source_id: str = Field(
        description="Source identifier (extension ID or MCP server name)"
    )
    timeout_ms: Optional[int] = Field(
        default=300000,  # 5 minutes default
        description="Timeout in milliseconds"
    )

    # Trust tier (信任层级)
    trust_tier: TrustTier = Field(
        default=TrustTier.T1,
        description="信任层级，影响默认治理策略 (Trust tier affecting default governance policies)"
    )

    # Additional metadata
    permissions_required: List[str] = Field(
        default_factory=list,
        description="Required permissions from manifest"
    )
    enabled: bool = Field(
        default=True,
        description="Whether the tool is currently enabled"
    )
    source_version: Optional[str] = Field(
        default=None,
        description="Version of the source (extension or MCP server)"
    )


class ToolInvocation(BaseModel):
    """
    Record of a tool invocation request

    This captures all information about a tool invocation for auditing
    and policy enforcement.
    """
    invocation_id: str = Field(
        description="Unique invocation identifier"
    )
    tool_id: str = Field(
        description="Tool identifier being invoked"
    )
    task_id: Optional[str] = Field(
        default=None,
        description="Associated task ID (if part of a task)"
    )
    project_id: Optional[str] = Field(
        default=None,
        description="Associated project ID"
    )
    spec_hash: Optional[str] = Field(
        default=None,
        description="Hash of the task spec (for plan freezing)"
    )
    spec_frozen: bool = Field(
        default=False,
        description="Whether the task spec is frozen (immutable)"
    )
    mode: ExecutionMode = Field(
        default=ExecutionMode.EXECUTION,
        description="Execution mode (planning or execution)"
    )
    inputs: Dict[str, Any] = Field(
        description="Tool input parameters"
    )
    actor: str = Field(
        description="Actor initiating the invocation (user ID or agent ID)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Invocation timestamp"
    )

    # Optional context
    session_id: Optional[str] = Field(
        default=None,
        description="Chat session ID"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User identifier"
    )


class ToolResult(BaseModel):
    """
    Result from tool execution

    This captures the outcome of a tool invocation including success status,
    payload, side effects, and any errors.
    """
    invocation_id: str = Field(
        description="Invocation ID this result corresponds to"
    )
    success: bool = Field(
        description="Whether the invocation succeeded"
    )
    payload: Any = Field(
        description="Tool output payload"
    )
    declared_side_effects: List[str] = Field(
        default_factory=list,
        description="Side effects that occurred during execution"
    )
    evidence: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Evidence pointers (logs, attachments, etc.)"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
    duration_ms: int = Field(
        description="Execution duration in milliseconds"
    )

    # Timestamps
    started_at: Optional[datetime] = Field(
        default=None,
        description="Execution start time"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Execution completion time"
    )

    # Additional metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional execution metadata"
    )

    # Provenance tracking (PR-C)
    provenance: Optional['ProvenanceStamp'] = Field(
        default=None,
        description="Provenance information for result traceability"
    )


class PolicyDecision(BaseModel):
    """
    Result of a policy check

    This represents the decision from the policy engine about whether
    a tool invocation should be allowed.
    """
    allowed: bool = Field(
        description="Whether the invocation is allowed"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Reason for denial (if not allowed)"
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether the invocation requires manual approval"
    )
    approval_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Context for approval request"
    )


# Rebuild models after all definitions are complete
# This is needed for forward references to work properly
def _rebuild_models():
    """Rebuild models to resolve forward references"""
    try:
        from agentos.core.capabilities.governance_models.provenance import ProvenanceStamp
        ToolResult.model_rebuild()
    except ImportError:
        # ProvenanceStamp not available yet, models will be rebuilt later
        pass

# Call rebuild on module import
_rebuild_models()
