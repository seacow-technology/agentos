"""Task-Driven Architecture: Task as the root aggregate for full traceability"""

from agentos.core.task.models import Task, TaskContext, TaskTrace, TaskLineageEntry
from agentos.core.task.manager import TaskManager
from agentos.core.task.trace_builder import TraceBuilder
from agentos.core.task.run_mode import RunMode, ModelPolicy, TaskMetadata
from agentos.core.task.service import TaskService
from agentos.core.task.state_machine import TaskStateMachine
from agentos.core.task.states import TaskState
from agentos.core.task.errors import (
    TaskStateError,
    InvalidTransitionError,
    TaskNotFoundError,
    TaskAlreadyInStateError,
)
from agentos.core.task.rollback import TaskRollbackService, RollbackNotAllowedError
from agentos.core.task.repo_context import (
    TaskRepoContext,
    ExecutionEnv,
    PathSecurityError,
)
from agentos.core.task.task_repo_service import TaskRepoService, build_repo_contexts

__all__ = [
    # Models
    "Task",
    "TaskContext",
    "TaskTrace",
    "TaskLineageEntry",
    # Managers
    "TaskManager",
    "TraceBuilder",
    # State Machine
    "TaskService",
    "TaskStateMachine",
    "TaskState",
    # Rollback
    "TaskRollbackService",
    "RollbackNotAllowedError",
    # Errors
    "TaskStateError",
    "InvalidTransitionError",
    "TaskNotFoundError",
    "TaskAlreadyInStateError",
    # Run Mode
    "RunMode",
    "ModelPolicy",
    "TaskMetadata",
    # Multi-Repo Support (Phase 5.1)
    "TaskRepoContext",
    "ExecutionEnv",
    "PathSecurityError",
    "TaskRepoService",
    "build_repo_contexts",
]
