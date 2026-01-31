"""
Action Domain Models for AgentOS v3

Data models for action execution, side effects tracking, rollback, and replay.

Design Principles:
1. All actions MUST be linked to a frozen decision_id
2. Side effects MUST be declared before execution
3. Evidence MUST be recorded for every execution
4. Rollback plans MUST be generated when possible
5. All data uses epoch_ms timestamps (ADR-011)

Risk Categories:
- LOCAL: File system operations, local commands
- REMOTE: SSH, API calls, external services
- EXTERNAL_API: Third-party API calls with rate limits
- CRITICAL: Irreversible operations (payments, deletions)
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from agentos.core.time import utc_now_ms


# ===================================================================
# Enums
# ===================================================================

class ActionExecutionStatus(str, Enum):
    """Status of action execution"""
    PENDING = "pending"       # Queued, not started
    RUNNING = "running"       # Currently executing
    SUCCESS = "success"       # Completed successfully
    FAILURE = "failure"       # Failed with error
    CANCELLED = "cancelled"   # Cancelled by user/system
    ROLLED_BACK = "rolled_back"  # Execution was rolled back


class SideEffectType(str, Enum):
    """
    Comprehensive side effect taxonomy.

    Based on Task #21 design and expanded for Action Domain.
    """
    # File System
    FS_READ = "fs.read"
    FS_WRITE = "fs.write"
    FS_DELETE = "fs.delete"
    FS_CHMOD = "fs.chmod"
    FS_MOVE = "fs.move"

    # Network
    NETWORK_HTTP = "network.http"
    NETWORK_HTTPS = "network.https"
    NETWORK_SOCKET = "network.socket"
    NETWORK_DNS = "network.dns"

    # Cloud Resources
    CLOUD_RESOURCE_CREATE = "cloud.resource_create"
    CLOUD_RESOURCE_DELETE = "cloud.resource_delete"
    CLOUD_RESOURCE_UPDATE = "cloud.resource_update"
    CLOUD_KEY_READ = "cloud.key_read"
    CLOUD_KEY_WRITE = "cloud.key_write"

    # Financial
    PAYMENT_CHARGE = "payment.charge"
    PAYMENT_REFUND = "payment.refund"
    PAYMENT_TRANSFER = "payment.transfer"

    # System
    SYSTEM_EXEC = "system.exec"
    SYSTEM_ENV_READ = "system.env.read"
    SYSTEM_ENV_WRITE = "system.env.write"
    PROCESS_SPAWN = "process.spawn"
    PROCESS_KILL = "process.kill"

    # Database
    DATABASE_READ = "database.read"
    DATABASE_WRITE = "database.write"
    DATABASE_DELETE = "database.delete"
    DATABASE_SCHEMA_CHANGE = "database.schema_change"

    # External Services
    EXTERNAL_API_CALL = "external.api_call"
    EXTERNAL_WEBHOOK = "external.webhook"
    RATE_LIMIT_CONSUMPTION = "rate_limit.consumption"

    # State Changes
    LOCAL_STATE_CHANGE = "state.local_change"
    REMOTE_STATE_CHANGE = "state.remote_change"
    PERSISTENT_STATE_MUTATION = "state.persistent_mutation"


class RiskLevel(str, Enum):
    """Risk level for actions"""
    LOW = "low"           # Read-only, safe operations
    MEDIUM = "medium"     # Limited side effects, reversible
    HIGH = "high"         # Significant side effects, partially reversible
    CRITICAL = "critical" # Irreversible, dangerous operations


class RollbackStatus(str, Enum):
    """Status of rollback operation"""
    NOT_APPLICABLE = "not_applicable"  # Action is irreversible
    PENDING = "pending"                # Rollback queued
    SUCCESS = "success"                # Rollback succeeded
    FAILURE = "failure"                # Rollback failed
    PARTIAL = "partial"                # Rollback partially succeeded


class ReplayMode(str, Enum):
    """Mode for replaying executions"""
    DRY_RUN = "dry_run"     # Simulate without side effects
    ACTUAL = "actual"       # Actually re-execute (requires ADMIN)
    COMPARE = "compare"     # Compare with original execution


# ===================================================================
# Side Effect Metadata
# ===================================================================

SIDE_EFFECT_METADATA: Dict[SideEffectType, Dict[str, Any]] = {
    # File System
    SideEffectType.FS_READ: {
        "risk": RiskLevel.LOW,
        "reversible": True,
        "requires_approval": False,
    },
    SideEffectType.FS_WRITE: {
        "risk": RiskLevel.MEDIUM,
        "reversible": True,
        "requires_approval": False,
    },
    SideEffectType.FS_DELETE: {
        "risk": RiskLevel.HIGH,
        "reversible": False,
        "requires_approval": True,
    },
    SideEffectType.FS_CHMOD: {
        "risk": RiskLevel.MEDIUM,
        "reversible": True,
        "requires_approval": False,
    },

    # Network
    SideEffectType.NETWORK_HTTP: {
        "risk": RiskLevel.MEDIUM,
        "reversible": False,
        "requires_approval": False,
    },
    SideEffectType.NETWORK_HTTPS: {
        "risk": RiskLevel.MEDIUM,
        "reversible": False,
        "requires_approval": False,
    },

    # Cloud
    SideEffectType.CLOUD_RESOURCE_CREATE: {
        "risk": RiskLevel.HIGH,
        "reversible": True,
        "requires_approval": True,
        "cost_implication": True,
    },
    SideEffectType.CLOUD_RESOURCE_DELETE: {
        "risk": RiskLevel.CRITICAL,
        "reversible": False,
        "requires_approval": True,
        "requires_confirmation": True,
    },

    # Financial
    SideEffectType.PAYMENT_CHARGE: {
        "risk": RiskLevel.CRITICAL,
        "reversible": False,
        "requires_approval": True,
        "requires_confirmation": True,
        "compliance": ["PCI-DSS", "SOX"],
    },
    SideEffectType.PAYMENT_REFUND: {
        "risk": RiskLevel.CRITICAL,
        "reversible": False,
        "requires_approval": True,
        "compliance": ["PCI-DSS"],
    },

    # System
    SideEffectType.SYSTEM_EXEC: {
        "risk": RiskLevel.HIGH,
        "reversible": False,
        "requires_approval": True,
    },
    SideEffectType.PROCESS_SPAWN: {
        "risk": RiskLevel.HIGH,
        "reversible": True,
        "requires_approval": False,
    },

    # Database
    SideEffectType.DATABASE_WRITE: {
        "risk": RiskLevel.MEDIUM,
        "reversible": True,
        "requires_approval": False,
    },
    SideEffectType.DATABASE_DELETE: {
        "risk": RiskLevel.HIGH,
        "reversible": False,
        "requires_approval": True,
    },
    SideEffectType.DATABASE_SCHEMA_CHANGE: {
        "risk": RiskLevel.CRITICAL,
        "reversible": False,
        "requires_approval": True,
        "requires_confirmation": True,
    },
}


def get_side_effect_risk(effect: SideEffectType) -> RiskLevel:
    """Get risk level for a side effect type"""
    metadata = SIDE_EFFECT_METADATA.get(effect, {})
    return metadata.get("risk", RiskLevel.MEDIUM)


def is_side_effect_reversible(effect: SideEffectType) -> bool:
    """Check if a side effect is reversible"""
    metadata = SIDE_EFFECT_METADATA.get(effect, {})
    return metadata.get("reversible", False)


# ===================================================================
# Action Execution Models
# ===================================================================

class ActionExecution(BaseModel):
    """
    Complete record of an action execution.

    MUST include:
    - decision_id: Link to frozen decision
    - declared_side_effects: What side effects were declared
    - actual_side_effects: What actually happened
    - evidence_id: Link to evidence record
    """
    execution_id: str = Field(
        description="Unique execution identifier (ulid)"
    )
    action_id: str = Field(
        description="Action capability ID (e.g., 'action.execute.local')"
    )
    params: Dict[str, Any] = Field(
        description="Action parameters"
    )
    decision_id: str = Field(
        description="Decision ID this action implements (MUST be frozen)"
    )
    agent_id: str = Field(
        description="Agent executing the action"
    )

    # Status tracking
    status: ActionExecutionStatus = Field(
        default=ActionExecutionStatus.PENDING,
        description="Execution status"
    )
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Execution result (if success)"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message (if failure)"
    )

    # Timing
    started_at_ms: int = Field(
        default_factory=utc_now_ms,
        description="Execution start time (epoch ms)"
    )
    completed_at_ms: Optional[int] = Field(
        default=None,
        description="Execution completion time (epoch ms)"
    )
    duration_ms: Optional[int] = Field(
        default=None,
        description="Execution duration in milliseconds"
    )

    # Side Effects
    declared_side_effects: List[SideEffectType] = Field(
        default_factory=list,
        description="Side effects declared before execution"
    )
    actual_side_effects: List[SideEffectType] = Field(
        default_factory=list,
        description="Side effects that actually occurred"
    )
    unexpected_side_effects: List[SideEffectType] = Field(
        default_factory=list,
        description="Side effects not declared (security risk)"
    )

    # Evidence & Rollback
    evidence_id: Optional[str] = Field(
        default=None,
        description="Evidence record ID"
    )
    rollback_plan: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Rollback plan (if reversible)"
    )
    is_reversible: bool = Field(
        default=False,
        description="Whether this action can be rolled back"
    )

    # Risk
    risk_level: RiskLevel = Field(
        default=RiskLevel.HIGH,
        description="Risk level of this action"
    )
    governance_approved: bool = Field(
        default=False,
        description="Whether governance approved this action"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


class SideEffectDeclaration(BaseModel):
    """
    Declaration of expected side effects before action execution.

    Used for comparison with actual side effects.
    """
    declaration_id: str = Field(
        description="Unique declaration ID (ulid)"
    )
    execution_id: str = Field(
        description="Associated execution ID"
    )
    action_id: str = Field(
        description="Action capability ID"
    )
    declared_effects: List[SideEffectType] = Field(
        description="Side effects this action will produce"
    )
    declared_at_ms: int = Field(
        default_factory=utc_now_ms,
        description="When declared (epoch ms)"
    )
    agent_id: str = Field(
        description="Agent making the declaration"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="Why these side effects are necessary"
    )


class ActionSideEffect(BaseModel):
    """
    Individual side effect record.

    Tracks each side effect that occurred during execution.
    """
    side_effect_id: int = Field(
        description="Auto-incremented ID"
    )
    execution_id: str = Field(
        description="Associated execution ID"
    )
    effect_type: SideEffectType = Field(
        description="Type of side effect"
    )
    was_declared: bool = Field(
        description="Whether this was declared beforehand"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Side effect details (e.g., file path, URL)"
    )
    timestamp_ms: int = Field(
        default_factory=utc_now_ms,
        description="When side effect occurred (epoch ms)"
    )
    severity: RiskLevel = Field(
        default=RiskLevel.MEDIUM,
        description="Severity of this side effect"
    )


class SideEffectComparison(BaseModel):
    """
    Comparison between declared and actual side effects.

    Critical for detecting unexpected behavior (security).
    """
    execution_id: str = Field(
        description="Associated execution ID"
    )
    declared_effects: List[SideEffectType] = Field(
        description="Effects that were declared"
    )
    actual_effects: List[SideEffectType] = Field(
        description="Effects that actually occurred"
    )
    expected_effects: List[SideEffectType] = Field(
        description="Effects that were both declared and occurred"
    )
    unexpected_effects: List[SideEffectType] = Field(
        description="Effects that occurred but weren't declared (ALERT!)"
    )
    missing_effects: List[SideEffectType] = Field(
        description="Effects that were declared but didn't occur"
    )
    is_compliant: bool = Field(
        description="Whether actual matches declared (no unexpected)"
    )
    compared_at_ms: int = Field(
        default_factory=utc_now_ms,
        description="When comparison was performed (epoch ms)"
    )


# ===================================================================
# Rollback Models
# ===================================================================

class RollbackPlan(BaseModel):
    """
    Plan for rolling back an action execution.

    Generated during execution planning phase.
    """
    plan_id: str = Field(
        description="Unique plan ID (ulid)"
    )
    execution_id: str = Field(
        description="Execution this plan can rollback"
    )
    rollback_action_id: str = Field(
        description="Action to execute for rollback"
    )
    rollback_params: Dict[str, Any] = Field(
        description="Parameters for rollback action"
    )
    is_full_rollback: bool = Field(
        default=True,
        description="Whether this is a complete rollback"
    )
    estimated_duration_ms: Optional[int] = Field(
        default=None,
        description="Estimated rollback time"
    )
    prerequisites: List[str] = Field(
        default_factory=list,
        description="Prerequisites for rollback (e.g., backup exists)"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings about rollback (e.g., data loss)"
    )
    created_at_ms: int = Field(
        default_factory=utc_now_ms,
        description="When plan was created (epoch ms)"
    )


class RollbackExecution(BaseModel):
    """
    Record of a rollback execution.

    Links original action to rollback action.
    """
    rollback_id: str = Field(
        description="Unique rollback ID (ulid)"
    )
    original_execution_id: str = Field(
        description="Original execution being rolled back"
    )
    rollback_execution_id: Optional[str] = Field(
        default=None,
        description="Execution ID of rollback action"
    )
    rollback_plan: RollbackPlan = Field(
        description="Rollback plan used"
    )
    status: RollbackStatus = Field(
        default=RollbackStatus.PENDING,
        description="Rollback status"
    )
    reason: str = Field(
        description="Why rollback was initiated"
    )
    initiated_by: str = Field(
        description="Agent/user who initiated rollback"
    )
    initiated_at_ms: int = Field(
        default_factory=utc_now_ms,
        description="When rollback started (epoch ms)"
    )
    completed_at_ms: Optional[int] = Field(
        default=None,
        description="When rollback completed (epoch ms)"
    )
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Rollback result"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message (if failure)"
    )


# ===================================================================
# Replay Models
# ===================================================================

class ReplayResult(BaseModel):
    """
    Result of replaying an action execution.

    Used for debugging and audit.
    """
    replay_id: str = Field(
        description="Unique replay ID (ulid)"
    )
    original_execution_id: str = Field(
        description="Original execution being replayed"
    )
    replay_mode: ReplayMode = Field(
        description="Replay mode (dry_run or actual)"
    )

    # Original execution data
    original_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Original execution result"
    )
    original_side_effects: List[SideEffectType] = Field(
        default_factory=list,
        description="Side effects from original execution"
    )

    # Replay execution data
    replay_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Replay execution result"
    )
    replay_side_effects: List[SideEffectType] = Field(
        default_factory=list,
        description="Side effects from replay"
    )

    # Comparison
    results_match: bool = Field(
        description="Whether results match"
    )
    differences: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Differences between original and replay"
    )

    # Metadata
    replayed_by: str = Field(
        description="Agent who initiated replay"
    )
    replayed_at_ms: int = Field(
        default_factory=utc_now_ms,
        description="When replay was performed (epoch ms)"
    )
    duration_ms: Optional[int] = Field(
        default=None,
        description="Replay duration"
    )


# ===================================================================
# Action Capability Definitions
# ===================================================================

class ActionCapabilityDefinition(BaseModel):
    """
    Definition for an Action capability.

    Extends base CapabilityDefinition with Action-specific fields.
    """
    capability_id: str = Field(
        description="Capability ID (e.g., 'action.execute.local')"
    )
    name: str = Field(
        description="Human-readable name"
    )
    description: str = Field(
        description="What this action does"
    )
    risk_level: RiskLevel = Field(
        description="Risk classification"
    )
    requires_frozen_decision: bool = Field(
        default=True,
        description="Whether this action requires a frozen decision"
    )
    produces_side_effects: List[SideEffectType] = Field(
        description="Side effects this action produces"
    )
    is_reversible: bool = Field(
        description="Whether this action can be rolled back"
    )
    rollback_strategy: Optional[str] = Field(
        default=None,
        description="Strategy for rollback (if reversible)"
    )
    requires_governance_approval: bool = Field(
        default=True,
        description="Whether governance approval is required"
    )
    timeout_ms: Optional[int] = Field(
        default=None,
        description="Execution timeout in milliseconds"
    )
    retry_policy: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Retry policy for transient failures"
    )


# ===================================================================
# Helper Functions
# ===================================================================

def compute_execution_duration(execution: ActionExecution) -> Optional[int]:
    """Compute execution duration in milliseconds"""
    if execution.completed_at_ms and execution.started_at_ms:
        return execution.completed_at_ms - execution.started_at_ms
    return None


def is_execution_complete(execution: ActionExecution) -> bool:
    """Check if execution is in a terminal state"""
    terminal_states = {
        ActionExecutionStatus.SUCCESS,
        ActionExecutionStatus.FAILURE,
        ActionExecutionStatus.CANCELLED,
        ActionExecutionStatus.ROLLED_BACK,
    }
    return execution.status in terminal_states


def calculate_risk_score(side_effects: List[SideEffectType]) -> float:
    """
    Calculate risk score based on side effects.

    Returns:
        Risk score from 0.0 (no risk) to 1.0 (maximum risk)
    """
    if not side_effects:
        return 0.0

    risk_weights = {
        RiskLevel.LOW: 0.1,
        RiskLevel.MEDIUM: 0.4,
        RiskLevel.HIGH: 0.7,
        RiskLevel.CRITICAL: 1.0,
    }

    total_score = 0.0
    for effect in side_effects:
        risk_level = get_side_effect_risk(effect)
        total_score += risk_weights.get(risk_level, 0.5)

    # Normalize to 0-1 range (assume max 5 critical side effects)
    max_score = 5.0
    return min(total_score / max_score, 1.0)
