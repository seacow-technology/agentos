# Task Dependency Service - Phase 5.3

## Overview

The Task Dependency Service provides automatic dependency detection, DAG management, and cycle prevention for tasks across multiple repositories. It's the core component of Phase 5.3: Cross-Repository Dependency Auto-Generation.

## Key Features

1. **Auto-Detect Dependencies**: Automatically discovers dependencies from:
   - Artifact references (commits, branches, patches)
   - File read/write operations
   - Cross-repository interactions

2. **DAG Management**: Build and query dependency graphs:
   - Topological sort for execution ordering
   - Ancestor/descendant queries
   - GraphViz DOT export for visualization

3. **Cycle Prevention**: Detect and prevent circular dependencies:
   - Pre-creation cycle check with `create_dependency_safe()`
   - Full graph cycle detection
   - Clear error messages

4. **Multiple Dependency Types**:
   - `BLOCKS`: Blocking dependency (must wait for completion)
   - `REQUIRES`: Required dependency (needs artifacts, can parallelize)
   - `SUGGESTS`: Suggested dependency (weak, informational)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TaskDependencyService                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────┐  ┌──────────────────────────┐   │
│  │  Dependency          │  │  Dependency              │   │
│  │  Detection           │  │  Graph (DAG)             │   │
│  │  ├─ Artifact Refs    │  │  ├─ Topological Sort    │   │
│  │  ├─ File Reads       │  │  ├─ Ancestors/Descendants│   │
│  │  └─ Audit Trail      │  │  ├─ Cycle Detection     │   │
│  │                      │  │  └─ GraphViz Export     │   │
│  └──────────────────────┘  └──────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Cycle Prevention                                     │  │
│  │  ├─ Pre-create check (create_dependency_safe)        │  │
│  │  ├─ DFS-based cycle detection                        │  │
│  │  └─ Clear error messages                             │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌────────────────┐  ┌──────────────────┐  ┌─────────────────┐
│ TaskArtifact   │  │ TaskAuditService │  │ task_dependency │
│ Service        │  │                  │  │ (SQLite table)  │
└────────────────┘  └──────────────────┘  └─────────────────┘
```

## Usage Examples

### 1. Automatic Dependency Detection

```python
from agentos.core.task.dependency_service import TaskDependencyService
from agentos.core.task.runner_integration import prepare_execution_env

# Initialize service
dep_service = TaskDependencyService(db)

# Prepare execution environment
exec_env = prepare_execution_env(task)

# Auto-detect dependencies
dependencies = dep_service.detect_dependencies(task, exec_env)

# Save dependencies (with cycle check)
for dep in dependencies:
    try:
        dep_service.create_dependency_safe(
            task.task_id,
            dep.depends_on_task_id,
            dep.dependency_type,
            dep.reason,
            created_by="auto_detect"
        )
    except CircularDependencyError as e:
        logger.warning(f"Skipped circular dependency: {e}")
```

### 2. Manual Dependency Creation

```python
# Create a blocking dependency
dep_service.create_dependency_safe(
    task_id="task-002",
    depends_on_task_id="task-001",
    dependency_type=DependencyType.BLOCKS,
    reason="Task 2 must wait for Task 1 to complete",
    created_by="manual"
)
```

### 3. Query Dependencies

```python
# Get direct dependencies
deps = dep_service.get_dependencies("task-002")

# Get reverse dependencies (who depends on this task)
reverse_deps = dep_service.get_reverse_dependencies("task-001")

# Build dependency graph
graph = dep_service.build_dependency_graph()

# Get all ancestors (transitive dependencies)
ancestors = graph.get_ancestors("task-003")

# Get all descendants (who depends on this recursively)
descendants = graph.get_descendants("task-001")
```

### 4. Topological Sort

```python
# Get execution order
graph = dep_service.build_dependency_graph()
execution_order = graph.topological_sort()

print(f"Execute tasks in order: {' -> '.join(execution_order)}")
```

### 5. Cycle Detection

```python
# Check for cycles
cycles = dep_service.detect_cycles()

if cycles:
    print(f"Found {len(cycles)} circular dependencies:")
    for cycle in cycles:
        print(f"  {' -> '.join(cycle)}")
else:
    print("No circular dependencies")
```

### 6. GraphViz Export

```python
# Export to DOT format
graph = dep_service.build_dependency_graph()
dot = graph.to_dot()

# Save to file
Path("deps.dot").write_text(dot)

# Render with GraphViz
# $ dot -Tpng deps.dot -o deps.png
```

## Dependency Detection Rules

### Rule 1: Artifact Reference Detection (Most Important)

**Trigger**: Task B references an artifact created by Task A

**Example**:
```python
# Task A creates commit
artifact_service.create_commit_ref(
    task_id="task-a",
    repo_id="backend",
    commit_hash="abc123",
)

# Task B references same commit
artifact_service.create_commit_ref(
    task_id="task-b",
    repo_id="backend",
    commit_hash="abc123",  # Same commit
)

# Result: task-b REQUIRES task-a
```

**Dependency Types by Artifact**:
- `COMMIT`, `PATCH`: → `REQUIRES` (strong dependency)
- `BRANCH`: → `SUGGESTS` (weak dependency, can change)
- `PR`, `FILE`, `TAG`: → `SUGGESTS`

### Rule 2: File Read Dependencies

**Trigger**: Task B reads a file that Task A modified

**Example**:
```python
# Task A writes file
audit_service.record_operation(
    task_id="task-a",
    operation="write",
    files_changed=["src/api.py"]
)

# Task B reads same file
audit_service.record_operation(
    task_id="task-b",
    operation="read",
    files_changed=["src/api.py"]
)

# Result: task-b SUGGESTS task-a
```

**Dependency Type**: `SUGGESTS` (weak, informational)

### Rule 3: Artifact Directory Detection

**Trigger**: Task reads `.agentos/artifacts/<task-id>.json`

**Example**:
```python
# Task B reads artifact file for Task A
artifact_path = Path(".agentos/artifacts/task-a.json")
if artifact_path.exists():
    # Dependency detected: task-b REQUIRES task-a
```

## CLI Commands

### Show Dependencies

```bash
# Show what a task depends on
agentos task dependencies show task-123

# Show who depends on a task (reverse)
agentos task dependencies show task-123 --reverse

# JSON output
agentos task dependencies show task-123 --format json
```

### Export Dependency Graph

```bash
# Export to DOT format (stdout)
agentos task dependencies graph

# Export to file
agentos task dependencies graph -o deps.dot

# Render with GraphViz
dot -Tpng deps.dot -o deps.png

# Export as JSON
agentos task dependencies graph --format json -o deps.json
```

### Check for Cycles

```bash
agentos task dependencies check-cycles
```

### Query Ancestors/Descendants

```bash
# Show all ancestors (transitive dependencies)
agentos task dependencies ancestors task-123

# Show all descendants (who depends on this)
agentos task dependencies descendants task-123
```

### Topological Sort

```bash
# Show execution order
agentos task dependencies topological-sort
```

### Manual Dependency Management

```bash
# Create dependency
agentos task dependencies create task-002 task-001 \
  --type requires \
  --reason "Task 2 needs output from Task 1" \
  --safe  # Check for cycles

# Delete dependency
agentos task dependencies delete task-002 task-001
agentos task dependencies delete task-002 task-001 --type requires
```

## Integration with TaskRunner

To integrate dependency detection into task execution, add this to `TaskRunner._execute_stage()`:

```python
from agentos.core.task.dependency_service import TaskDependencyService, CircularDependencyError
from agentos.core.task.runner_integration import prepare_execution_env

def _execute_stage(self, task: Task):
    # 1. Prepare execution environment
    exec_env = prepare_execution_env(task)

    # 2. Execute task logic
    result = self._run_task_logic(task, exec_env)

    # 3. Auto-detect dependencies
    dep_service = TaskDependencyService(self.db)
    dependencies = dep_service.detect_dependencies(task, exec_env)

    # 4. Save dependencies (with cycle check)
    for dep in dependencies:
        try:
            dep_service.create_dependency_safe(
                dep.task_id,
                dep.depends_on_task_id,
                dep.dependency_type,
                dep.reason,
                created_by="auto_detect"
            )
        except CircularDependencyError as e:
            logger.warning(f"Skipped circular dependency: {e}")

    return result
```

## Database Schema

The `task_dependency` table (from v18 schema):

```sql
CREATE TABLE task_dependency (
    dependency_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,                       -- Dependent task
    depends_on_task_id TEXT NOT NULL,            -- Dependency task
    dependency_type TEXT NOT NULL DEFAULT 'blocks',  -- blocks | requires | suggests
    reason TEXT,                                 -- Why this dependency exists
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,                             -- user/system/auto_detect
    metadata TEXT,                               -- JSON: additional info

    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (depends_on_task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,

    -- Constraints
    UNIQUE(task_id, depends_on_task_id, dependency_type),
    CHECK (task_id != depends_on_task_id),
    CHECK (dependency_type IN ('blocks', 'requires', 'suggests'))
);
```

## Dependency Types Explained

| Type       | Meaning                                  | Use Case                          |
|------------|------------------------------------------|-----------------------------------|
| `BLOCKS`   | Must wait for dependency to complete    | Sequential execution required     |
| `REQUIRES` | Needs artifacts, can parallelize        | Uses output but can start early   |
| `SUGGESTS` | Weak dependency, informational only     | Related but not critical          |

**Priority** (for deduplication): `BLOCKS` > `REQUIRES` > `SUGGESTS`

When multiple dependencies exist between the same task pair, only the strongest is kept.

## Cycle Detection Algorithm

The service uses DFS (Depth-First Search) with recursion stack to detect cycles:

```python
def find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """
    For each node:
      1. Mark as visited and add to recursion stack
      2. Visit all neighbors
      3. If neighbor is in recursion stack → cycle found
      4. Remove from recursion stack when done
    """
```

**Time Complexity**: O(V + E) where V = tasks, E = dependencies

## Performance Considerations

1. **Deduplication**: Only strongest dependency type is kept per task pair
2. **Indexes**: Optimized queries with database indexes on:
   - `task_id`
   - `depends_on_task_id`
   - `(depends_on_task_id, task_id)` for reverse queries

3. **Lazy Loading**: Graphs are built on-demand, not cached
4. **Batch Operations**: Detect all dependencies at once, then save in transaction

## Error Handling

### CircularDependencyError

Raised when adding a dependency would create a cycle:

```python
try:
    dep_service.create_dependency_safe(
        "task-a", "task-c", DependencyType.REQUIRES, "Would create cycle"
    )
except CircularDependencyError as e:
    # Handle error: log, skip, or retry with different type
    logger.error(f"Cannot create dependency: {e}")
```

### sqlite3.IntegrityError

Raised when constraints are violated:
- Duplicate dependency
- Self-dependency
- Invalid dependency type

## Testing

Run unit tests:

```bash
pytest tests/unit/task/test_dependency_service.py -v
```

Run integration tests:

```bash
pytest tests/integration/task/test_dependency_workflow.py -v
```

Run example:

```bash
python examples/dependency_detection_example.py
```

## Examples

See `/examples/dependency_detection_example.py` for a complete workflow demonstrating:
- Task execution with artifact creation
- Automatic dependency detection
- DAG analysis and visualization
- Topological sort
- GraphViz export

## Future Enhancements

1. **API Call Dependencies**: Detect when Task B calls APIs modified by Task A
2. **Conflict Resolution**: Automatic handling of conflicting dependencies
3. **Dependency Strength**: Numerical weights for priority scheduling
4. **Parallel Execution**: Use DAG to schedule parallel task execution
5. **Dependency Reasons**: AI-generated explanations for detected dependencies

## References

- **Schema**: `/agentos/store/migrations/v18_multi_repo_projects.sql`
- **Models**: `/agentos/core/task/models.py` (TaskDependency, DependencyType)
- **Artifact Service**: `/agentos/core/task/artifact_service.py`
- **Audit Service**: `/agentos/core/task/audit_service.py`
- **Runner Integration**: `/agentos/core/task/runner_integration.py`
