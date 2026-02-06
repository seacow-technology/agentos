# MCP Integration Module

This module provides integration with Model Context Protocol (MCP) servers, allowing AgentOS to use tools from MCP-compliant servers alongside native Extensions.

## Architecture

The MCP integration consists of four main components:

### 1. Configuration Management (`config.py`)

Loads and manages MCP server configurations from YAML files.

```python
from agentos.core.mcp import MCPConfigManager

manager = MCPConfigManager()  # Loads from ~/.agentos/mcp_servers.yaml
enabled_servers = manager.get_enabled_servers()
```

**Configuration Format:**

```yaml
mcp_servers:
  - id: server-id
    enabled: true
    transport: stdio
    command: ["node", "server.js"]
    allow_tools: ["tool1", "tool2"]  # empty = allow all
    deny_side_effect_tags: ["payments"]
    env: {"KEY": "value"}
    timeout_ms: 30000
```

### 2. MCP Client (`client.py`)

Implements the MCP protocol client using stdio transport.

```python
from agentos.core.mcp import MCPClient, MCPServerConfig

config = MCPServerConfig(
    id="my-server",
    command=["node", "server.js"]
)

client = MCPClient(config)
await client.connect()

# List available tools
tools = await client.list_tools()

# Call a tool
result = await client.call_tool("tool_name", {"arg": "value"})

await client.disconnect()
```

**Features:**
- Async subprocess management
- JSON-RPC 2.0 communication
- Timeout handling
- Graceful connection management
- Error recovery

### 3. Adapter (`adapter.py`)

Converts MCP tool schemas to the unified ToolDescriptor format.

```python
from agentos.core.mcp import MCPAdapter

adapter = MCPAdapter()

# Convert MCP tool to ToolDescriptor
descriptor = adapter.mcp_tool_to_descriptor(
    server_id="my-server",
    mcp_tool=mcp_tool_schema,
    server_config=config
)

# Infer risk level
risk = adapter.infer_risk_level(
    tool_name="delete_file",
    tool_description="Delete a file",
    input_schema={}
)  # Returns RiskLevel.HIGH

# Convert MCP result to ToolResult
result = adapter.mcp_result_to_tool_result(
    invocation_id="inv_123",
    mcp_result=mcp_result,
    duration_ms=150
)
```

**Risk Inference Strategy:**

- **CRITICAL**: Payment operations, key management, dangerous deletions
- **HIGH**: Write/delete operations, execution, resource creation
- **MED**: Default for uncertain operations
- **LOW**: Read-only operations (get, list, search)

**Side Effect Inference:**

The adapter automatically infers side effects based on tool name and description:

- `fs.read`, `fs.write`, `fs.delete`, `fs.chmod` - Filesystem operations
- `network.http`, `network.socket`, `network.dns` - Network operations
- `cloud.*` - Cloud resource operations
- `payments` - Financial operations
- `system.exec`, `system.env` - System operations
- `database.*` - Database operations

### 4. Health Checker (`health.py`)

Monitors MCP server health and availability.

```python
from agentos.core.mcp import MCPHealthChecker, HealthStatus

checker = MCPHealthChecker(client)

# Perform health check
result = await checker.check_health()
if result.status == HealthStatus.HEALTHY:
    print("Server is healthy")

# Start continuous monitoring
await checker.start_monitoring(interval_seconds=60)

# Stop monitoring
await checker.stop_monitoring()
```

**Health Status:**
- `HEALTHY`: Server is responsive and functioning normally
- `DEGRADED`: Server is responsive but slow or experiencing issues
- `UNHEALTHY`: Server is not responsive or has failed

## Integration with Capability System

The MCP module integrates seamlessly with the unified Capability abstraction layer:

### Registry Integration

```python
from agentos.core.capabilities.registry import CapabilityRegistry
from agentos.core.extensions.registry import ExtensionRegistry

ext_registry = ExtensionRegistry()
cap_registry = CapabilityRegistry(
    ext_registry,
    mcp_config_path=Path("mcp_servers.yaml")
)

# List all tools (including MCP)
all_tools = cap_registry.list_tools()

# Filter by source
mcp_tools = cap_registry.list_tools(source_types=[ToolSource.MCP])

# Get specific MCP tool
tool = cap_registry.get_tool("mcp:server-id:tool_name")
```

### Router Integration

```python
from agentos.core.capabilities.router import ToolRouter
from agentos.core.capabilities.capability_models import ToolInvocation

router = ToolRouter(cap_registry)

invocation = ToolInvocation(
    invocation_id="inv_123",
    tool_id="mcp:server-id:tool_name",
    inputs={"arg": "value"},
    actor="user@example.com",
    project_id="proj_123",
    spec_frozen=True,
    spec_hash="abc123"
)

# Router automatically dispatches to MCP client
result = await router.invoke_tool("mcp:server-id:tool_name", invocation)
```

## Configuration Examples

### Basic Configuration

```yaml
mcp_servers:
  - id: echo-server
    enabled: true
    command: ["node", "servers/echo/index.js"]
```

### Restricted Configuration

```yaml
mcp_servers:
  - id: filesystem
    enabled: true
    command: ["python3", "-m", "mcp_filesystem"]
    # Only allow read operations
    allow_tools:
      - "read_file"
      - "list_directory"
    # Deny dangerous operations
    deny_side_effect_tags:
      - "fs.write"
      - "fs.delete"
      - "fs.chmod"
```

### Production Configuration

```yaml
mcp_servers:
  - id: api-server
    enabled: true
    command: ["node", "servers/api/index.js"]
    allow_tools: ["fetch", "get", "post"]
    deny_side_effect_tags:
      - "payments"
      - "cloud.resource_delete"
    env:
      API_KEY: "${API_KEY}"  # Load from environment
      NODE_ENV: "production"
    timeout_ms: 60000
```

## Security Considerations

### 1. Server Configuration

- **Default to disabled**: New servers should be `enabled: false` by default
- **Use whitelists**: Prefer `allow_tools` over allowing all tools
- **Deny dangerous operations**: Use `deny_side_effect_tags` to block high-risk operations
- **Set timeouts**: Configure appropriate `timeout_ms` to prevent hanging

### 2. Risk Classification

The adapter automatically classifies tools by risk level:

- Tools are filtered by the policy engine based on risk level
- CRITICAL risk tools require admin approval
- HIGH risk tools may require additional checks

### 3. Graceful Degradation

- If an MCP server fails to connect, the system continues without it
- Failed health checks mark servers as UNHEALTHY but don't crash the system
- Registry refresh gracefully handles server failures

### 4. Isolation

Currently, MCP servers run as separate processes with:
- Stdio-based communication (no network exposure)
- Environment variable isolation
- Process-level resource limits (via OS)

Future enhancements may include:
- Container-based isolation
- Network restrictions
- Filesystem sandboxing

## Error Handling

### Connection Errors

```python
from agentos.core.mcp import MCPConnectionError

try:
    await client.connect()
except MCPConnectionError as e:
    logger.error(f"Failed to connect: {e}")
    # Graceful degradation - continue without this server
```

### Timeout Errors

```python
from agentos.core.mcp import MCPTimeoutError

try:
    result = await client.call_tool("slow_tool", {})
except MCPTimeoutError as e:
    logger.error(f"Tool timed out: {e}")
    # Return error to user
```

### Protocol Errors

```python
from agentos.core.mcp import MCPProtocolError

try:
    tools = await client.list_tools()
except MCPProtocolError as e:
    logger.error(f"Protocol error: {e}")
    # Mark server as unhealthy
```

## Testing

Comprehensive unit tests are provided in `tests/core/mcp/test_mcp_client.py`:

```bash
# Run all MCP tests
pytest tests/core/mcp/test_mcp_client.py -v

# Run specific test
pytest tests/core/mcp/test_mcp_client.py::test_config_loading -v

# Run with coverage
pytest tests/core/mcp/ --cov=agentos.core.mcp --cov-report=html
```

Test coverage includes:
- Configuration loading and validation
- Client connection and communication
- Tool listing and invocation
- MCP to ToolDescriptor mapping
- Risk and side effect inference
- Health checking
- Registry and router integration
- Graceful degradation scenarios

## Example: Creating an MCP Server

To create your own MCP server, implement the following JSON-RPC methods:

```javascript
// Initialize
{
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "agentos", "version": "0.3.1"}
  }
}

// List tools
{
  "method": "tools/list",
  "params": {}
}
// Response: {"tools": [...]}

// Call tool
{
  "method": "tools/call",
  "params": {
    "name": "tool_name",
    "arguments": {"arg": "value"}
  }
}
// Response: {"content": [...], "isError": false}
```

See `examples/mcp_servers.yaml.example` for configuration examples.

## Roadmap

### Phase 1 (Current): Basic Integration
- [x] Stdio transport
- [x] Tool discovery and invocation
- [x] Risk and side effect inference
- [x] Health monitoring
- [x] Registry integration

### Phase 2 (Future): Enhanced Security
- [ ] Container-based isolation (Docker/Podman)
- [ ] Network sandboxing
- [ ] Filesystem restrictions
- [ ] Resource limits (CPU/memory)

### Phase 3 (Future): Advanced Features
- [ ] Server marketplace
- [ ] Automatic server discovery
- [ ] Server versioning and updates
- [ ] Performance metrics and monitoring

## References

- [MCP Protocol Specification](https://github.com/anthropics/mcp)
- [AgentOS Capability Abstraction](../capabilities/README_CAPABILITY_ABSTRACTION.md)
- [Example Configuration](../../../examples/mcp_servers.yaml.example)
