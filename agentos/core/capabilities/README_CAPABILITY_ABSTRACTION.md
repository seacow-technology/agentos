# Capability Abstraction Layer (PR-1)

## Overview

The Capability Abstraction Layer provides a unified interface for discovering and invoking tools from multiple sources (Extensions and MCP servers). This layer enables:

- **Unified tool discovery**: Single interface for listing tools from all sources
- **Risk-based access control**: Classify tools by risk level (LOW/MED/HIGH/CRITICAL)
- **Side-effect tracking**: Track and control tool side effects (filesystem, network, etc.)
- **Policy enforcement**: Extensible policy engine for access control (PR-3)
- **Audit trail**: Complete audit logging for compliance and debugging

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Capability Abstraction Layer              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │ CapabilityRegistry│◄────►│   ToolRouter     │            │
│  └──────────────────┘      └──────────────────┘            │
│           │                         │                        │
│           │                         ▼                        │
│           │                ┌──────────────────┐             │
│           │                │  PolicyEngine    │             │
│           │                └──────────────────┘             │
│           │                         │                        │
│           ▼                         ▼                        │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │   Audit Logger   │      │   Tool Executors │            │
│  └──────────────────┘      └──────────────────┘            │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│                        Data Sources                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │ Extension Registry│      │   MCP Client     │            │
│  │  (implemented)    │      │  (PR-2: TODO)    │            │
│  └──────────────────┘      └──────────────────┘            │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Data Models (`capability_models.py`)

Core data structures for the capability system:

- **ToolDescriptor**: Unified tool description
  - `tool_id`: Unique identifier (format: `ext:<ext_id>:<cmd>` or `mcp:<server>:<tool>`)
  - `name`, `description`: Human-readable information
  - `input_schema`, `output_schema`: JSON Schema for validation
  - `risk_level`: Risk classification (LOW/MED/HIGH/CRITICAL)
  - `side_effect_tags`: List of potential side effects
  - `source_type`, `source_id`: Tool source information

- **ToolInvocation**: Invocation request
  - `invocation_id`: Unique invocation identifier
  - `tool_id`: Tool being invoked
  - `inputs`: Input parameters
  - `actor`: User/agent initiating the invocation
  - `mode`: Planning or execution mode
  - `spec_frozen`: Whether the task spec is immutable

- **ToolResult**: Execution result
  - `success`: Whether invocation succeeded
  - `payload`: Tool output
  - `declared_side_effects`: Side effects that occurred
  - `error`: Error message if failed
  - `duration_ms`: Execution duration

### 2. CapabilityRegistry (`registry.py`)

Unified tool discovery and management:

```python
from agentos.core.capabilities import CapabilityRegistry
from agentos.core.extensions.registry import ExtensionRegistry

# Initialize
ext_registry = ExtensionRegistry()
cap_registry = CapabilityRegistry(ext_registry)

# List all tools
all_tools = cap_registry.list_tools()

# Filter by risk level
safe_tools = cap_registry.list_tools(risk_level_max=RiskLevel.MED)

# Filter by side effects
readonly_tools = cap_registry.list_tools(
    exclude_side_effects=[SideEffect.FS_WRITE, SideEffect.FS_DELETE]
)

# Get specific tool
tool = cap_registry.get_tool("ext:tools.postman:get")

# Search tools
results = cap_registry.search_tools("http")
```

**Features:**
- Automatic caching with TTL (60s default)
- Graceful degradation (one source failure doesn't affect others)
- Risk level inference from Extension metadata
- Side effect detection from permissions and naming

### 3. ToolRouter (`router.py`)

Routes tool invocations to appropriate executors:

```python
from agentos.core.capabilities import ToolRouter, ToolInvocation
from datetime import datetime

# Initialize
router = ToolRouter(cap_registry)

# Create invocation
invocation = ToolInvocation(
    invocation_id="inv_123",
    tool_id="ext:tools.postman:get",
    inputs={"url": "https://api.example.com"},
    actor="user@example.com",
    timestamp=datetime.now()
)

# Invoke tool (async)
result = await router.invoke_tool("ext:tools.postman:get", invocation)

# Check result
if result.success:
    print(f"Success: {result.payload}")
else:
    print(f"Error: {result.error}")
```

**Features:**
- Unified invocation interface
- Policy checks before execution (PR-3)
- Automatic audit logging
- Error handling and result normalization
- Synchronous wrapper available: `router.sync_invoke_tool()`

### 4. Audit (`audit.py`)

Audit event emitters for compliance and debugging:

```python
from agentos.core.capabilities.audit import (
    emit_tool_invocation_start,
    emit_tool_invocation_end,
    emit_policy_violation
)

# Log invocation start
emit_tool_invocation_start(invocation)

# Execute tool
result = execute_tool(invocation)

# Log invocation end
emit_tool_invocation_end(result)
```

**PR-1**: Logs to standard Python logger
**PR-3**: Will integrate with `task_audits` table

### 5. PolicyEngine (`policy.py`)

Access control and gating:

```python
from agentos.core.capabilities.policy import ToolPolicyEngine

# Initialize
engine = ToolPolicyEngine()

# Check if invocation is allowed
decision = engine.check_allowed(tool, invocation)

if not decision.allowed:
    print(f"Denied: {decision.reason}")
    if decision.requires_approval:
        # Request admin approval
        request_approval(decision.approval_context)
```

**PR-1**: Allow-all policy (basic structure)
**PR-3**: Complete implementation with:
- Risk-based approval requirements
- Spec freezing for high-risk operations
- Admin token verification
- Side-effect policies

## Tool ID Format

Tool IDs follow a consistent format:

- **Extension tools**: `ext:<extension_id>:<command_name>`
  - Example: `ext:tools.postman:get`

- **MCP tools**: `mcp:<server_name>:<tool_name>`
  - Example: `mcp:filesystem:read_file`

This format enables:
- Clear source identification
- Collision-free naming
- Easy routing to correct executor

## Risk Levels

Tools are classified by risk level:

| Level    | Description | Examples |
|----------|-------------|----------|
| LOW      | Read-only, no side effects | List files, read config |
| MED      | Limited side effects, reversible | Create file, HTTP GET |
| HIGH     | Significant side effects | Delete files, HTTP POST |
| CRITICAL | Dangerous operations | Payments, cloud resources |

Risk level determines:
- Whether admin approval is required (PR-3)
- Whether spec freezing is needed (PR-3)
- Default audit verbosity

## Side Effects

Side effects are tracked for transparency:

| Category | Side Effects |
|----------|--------------|
| Filesystem | `fs.read`, `fs.write`, `fs.delete`, `fs.chmod` |
| Network | `network.http`, `network.socket`, `network.dns` |
| Cloud | `cloud.key_read`, `cloud.key_write`, `cloud.resource_create`, `cloud.resource_delete` |
| Financial | `payments` |
| System | `system.exec`, `system.env` |
| Database | `database.read`, `database.write`, `database.delete` |

## Extension → ToolDescriptor Mapping

Extensions are automatically mapped to ToolDescriptors:

1. **Risk Level Detection**:
   - Keywords in name/description (write, delete, exec) → HIGH
   - Network permission → HIGH
   - Payment/cloud permission → CRITICAL
   - Default → MED

2. **Side Effect Detection**:
   - Inferred from permissions and keywords
   - `network` permission → `network.http`
   - "write" keyword → `fs.write`
   - "delete" keyword → `fs.delete`

3. **Input Schema**:
   - Parsed from `commands.yaml` (TODO)
   - Fallback to generic schema

## Usage Example

See `/examples/capability_usage_example.py` for a complete example:

```bash
python3 examples/capability_usage_example.py
```

## Testing

Run unit tests:

```bash
python3 -m pytest tests/core/capabilities/test_capability_registry.py -v
```

Tests cover:
- ✓ ToolDescriptor creation
- ✓ Extension to ToolDescriptor mapping
- ✓ Registry tool listing and filtering
- ✓ Router dispatching
- ✓ Policy engine (basic)

## Future Work (PR-2 and PR-3)

### PR-2: MCP Integration
- Implement MCP client
- Add MCP tool discovery
- Implement MCP tool invocation
- Add MCP server management

### PR-3: Security Gates
- Implement complete policy engine
- Add spec freezing mechanism
- Add admin approval flow
- Integrate with `task_audits` table
- Add risk-based execution gates

## API Reference

### CapabilityRegistry

```python
class CapabilityRegistry:
    def __init__(
        self,
        extension_registry: ExtensionRegistry,
        mcp_client=None  # PR-2
    )

    def list_tools(
        self,
        source_types: Optional[List[ToolSource]] = None,
        risk_level_max: Optional[RiskLevel] = None,
        exclude_side_effects: Optional[List[str]] = None,
        enabled_only: bool = True
    ) -> List[ToolDescriptor]

    def get_tool(self, tool_id: str) -> Optional[ToolDescriptor]

    def search_tools(self, query: str) -> List[ToolDescriptor]

    def refresh(self)
```

### ToolRouter

```python
class ToolRouter:
    def __init__(
        self,
        registry: CapabilityRegistry,
        policy_engine: Optional[ToolPolicyEngine] = None
    )

    async def invoke_tool(
        self,
        tool_id: str,
        invocation: ToolInvocation
    ) -> ToolResult

    def sync_invoke_tool(
        self,
        tool_id: str,
        invocation: ToolInvocation
    ) -> ToolResult
```

### ToolPolicyEngine

```python
class ToolPolicyEngine:
    def check_allowed(
        self,
        tool: ToolDescriptor,
        invocation: ToolInvocation
    ) -> PolicyDecision

    def requires_spec_freezing(self, tool: ToolDescriptor) -> bool

    def requires_admin_approval(self, tool: ToolDescriptor) -> bool
```

## License

Same as AgentOS project license.
