# Task Router - Capability-Driven Instance Selection

## Overview

The Task Router is a core component of AgentOS that intelligently selects provider instances for task execution based on capability requirements, with full explainability and auditability.

**PR-1: Router Core Implementation**

## Key Features

- **Capability-Driven**: Routes tasks based on extracted requirements (coding, frontend, data, etc.)
- **Explainable**: Every routing decision includes detailed reasoning
- **Auditable**: All routing events are logged and can be traced
- **Failover Support**: Automatic fallback to alternative instances
- **Manual Override**: Users can override routing decisions
- **Persistent**: Routes are saved to database for traceability

## Architecture

```
TaskSpec → Requirements → Profiles → Scoring → RoutePlan
            Extractor      Builder    Engine
```

### Core Components

1. **RequirementsExtractor**: Extracts capability needs from task specification
2. **InstanceProfileBuilder**: Builds capability profiles from ProviderRegistry
3. **RouteScorer**: Scores instances against requirements
4. **Router**: Main orchestrator that ties everything together
5. **RouterPersistence**: Database operations for route plans
6. **RouterEvents**: Event emission for auditability

## Usage

### Basic Routing

```python
from agentos.router import Router

router = Router()

task_spec = {
    "task_id": "task_001",
    "title": "Implement authentication API",
    "description": "Create REST API with FastAPI",
}

route_plan = await router.route(
    task_id=task_spec["task_id"],
    task_spec=task_spec,
)

print(f"Selected: {route_plan.selected}")
print(f"Reasons: {route_plan.reasons}")
```

### Route Verification (Before Execution)

```python
# Verify route is still valid before execution
updated_plan, reroute_event = await router.verify_or_reroute(
    task_id="task_001",
    current_plan=route_plan,
)

if reroute_event:
    print(f"Rerouted: {reroute_event.reason_code}")
```

### Manual Override

```python
# User manually selects a different instance
overridden_plan = router.override_route(
    task_id="task_001",
    current_plan=route_plan,
    new_instance_id="llamacpp:qwen3-coder-30b",
)
```

### Persistence

```python
from agentos.router import RouterPersistence

persistence = RouterPersistence()

# Save route plan
persistence.save_route_plan(route_plan)

# Load route plan
loaded_plan = persistence.load_route_plan("task_001")

# Get routing stats
stats = persistence.get_routing_stats()
print(f"Total routed: {stats['total_routed']}")
```

### Event Emission

```python
from agentos.router import router_events

# Emit routing event
router_events.emit_task_routed(route_plan)

# Emit reroute event
router_events.emit_task_rerouted(reroute_event)

# Emit override event
router_events.emit_task_route_overridden(
    task_id="task_001",
    from_instance="ollama:default",
    to_instance="llamacpp:qwen3-coder-30b",
    user="user123",
)
```

## Scoring Algorithm

The router uses a multi-factor scoring formula:

### Hard Constraints (Disqualifying)
- Instance must be in `READY` state
- Fingerprint must match (if available)

### Soft Scoring (0.0 - 1.0)
- **Base score**: 0.5
- **Tags match**: +0.2 per matched capability
- **Context window**: +0.1 if sufficient, -0.2 if insufficient
- **Latency**: +0.0 to +0.1 (lower is better)
- **Local preference**: +0.05 for local, -0.02 for cloud

## Requirements Extraction

The requirements extractor uses keyword-based rules to detect:

### Capabilities
- **coding**: "code", "implement", "refactor", "debug", "PR"
- **frontend**: "React", "Vue", "UI", "component", "HTML/CSS"
- **backend**: "API", "REST", "database", "SQL", "server"
- **data**: "data", "analysis", "pandas", "SQL", "ETL"
- **testing**: "test", "pytest", "jest", "QA", "coverage"
- **long_ctx**: "long", "multiple files", "summary", "entire"

### Preferences
- **local**: Default preference (unless cloud explicitly mentioned)
- **fast**: "quick", "urgent", "ASAP"
- **quality**: "production", "robust", "best practice"

## Database Schema

Router uses the following fields in the `tasks` table:

```sql
ALTER TABLE tasks ADD COLUMN route_plan_json TEXT;
ALTER TABLE tasks ADD COLUMN requirements_json TEXT;
ALTER TABLE tasks ADD COLUMN selected_instance_id TEXT;
ALTER TABLE tasks ADD COLUMN router_version TEXT;
```

Migration: `v12_task_routing.sql`

## Event Types

Router emits the following event types:

- `task.routed`: Task was initially routed
- `task.route_verified`: Route was verified as still valid
- `task.rerouted`: Task was rerouted to fallback instance
- `task.route_overridden`: User manually changed routing

## Example Output

```
Route Plan for Task task_001:
  Selected: llamacpp:qwen3-coder-30b (score: 0.92)
  Reasons: READY, tags_match=coding, ctx>=4096, latency_best, local_preferred
  Fallback: llamacpp:glm47flash-q8, ollama:default
  Requirements: needs=['coding', 'backend'], prefer=['local']
  Router: v1 @ 2026-01-28T01:30:00.000Z
```

## Running Examples

```bash
cd /Users/pangge/PycharmProjects/AgentOS
python -m agentos.router.example
```

## Integration Points

### PR-2: Chat → Task Router
- Chat creates TaskSpec → Router.route() → Save RoutePlan
- Display selected instance + reasons in UI

### PR-3: Runner Integration
- Runner loads RoutePlan → verify_or_reroute() → Execute
- Handle execution failures → reroute_on_failure()

## Testing

Key test scenarios:

1. **Multiple instances available**: Select best scoring instance
2. **Selected instance fails**: Reroute to fallback
3. **All instances fail**: Re-route from scratch
4. **Manual override**: Update route plan correctly
5. **No instances available**: Raise appropriate error

## Future Enhancements

- LLM-based requirements extraction (more sophisticated than keywords)
- Dynamic scoring weights based on historical performance
- Cost-aware routing (balance performance vs. cost)
- Multi-stage routing (different instances for different task phases)
- Learning from routing success/failure rates

## References

- Specification: `/Users/pangge/PycharmProjects/AgentOS/docs/todos/reouter.md`
- Provider Architecture: `/Users/pangge/PycharmProjects/AgentOS/agentos/providers/`
- Event System: `/Users/pangge/PycharmProjects/AgentOS/agentos/core/events/`
- Database Schema: `/Users/pangge/PycharmProjects/AgentOS/agentos/store/`
