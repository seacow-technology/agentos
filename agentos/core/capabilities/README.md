# Capability Runner System

The Capability Runner system provides the execution framework for extension capabilities in AgentOS. It handles routing commands to appropriate executors, managing execution context, and returning formatted results.

## Architecture

```
CommandRoute (from Slash Router)
    ↓
CapabilityRunner
    ↓
Executor Selection (exec, analyze, etc.)
    ↓
Execution in Controlled Environment
    ↓
Result Formatting
    ↓
CapabilityResult (to Chat UI)
```

## Core Components

### 1. CapabilityRunner (`runner.py`)

Main orchestrator that:
- Routes commands to appropriate executors
- Manages execution context
- Handles errors gracefully
- Formats results for display
- Logs execution for audit

**Example:**
```python
from agentos.core.capabilities import CapabilityRunner, CommandRoute, ExecutionContext
from pathlib import Path

runner = CapabilityRunner()

route = CommandRoute(
    command_name="/postman",
    extension_id="tools.postman",
    action_id="get",
    runner="exec.postman_cli",
    args=["https://api.example.com"]
)

context = ExecutionContext(
    session_id="abc123",
    user_id="user1",
    extension_id="tools.postman",
    work_dir=Path(".agentos/extensions/tools.postman/work")
)

result = runner.execute(route, context)

if result.success:
    print(result.output)
else:
    print(f"Error: {result.error}")
```

### 2. Executors (`executors.py`)

Different executor types for different runner patterns:

#### ExecToolExecutor
Executes command-line tools (exec.xxx runner type).

**Supports:**
- `exec.postman_cli` - Execute postman CLI
- `exec.curl` - Execute curl
- `exec.ffmpeg` - Execute ffmpeg
- Any `exec.<tool_name>` pattern

**Example:**
```python
executor = ExecToolExecutor()

result = executor.execute(route, context)
```

#### AnalyzeResponseExecutor
Analyzes output using LLM (analyze.response runner type).

**Features:**
- Analyze previous command output
- Analyze provided data
- Use extension usage docs for context
- Provide simple analysis fallback

**Example:**
```python
# Analyze last response
route = CommandRoute(
    command_name="/postman",
    extension_id="tools.postman",
    action_id="explain",
    runner="analyze.response",
    args=["last_response"]
)

result = executor.execute(route, context)
```

### 3. ToolExecutor (`tool_executor.py`)

Executes command-line tools in a controlled environment.

**Security Features:**
- Working directory isolation
- PATH restrictions
- Environment variable whitelisting
- Timeout control
- Output capture

**Tool Resolution:**
1. `.agentos/tools/<tool_name>`
2. `.agentos/bin/<tool_name>`
3. System PATH

**Example:**
```python
from agentos.core.capabilities.tool_executor import ToolExecutor

executor = ToolExecutor()

result = executor.execute_tool(
    tool_name="postman",
    args=["get", "https://api.example.com"],
    work_dir=Path(".agentos/extensions/tools.postman/work"),
    timeout=300
)

print(f"Exit code: {result.exit_code}")
print(f"Output: {result.stdout}")
print(f"Duration: {result.duration_ms}ms")
```

### 4. ResponseStore (`response_store.py`)

Stores the last response from each session for follow-up commands.

**Features:**
- Per-session storage
- Automatic size limiting (1MB max)
- TTL expiration (24 hours default)
- Metadata support

**Example:**
```python
from agentos.core.capabilities.response_store import get_response_store

store = get_response_store()

# Save response
store.save("session_123", response_data, metadata={
    "extension_id": "tools.postman",
    "command": "/postman get"
})

# Retrieve response
response = store.get("session_123")
```

## Data Models

### CommandRoute
Parsed slash command from the router:
```python
@dataclass
class CommandRoute:
    command_name: str      # e.g., "/postman"
    extension_id: str      # e.g., "tools.postman"
    action_id: str         # e.g., "get", "list"
    runner: str            # e.g., "exec.postman_cli"
    args: List[str]        # Command arguments
    flags: Dict[str, Any]  # Named flags
    description: Optional[str]
    metadata: Dict[str, Any]
```

### ExecutionContext
Context for capability execution:
```python
@dataclass
class ExecutionContext:
    session_id: str
    user_id: str
    extension_id: str
    work_dir: Path
    usage_doc: Optional[str]      # From docs/USAGE.md
    last_response: Optional[str]  # Previous output
    timeout: int = 300            # Seconds
    env_whitelist: List[str]      # Allowed env vars
```

### CapabilityResult
Final result returned to user:
```python
@dataclass
class CapabilityResult:
    success: bool
    output: str
    error: Optional[str]
    metadata: Dict[str, Any]
    artifacts: List[Path]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
```

## Integration with Chat

In your chat handler or slash router:

```python
from agentos.core.capabilities import CapabilityRunner, ExecutionContext
from pathlib import Path

def execute_extension_capability(route: CommandRoute, session_id: str):
    # 1. Prepare context
    context = ExecutionContext(
        session_id=session_id,
        user_id=get_current_user_id(),
        extension_id=route.extension_id,
        usage_doc=read_extension_usage(route.extension_id),
        work_dir=Path(f".agentos/extensions/{route.extension_id}/work/"),
        timeout=300
    )

    # 2. Execute
    runner = CapabilityRunner()
    result = runner.execute(route, context)

    # 3. Format response for user
    if result.success:
        return {
            "type": "capability_result",
            "output": result.output,
            "metadata": result.metadata,
            "duration": result.duration_seconds
        }
    else:
        return {
            "type": "capability_error",
            "error": result.error,
            "hint": "Check the extension logs for details."
        }
```

## Error Handling

The system provides user-friendly error messages:

### ToolNotFoundError
```
postman not found.

Hint: Make sure the extension is installed correctly.
You may need to reinstall the extension.
```

### TimeoutError
```
Command timed out after 300 seconds.

Hint: The command took too long. Try increasing the timeout
or simplifying the operation.
```

### SecurityError
```
Work directory /etc is not safe or does not exist.

Hint: This operation violates security policies.
Check the command and work directory.
```

## Runner Types

### Implemented

- `exec.<tool_name>` - Execute command-line tools
- `analyze.response` - Analyze output with LLM
- `analyze.schema` - Analyze JSON schema (stub)

### Future Extensions

- `browser.navigate` - Navigate to URLs in browser
- `api.call` - Make API calls directly
- `python.script` - Execute Python scripts
- `node.script` - Execute Node.js scripts

## Security

### Sandboxed Execution

1. **Working Directory Isolation**
   - Commands run in `.agentos/extensions/<id>/work/`
   - Cannot access files outside work directory

2. **PATH Restrictions**
   - Only `.agentos/tools/` and `.agentos/bin/` + system PATH
   - No arbitrary executable paths

3. **Environment Whitelisting**
   - Only safe environment variables allowed
   - No sensitive data in environment

4. **Timeout Control**
   - Default 300 seconds (5 minutes)
   - Prevents runaway processes

### Audit Logging

All executions are logged with:
- Extension ID
- Command and action
- User and session ID
- Success/failure
- Duration
- Error details (if failed)

## Testing

Run all tests:
```bash
pytest tests/unit/core/capabilities/ -v
```

Run specific test suites:
```bash
# Response store
pytest tests/unit/core/capabilities/test_response_store.py -v

# Tool executor
pytest tests/unit/core/capabilities/test_tool_executor.py -v

# Runner
pytest tests/unit/core/capabilities/test_runner.py -v

# Integration
pytest tests/unit/core/capabilities/test_integration.py -v
```

## Extending

### Adding a Custom Executor

```python
from agentos.core.capabilities.executors import BaseExecutor
from agentos.core.capabilities.models import ExecutionResult

class MyCustomExecutor(BaseExecutor):
    def supports_runner(self, runner: str) -> bool:
        return runner.startswith("custom.")

    def execute(self, route, context):
        # Your custom logic here
        return ExecutionResult(
            success=True,
            output="Custom result",
            metadata={}
        )

# Register with runner
runner = CapabilityRunner()
runner.register_executor("custom", MyCustomExecutor())
```

### Adding a Custom Runner Type

In your extension's `commands.yaml`:
```yaml
actions:
  - id: my_action
    description: My custom action
    runner: custom.my_runner
    args: []
```

Then implement the executor for `custom.my_runner`.

## Performance

### Response Store
- In-memory storage (fast)
- 1MB size limit per response
- 24-hour TTL
- Automatic cleanup of expired entries

### Tool Execution
- Minimal overhead (<10ms)
- Direct subprocess execution
- Efficient output capture
- Timeout prevents resource waste

### Benchmarks

```
Simple echo command: ~5-10ms
Complex tool (postman): ~100-500ms
LLM analysis: ~1-3 seconds
```

## Troubleshooting

### Tool not found
1. Check extension is installed
2. Verify tool exists in `.agentos/tools/`
3. Check file permissions (must be executable)

### Timeout errors
1. Increase timeout in context
2. Check command is not blocking on input
3. Verify network connectivity (if applicable)

### Security errors
1. Verify work directory path
2. Check directory exists and is writable
3. Ensure path is under allowed locations

## Related Components

- **Extension Registry** (PR-A): Manages installed extensions
- **Slash Command Router** (PR-D): Parses commands and creates routes
- **Install Engine** (PR-B): Installs extension tools
- **WebUI Extensions** (PR-C): Displays extension management UI
