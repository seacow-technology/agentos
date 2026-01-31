"""
Action Domain for AgentOS v3 Capability System

This domain handles HIGH RISK operations - actual execution of actions
that produce side effects in the real world.

Core Principles:
1. ALL actions require frozen decision_id (traceability)
2. Side effects must be declared upfront
3. Evidence recording is mandatory
4. Rollback capability when possible
5. Replay for debugging and audit

Components:
- ActionExecutor: Core action execution engine
- SideEffectsTracker: Track declared vs actual side effects
- RollbackEngine: Handle action rollback
- ReplayEngine: Replay historical executions

Risk Management:
- Risk Level: HIGH by default
- Requires: decision.plan.freeze + governance.policy.check
- Must produce: Evidence + Side Effect records
"""

from agentos.core.capability.domains.action.models import (
    ActionExecution,
    ActionExecutionStatus,
    SideEffectDeclaration,
    SideEffectComparison,
    RollbackPlan,
    RollbackStatus,
    ReplayMode,
    ReplayResult,
    ActionSideEffect,
)

from agentos.core.capability.domains.action.action_executor import (
    ActionExecutor,
    get_action_executor,
    MissingDecisionError,
    UnfrozenPlanError,
    MissingSideEffectsDeclarationError,
    EvidenceRecordingFailedError,
)

from agentos.core.capability.domains.action.side_effects_tracker import (
    ActionSideEffectsTracker,
    get_action_side_effects_tracker,
)

from agentos.core.capability.domains.action.rollback_engine import (
    RollbackEngine,
    get_rollback_engine,
    IrreversibleActionError,
    RollbackFailedError,
)

from agentos.core.capability.domains.action.replay_engine import (
    ReplayEngine,
    get_replay_engine,
    ReplayError,
    InsufficientPermissionsError,
)

__all__ = [
    # Models
    "ActionExecution",
    "ActionExecutionStatus",
    "SideEffectDeclaration",
    "SideEffectComparison",
    "RollbackPlan",
    "RollbackStatus",
    "ReplayMode",
    "ReplayResult",
    "ActionSideEffect",
    # Executors
    "ActionExecutor",
    "get_action_executor",
    "ActionSideEffectsTracker",
    "get_action_side_effects_tracker",
    "RollbackEngine",
    "get_rollback_engine",
    "ReplayEngine",
    "get_replay_engine",
    # Errors
    "MissingDecisionError",
    "UnfrozenPlanError",
    "MissingSideEffectsDeclarationError",
    "EvidenceRecordingFailedError",
    "IrreversibleActionError",
    "RollbackFailedError",
    "ReplayError",
    "InsufficientPermissionsError",
]
