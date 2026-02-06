# Capability Runner Quick Start

## Installation

The Capability Runner is part of the core AgentOS system. No additional installation required.

## 5-Minute Tutorial

### 1. Execute a Command

```python
from agentos.core.capabilities import CapabilityRunner, CommandRoute, ExecutionContext
from pathlib import Path

# Create runner
runner = CapabilityRunner()

# Create route (normally from Slash Router)
route = CommandRoute(
    command_name="/postman",
    extension_id="tools.postman",
    action_id="get",
    runner="exec.postman_cli",
    args=["https://api.example.com"]
)

# Create context
context = ExecutionContext(
    session_id="my_session",
    user_id="user_123",
    extension_id="tools.postman",
    work_dir=Path(".agentos/extensions/tools.postman/work")
)

# Execute!
result = runner.execute(route, context)

print(f"Success: {result.success}")
print(f"Output: {result.output}")
```

### 2. Analyze a Response

```python
# First, run a command (as above)
# Then analyze it:

analyze_route = CommandRoute(
    command_name="/postman",
    extension_id="tools.postman",
    action_id="explain",
    runner="analyze.response",
    args=["last_response"]
)

result = runner.execute(analyze_route, context)
print(result.output)  # Analysis of the previous response
```

### 3. Handle Errors

```python
result = runner.execute(route, context)

if not result.success:
    print(f"Error: {result.error}")
    print(f"Duration: {result.duration_seconds}s")
```

## Common Patterns

### Pattern 1: Execute Tool with Flags

```python
route = CommandRoute(
    command_name="/test",
    extension_id="test.cli",
    action_id="list",
    runner="exec.ls",
    args=["/path/to/dir"],
    flags={
        "l": True,     # -l flag
        "a": True,     # -a flag
        "sort": "size" # --sort=size
    }
)
```

### Pattern 2: Check Tool Availability

```python
from agentos.core.capabilities.tool_executor import ToolExecutor

executor = ToolExecutor()

if executor.check_tool_exists("postman"):
    print("Postman is available")
else:
    print("Postman not found")
```

### Pattern 3: Store and Retrieve Responses

```python
from agentos.core.capabilities.response_store import get_response_store

store = get_response_store()

# Save
store.save("session_123", response_data)

# Retrieve
data = store.get("session_123")
```

### Pattern 4: Custom Executor

```python
from agentos.core.capabilities.executors import BaseExecutor
from agentos.core.capabilities.models import ExecutionResult

class MyExecutor(BaseExecutor):
    def supports_runner(self, runner: str) -> bool:
        return runner == "custom.my_runner"

    def execute(self, route, context):
        # Your custom logic
        return ExecutionResult(
            success=True,
            output="Custom result",
            metadata={}
        )

# Register
runner.register_executor("custom", MyExecutor())
```

## Runner Types

| Runner Type | Description | Example |
|------------|-------------|---------|
| `exec.<tool>` | Execute CLI tool | `exec.postman_cli` |
| `analyze.response` | Analyze with LLM | `analyze.response` |
| `analyze.schema` | Analyze schema | `analyze.schema` |

## Security Notes

- Commands run in isolated work directories
- Only whitelisted environment variables
- 5-minute default timeout
- Tools must be in `.agentos/tools/` or system PATH

## Error Types

| Exception | Meaning | Solution |
|-----------|---------|----------|
| `ToolNotFoundError` | Tool not installed | Install extension |
| `TimeoutError` | Command too slow | Increase timeout |
| `SecurityError` | Policy violation | Check work directory |
| `ExecutionError` | Other failure | Check logs |

## Configuration

### Timeout

```python
context = ExecutionContext(
    # ... other params ...
    timeout=600  # 10 minutes
)
```

### Environment Variables

```python
context = ExecutionContext(
    # ... other params ...
    env_whitelist=["PATH", "HOME", "MY_VAR"]
)
```

### Work Directory

```python
context = ExecutionContext(
    # ... other params ...
    work_dir=Path(".agentos/extensions/my.ext/work")
)
```

## Testing

Run tests:
```bash
pytest tests/unit/core/capabilities/ -v
```

Run demo:
```bash
python3 examples/capability_runner_demo.py
```

## Next Steps

1. Read the full [README.md](./README.md)
2. Check out the [demo script](../../examples/capability_runner_demo.py)
3. Look at [test examples](../../tests/unit/core/capabilities/)
4. Integrate with your chat handler

## Common Issues

### Issue: "Tool not found"
**Solution**: Ensure extension is installed and tool is in `.agentos/tools/`

### Issue: "Work directory not safe"
**Solution**: Use a directory under `.agentos/` or home directory

### Issue: "Command timeout"
**Solution**: Increase `timeout` parameter in context

### Issue: "No content to analyze"
**Solution**: Run a command first, or provide content in args

## Getting Help

- Read the [full documentation](./README.md)
- Check [implementation summary](../../../PR-E-CAPABILITY-RUNNER-SUMMARY.md)
- Look at [test cases](../../tests/unit/core/capabilities/)
- Run the [demo](../../examples/capability_runner_demo.py)
