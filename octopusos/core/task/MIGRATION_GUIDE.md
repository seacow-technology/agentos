# Task State Machine Migration Guide

**Task #3: S3 - Enforce State Machine at core/task API**

This guide explains how to migrate existing code to use the new `TaskService` layer that enforces state machine transitions.

## Overview

All task status changes MUST now go through `TaskStateMachine.transition()` via the `TaskService` layer. Direct status updates are deprecated and will be removed in a future version.

## Key Changes

### 1. Task Creation

**❌ Old Way (Deprecated):**
```python
from agentos.core.task import TaskManager

manager = TaskManager()
task = manager.create_task(title="My Task")  # Creates with status="created"
manager.update_task_status(task.task_id, "approved")  # Direct update
```

**✅ New Way:**
```python
from agentos.core.task.service import TaskService

service = TaskService()
# All tasks start as DRAFT
task = service.create_draft_task(title="My Task", created_by="user")
# Use state machine for transitions
task = service.approve_task(task.task_id, actor="approver", reason="Looks good")
```

### 2. Task Approval

**❌ Old Way (Deprecated):**
```python
manager.update_task_status(task_id, "approved")
```

**✅ New Way:**
```python
task = service.approve_task(
    task_id=task_id,
    actor="approver_name",
    reason="Task approved for execution"
)
```

### 3. Task Execution Lifecycle

**❌ Old Way (Deprecated):**
```python
# Direct status updates
manager.update_task_status(task_id, "queued")
manager.update_task_status(task_id, "running")
manager.update_task_status(task_id, "succeeded")
```

**✅ New Way:**
```python
# Use state machine methods
task = service.queue_task(task_id, actor="scheduler", reason="Ready for execution")
task = service.start_task(task_id, actor="runner", reason="Starting execution")
task = service.complete_task_execution(task_id, actor="runner", reason="Execution completed")
task = service.verify_task(task_id, actor="verifier", reason="Verification passed")
task = service.mark_task_done(task_id, actor="user", reason="Task completed successfully")
```

### 4. Task Failure

**❌ Old Way (Deprecated):**
```python
manager.update_task_status(task_id, "failed")
```

**✅ New Way:**
```python
task = service.fail_task(
    task_id=task_id,
    actor="runner",
    reason="Execution error: connection timeout",
    metadata={"error_code": "TIMEOUT", "retry_count": 3}
)
```

### 5. Task Cancellation

**❌ Old Way (Deprecated):**
```python
manager.update_task_status(task_id, "canceled")
```

**✅ New Way:**
```python
task = service.cancel_task(
    task_id=task_id,
    actor="user",
    reason="Task no longer needed"
)
```

### 6. Task Retry

**❌ Old Way (Deprecated):**
```python
# Manually change failed task back to queued
manager.update_task_status(task_id, "queued")
```

**✅ New Way:**
```python
task = service.retry_failed_task(
    task_id=task_id,
    actor="user",
    reason="Fixed underlying issue, retrying"
)
```

## State Transition Rules

### Valid Transitions

```
DRAFT → APPROVED → QUEUED → RUNNING → VERIFYING → VERIFIED → DONE
                                  ↓           ↓
                               FAILED     FAILED
                                  ↓
                               QUEUED (retry)

DRAFT/APPROVED/QUEUED/RUNNING/VERIFYING → CANCELED
```

### Invalid Transitions

Any transition not listed above will raise `InvalidTransitionError`:

```python
from agentos.core.task.errors import InvalidTransitionError

try:
    # This will fail: DRAFT cannot go directly to RUNNING
    service.start_task(task_id, actor="runner", reason="Starting")
except InvalidTransitionError as e:
    print(f"Invalid transition: {e}")
    # Output: "Invalid transition from 'draft' to 'running': No transition rule defined"
```

## Migration Strategy

### Phase 1: Add TaskService Alongside Existing Code

1. Import `TaskService` in your modules
2. Use `TaskService` for new code
3. Keep existing `TaskManager.update_task_status()` calls for backward compatibility

```python
from agentos.core.task import TaskManager
from agentos.core.task.service import TaskService

# Old code still works (with deprecation warning)
manager = TaskManager()
manager.update_task_status(task_id, "running")  # ⚠️ Deprecated

# New code uses TaskService
service = TaskService()
service.start_task(task_id, actor="runner", reason="Starting")  # ✅ Recommended
```

### Phase 2: Migrate Existing Code Gradually

Identify all places where task status is modified:

```bash
# Find all direct status updates
grep -r "update_task_status" agentos/
grep -r "UPDATE tasks SET status" agentos/
```

Replace them with appropriate `TaskService` methods.

### Phase 3: Add Deprecation Warnings

Add deprecation warnings to `TaskManager.update_task_status()`:

```python
import warnings

def update_task_status(self, task_id: str, status: str) -> None:
    warnings.warn(
        "TaskManager.update_task_status() is deprecated. "
        "Use TaskService methods for state transitions.",
        DeprecationWarning,
        stacklevel=2
    )
    # ... existing implementation
```

### Phase 4: Remove Direct Status Updates

Once all code is migrated:
1. Remove `TaskManager.update_task_status()`
2. Make all status updates raise errors
3. Update documentation

## Code Locations to Update

### High Priority (Core Execution Paths)

1. **Task Runner** (`agentos/core/runner/task_runner.py`)
   - Lines 132, 166, 181, 290: Replace `update_task_status()` with `TaskService` methods

2. **CLI Task Commands** (`agentos/cli/task.py`)
   - Line 290: Replace `update_task_status()` with `TaskService.queue_task()` or similar

3. **Chat Handler** (`agentos/core/chat/handlers/task_handler.py`)
   - Task creation already correct (creates with status), but should use `TaskService.create_draft_task()`

4. **Interactive CLI** (`agentos/cli/interactive.py`)
   - Task creation should use `TaskService.create_draft_task()`

5. **Executor Engine** (`agentos/core/executor/executor_engine.py`)
   - Any status updates should use `TaskService` methods

### Medium Priority (Support Systems)

6. **Supervisor Policies** (`agentos/core/supervisor/policies/`)
   - Update any policy that modifies task status

7. **Mode Pipeline Runner** (`agentos/core/mode/pipeline_runner.py`)
   - Replace any direct status updates with `TaskService` methods

8. **WebUI APIs** (`agentos/webui/api/tasks.py`)
   - Currently read-only, but may need approval endpoint

### Low Priority (Test Code)

9. **Test Files** (`tests/`)
   - Update tests to use new `TaskService` API
   - Tests are allowed to use direct DB access for setup

## Benefits

1. **State Machine Enforcement**: Invalid transitions are caught immediately
2. **Audit Trail**: All transitions are automatically logged with actor/reason
3. **Type Safety**: Clear API for each business operation
4. **Testability**: Easy to mock and test state transitions
5. **Documentation**: Self-documenting API (method names describe operations)

## Error Handling

### Handling Invalid Transitions

```python
from agentos.core.task.errors import InvalidTransitionError

try:
    service.start_task(task_id, actor="runner", reason="Starting")
except InvalidTransitionError as e:
    logger.error(f"Cannot start task {task_id}: {e}")
    # Handle error appropriately
    # e.from_state and e.to_state contain the attempted transition
```

### Checking Valid Transitions

```python
# Get list of valid next states
valid_transitions = service.get_valid_transitions(task_id)

if "running" in valid_transitions:
    service.start_task(task_id, actor="runner", reason="Starting")
else:
    logger.warning(f"Task {task_id} cannot be started from current state")
```

## Testing

### Unit Tests

See `tests/unit/task/test_task_api_enforces_state_machine.py` for comprehensive test coverage.

### Integration Tests

When writing integration tests:

```python
from agentos.core.task.service import TaskService

def test_full_task_execution(tmp_path):
    service = TaskService(db_path=tmp_path / "test.db")

    # Create task
    task = service.create_draft_task(title="Test", created_by="test")

    # Full lifecycle
    task = service.approve_task(task.task_id, "approver", "Approved")
    task = service.queue_task(task.task_id, "scheduler", "Queued")
    task = service.start_task(task.task_id, "runner", "Running")
    task = service.complete_task_execution(task.task_id, "runner", "Done")
    task = service.verify_task(task.task_id, "verifier", "Verified")
    task = service.mark_task_done(task.task_id, "user", "Complete")

    assert task.status == "done"
```

## FAQs

### Q: Can I still use TaskManager for queries?

**A:** Yes! `TaskManager` is still used for queries (get_task, list_tasks, etc.). Only status updates need to go through `TaskService`.

### Q: What if I need to bypass the state machine for testing?

**A:** For tests, you can directly insert into the database. For production code, you MUST use `TaskService`.

### Q: How do I handle "orphan" tasks?

**A:** Orphan tasks should be created with `create_draft_task()` and marked with special metadata:

```python
task = service.create_draft_task(
    title=f"Orphan: {ref_id}",
    created_by="system",
    metadata={"orphan": True, "trigger_ref": ref_id}
)
```

### Q: Can I extend the state machine with custom states?

**A:** Not currently. Custom states require modifying `agentos/core/task/states.py` and the transition table in `state_machine.py`.

### Q: What about backward compatibility?

**A:** The old `TaskManager.update_task_status()` will remain for one release cycle with deprecation warnings, then be removed.

## Support

For questions or issues:
1. Check this migration guide
2. See unit tests for examples
3. Consult the task state machine documentation
4. Open an issue with the "task-state-machine" label
