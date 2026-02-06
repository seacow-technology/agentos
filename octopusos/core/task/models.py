"""Task data models"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# Import run_mode types for type hints
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentos.core.task.run_mode import TaskMetadata


@dataclass
class Task:
    """Task: Root aggregate for traceability"""

    task_id: str  # ULID
    title: str
    status: str = "created"  # Free-form: created/planning/executing/succeeded/failed/canceled/orphan/blocked
    session_id: Optional[str] = None
    project_id: Optional[str] = None  # FK to projects table (v0.26)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    exit_reason: Optional[str] = None  # done, max_iterations, blocked, fatal_error, user_cancelled, unknown (v0.28)

    # Router fields (PR-2: Chat→Task Router Integration)
    route_plan_json: Optional[str] = None  # JSON serialized RoutePlan
    requirements_json: Optional[str] = None  # JSON serialized TaskRequirements
    selected_instance_id: Optional[str] = None  # Selected provider instance ID
    router_version: Optional[str] = None  # Router version used

    # v0.4 Project-Aware fields (v0.31 migration)
    repo_id: Optional[str] = None  # FK to repos table
    workdir: Optional[str] = None  # Working directory path
    spec_frozen: int = 0  # Spec frozen flag (0=unfrozen, 1=frozen) - Task #4
    
    def is_orphan(self) -> bool:
        """Check if this is an orphan task"""
        return self.status == "orphan" or self.metadata.get("orphan", False)

    def is_spec_frozen(self) -> bool:
        """Check if task specification is frozen

        Task #4: Execution frozen plan validation
        Returns True if spec_frozen = 1, False otherwise
        """
        return self.spec_frozen == 1

    def get_run_mode(self) -> str:
        """Get run mode from metadata"""
        return self.metadata.get("run_mode", "assisted")
    
    def get_model_policy(self) -> Dict[str, str]:
        """Get model policy from metadata"""
        return self.metadata.get("model_policy", {})
    
    def get_current_stage(self) -> Optional[str]:
        """Get current stage from metadata"""
        return self.metadata.get("current_stage")
    
    def set_current_stage(self, stage: str) -> None:
        """Set current stage in metadata"""
        self.metadata["current_stage"] = stage

    def get_retry_config(self) -> "RetryConfig":
        """Get retry configuration from metadata"""
        from agentos.core.task.retry_strategy import RetryConfig

        retry_data = self.metadata.get("retry_config")
        if retry_data:
            return RetryConfig.from_dict(retry_data)
        else:
            # Return default config
            return RetryConfig()

    def get_retry_state(self) -> "RetryState":
        """Get retry state from metadata"""
        from agentos.core.task.retry_strategy import RetryState

        retry_state_data = self.metadata.get("retry_state")
        if retry_state_data:
            return RetryState.from_dict(retry_state_data)
        else:
            # Return initial state
            return RetryState()

    def update_retry_state(self, retry_state: "RetryState") -> None:
        """Update retry state in metadata"""
        self.metadata["retry_state"] = retry_state.to_dict()

    def get_timeout_config(self) -> "TimeoutConfig":
        """Get timeout configuration from metadata"""
        from agentos.core.task.timeout_manager import TimeoutConfig

        timeout_data = self.metadata.get("timeout_config")
        if timeout_data:
            return TimeoutConfig.from_dict(timeout_data)
        else:
            return TimeoutConfig()

    def get_timeout_state(self) -> "TimeoutState":
        """Get timeout state from metadata"""
        from agentos.core.task.timeout_manager import TimeoutState

        timeout_state_data = self.metadata.get("timeout_state")
        if timeout_state_data:
            return TimeoutState.from_dict(timeout_state_data)
        else:
            return TimeoutState()

    def update_timeout_state(self, timeout_state: "TimeoutState") -> None:
        """Update timeout state in metadata"""
        self.metadata["timeout_state"] = timeout_state.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "session_id": self.session_id,
            "project_id": self.project_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "metadata": self.metadata,
            "exit_reason": self.exit_reason,
            "spec_frozen": self.spec_frozen,  # Task #4: Include frozen status
        }
        # Add router fields if present
        if self.route_plan_json:
            result["route_plan_json"] = self.route_plan_json
        if self.requirements_json:
            result["requirements_json"] = self.requirements_json
        if self.selected_instance_id:
            result["selected_instance_id"] = self.selected_instance_id
        if self.router_version:
            result["router_version"] = self.router_version
        # Add v0.4 fields if present
        if self.repo_id:
            result["repo_id"] = self.repo_id
        if self.workdir:
            result["workdir"] = self.workdir
        return result


@dataclass
class TaskContext:
    """Task execution context (passed through pipeline)"""
    
    task_id: str
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }


@dataclass
class TaskLineageEntry:
    """Single lineage entry"""
    
    task_id: str
    kind: str  # nl_request|intent|coordinator_run|execution_request|commit|...
    ref_id: str
    phase: Optional[str] = None
    timestamp: Optional[str] = None  # Renamed from created_at for consistency
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Backward compatibility alias
    @property
    def created_at(self) -> Optional[str]:
        """Alias for timestamp (backward compatibility)"""
        return self.timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "kind": self.kind,
            "ref_id": self.ref_id,
            "phase": self.phase,
            "created_at": self.timestamp,  # Keep created_at in dict for DB compatibility
            "metadata": self.metadata,
        }


@dataclass
class TaskTrace:
    """Task trace: Shallow output by default, expandable on demand"""

    task: Task
    timeline: List[TaskLineageEntry]  # Sorted by created_at
    agents: List[Dict[str, Any]] = field(default_factory=list)
    audits: List[Dict[str, Any]] = field(default_factory=list)

    # Expanded content (lazy loaded)
    _expanded: Dict[str, Any] = field(default_factory=dict)

    def expand(self, kind: str) -> Optional[Any]:
        """Get expanded content for a specific kind (lazy loaded)"""
        return self._expanded.get(kind)

    def set_expanded(self, kind: str, content: Any) -> None:
        """Set expanded content for a kind"""
        self._expanded[kind] = content

    def get_refs_by_kind(self, kind: str) -> List[str]:
        """Get all ref_ids for a specific kind"""
        return [entry.ref_id for entry in self.timeline if entry.kind == kind]

    def get_latest_ref(self, kind: str) -> Optional[str]:
        """Get the latest ref_id for a specific kind"""
        refs = self.get_refs_by_kind(kind)
        return refs[-1] if refs else None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (shallow)"""
        return {
            "task": self.task.to_dict(),
            "timeline": [entry.to_dict() for entry in self.timeline],
            "agents": self.agents,
            "audits": self.audits,
        }


# ============================================
# Multi-Repo Task Models (v18)
# ============================================


class RepoScopeType(str, Enum):
    """Repository scope type enumeration"""

    FULL = "full"  # Full repository access
    PATHS = "paths"  # Limited to specific paths (via path_filters)
    READ_ONLY = "read_only"  # Read-only access


class DependencyType(str, Enum):
    """Task dependency type enumeration"""

    BLOCKS = "blocks"  # Blocking dependency (must wait for completion)
    REQUIRES = "requires"  # Required dependency (can run in parallel, needs artifacts)
    SUGGESTS = "suggests"  # Suggested dependency (weak, non-blocking)


class ArtifactRefType(str, Enum):
    """Artifact reference type enumeration"""

    COMMIT = "commit"  # Git commit SHA
    BRANCH = "branch"  # Git branch name
    PR = "pr"  # Pull Request number
    PATCH = "patch"  # Patch file path or content
    FILE = "file"  # File path
    TAG = "tag"  # Git tag


@dataclass
class TaskRepoScope:
    """Task repository scope

    Maps to task_repo_scope table in v18 schema.
    Defines which repositories a task can access and how.
    """

    scope_id: Optional[int] = None
    task_id: str = ""
    repo_id: str = ""
    scope: RepoScopeType = RepoScopeType.FULL
    path_filters: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "scope_id": self.scope_id,
            "task_id": self.task_id,
            "repo_id": self.repo_id,
            "scope": self.scope.value if isinstance(self.scope, RepoScopeType) else self.scope,
            "path_filters": json.dumps(self.path_filters) if self.path_filters else None,
            "created_at": self.created_at,
            "metadata": json.dumps(self.metadata) if self.metadata else None,
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "TaskRepoScope":
        """Create from database row"""
        path_filters_raw = row.get("path_filters")
        path_filters = json.loads(path_filters_raw) if path_filters_raw else []

        metadata_raw = row.get("metadata")
        metadata = json.loads(metadata_raw) if metadata_raw else {}

        return cls(
            scope_id=row.get("scope_id"),
            task_id=row["task_id"],
            repo_id=row["repo_id"],
            scope=RepoScopeType(row.get("scope", "full")),
            path_filters=path_filters,
            created_at=row.get("created_at"),
            metadata=metadata,
        )


@dataclass
class TaskDependency:
    """Task dependency relationship

    Maps to task_dependency table in v18 schema.
    Defines dependencies between tasks (including cross-repo dependencies).
    """

    dependency_id: Optional[int] = None
    task_id: str = ""
    depends_on_task_id: str = ""
    dependency_type: DependencyType = DependencyType.BLOCKS
    reason: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "dependency_id": self.dependency_id,
            "task_id": self.task_id,
            "depends_on_task_id": self.depends_on_task_id,
            "dependency_type": self.dependency_type.value if isinstance(self.dependency_type, DependencyType) else self.dependency_type,
            "reason": self.reason,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "metadata": json.dumps(self.metadata) if self.metadata else None,
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "TaskDependency":
        """Create from database row"""
        metadata_raw = row.get("metadata")
        metadata = json.loads(metadata_raw) if metadata_raw else {}

        return cls(
            dependency_id=row.get("dependency_id"),
            task_id=row["task_id"],
            depends_on_task_id=row["depends_on_task_id"],
            dependency_type=DependencyType(row.get("dependency_type", "blocks")),
            reason=row.get("reason"),
            created_at=row.get("created_at"),
            created_by=row.get("created_by"),
            metadata=metadata,
        )


@dataclass
class TaskArtifactRef:
    """Task artifact reference

    Maps to task_artifact_ref table in v18 schema.
    Records cross-repo artifact references (commits, PRs, patches, files, etc.).
    """

    artifact_id: Optional[int] = None
    task_id: str = ""
    repo_id: str = ""
    ref_type: ArtifactRefType = ArtifactRefType.COMMIT
    ref_value: str = ""
    summary: Optional[str] = None
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "artifact_id": self.artifact_id,
            "task_id": self.task_id,
            "repo_id": self.repo_id,
            "ref_type": self.ref_type.value if isinstance(self.ref_type, ArtifactRefType) else self.ref_type,
            "ref_value": self.ref_value,
            "summary": self.summary,
            "created_at": self.created_at,
            "metadata": json.dumps(self.metadata) if self.metadata else None,
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "TaskArtifactRef":
        """Create from database row"""
        metadata_raw = row.get("metadata")
        metadata = json.loads(metadata_raw) if metadata_raw else {}

        return cls(
            artifact_id=row.get("artifact_id"),
            task_id=row["task_id"],
            repo_id=row["repo_id"],
            ref_type=ArtifactRefType(row.get("ref_type", "commit")),
            ref_value=row["ref_value"],
            summary=row.get("summary"),
            created_at=row.get("created_at"),
            metadata=metadata,
        )


# ============================================
# Task Template Models (v26)
# ============================================


@dataclass
class TaskTemplate:
    """Task template for saving and reusing task configurations

    Maps to task_templates table in v26 schema.
    Allows users to save common task configurations as templates.
    """

    template_id: str
    name: str  # 1-100 characters
    title_template: str
    description: Optional[str] = None
    created_by_default: Optional[str] = None
    metadata_template: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    use_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "title_template": self.title_template,
            "created_by_default": self.created_by_default,
            "metadata_template": self.metadata_template,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "use_count": self.use_count,
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "TaskTemplate":
        """Create from database row"""
        metadata_raw = row.get("metadata_template_json")
        metadata = json.loads(metadata_raw) if metadata_raw else {}

        return cls(
            template_id=row["template_id"],
            name=row["name"],
            description=row.get("description"),
            title_template=row["title_template"],
            created_by_default=row.get("created_by_default"),
            metadata_template=metadata,
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            created_by=row.get("created_by"),
            use_count=row.get("use_count", 0),
        )
