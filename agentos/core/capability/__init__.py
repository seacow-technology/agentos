"""
AgentOS v3 Capability System

This module provides the core capability infrastructure for AgentOS v3:
- 27 atomic capabilities across 5 domains
- Golden Path enforcement (State→Decision→Governance→Action→Evidence)
- Permission checks with caching (< 10ms)
- Complete audit trail

Key Components:
1. CapabilityRegistry - Central capability management and grants
2. PathValidator - Golden Path validation engine
3. PreconditionChecker - Dependency and state precondition validation
4. SideEffectsTracker - Side effect recording and validation

Usage:
    from agentos.core.capability import (
        get_capability_registry,
        get_path_validator,
        get_precondition_checker,
        get_side_effects_tracker,
    )

    # Initialize registry
    registry = get_capability_registry()
    registry.load_definitions()  # Load all 27 capabilities

    # Grant capability to agent
    registry.grant_capability(
        agent_id="chat_agent",
        capability_id="state.memory.read",
        granted_by="system",
        reason="Chat agent needs to read memory"
    )

    # Check permission
    has_perm = registry.has_capability("chat_agent", "state.memory.read")

    # Enforce permission (raises PermissionDenied if not allowed)
    registry.check_capability(
        agent_id="chat_agent",
        capability_id="state.memory.read",
        operation="list_memories"
    )

    # Validate path
    validator = get_path_validator()
    validator.start_session("task-123")
    validator.validate_call(
        from_domain=CapabilityDomain.STATE,
        to_domain=CapabilityDomain.DECISION,
        agent_id="chat_agent",
        capability_id="decision.plan.create",
        operation="create_plan"
    )

    # Check preconditions
    checker = get_precondition_checker()
    checker.check_preconditions(
        agent_id="executor_agent",
        capability_id="action.execute",
        context={"plan_frozen": True}
    )

    # Track side effects
    tracker = get_side_effects_tracker()
    tracker.start_session("task-123")
    tracker.record_side_effect(
        capability_id="action.file.write",
        side_effect_type=SideEffectType.FILE_SYSTEM_WRITE,
        agent_id="executor_agent",
        operation="write_file"
    )
"""

# Models
from agentos.core.capability.models import (
    CapabilityDefinition,
    CapabilityDomain,
    CapabilityLevel,
    CapabilityGrant,
    CapabilityInvocation,
    RiskLevel,
    SideEffectType,
    CostModel,
    CallStackEntry,
    PathValidationResult,
    get_default_capabilities,
    validate_capability_definition,
)

# Registry
from agentos.core.capability.registry import (
    CapabilityRegistry,
    PermissionDenied,
    get_capability_registry,
)

# Path Validator
from agentos.core.capability.path_validator import (
    PathValidator,
    PathValidationError,
    get_path_validator,
    GOLDEN_PATH_RULES,
    FORBIDDEN_PATHS,
)

# Precondition Checker
from agentos.core.capability.precondition_checker import (
    PreconditionChecker,
    PreconditionError,
    get_precondition_checker,
)

# Side Effects Tracker
from agentos.core.capability.side_effects_tracker import (
    SideEffectsTracker,
    SideEffectRecord,
    SideEffectSummary,
    UnexpectedSideEffectError,
    get_side_effects_tracker,
)


__all__ = [
    # Models
    "CapabilityDefinition",
    "CapabilityDomain",
    "CapabilityLevel",
    "CapabilityGrant",
    "CapabilityInvocation",
    "RiskLevel",
    "SideEffectType",
    "CostModel",
    "CallStackEntry",
    "PathValidationResult",
    "get_default_capabilities",
    "validate_capability_definition",
    # Registry
    "CapabilityRegistry",
    "PermissionDenied",
    "get_capability_registry",
    # Path Validator
    "PathValidator",
    "PathValidationError",
    "get_path_validator",
    "GOLDEN_PATH_RULES",
    "FORBIDDEN_PATHS",
    # Precondition Checker
    "PreconditionChecker",
    "PreconditionError",
    "get_precondition_checker",
    # Side Effects Tracker
    "SideEffectsTracker",
    "SideEffectRecord",
    "SideEffectSummary",
    "UnexpectedSideEffectError",
    "get_side_effects_tracker",
]


# Version info
__version__ = "3.0.0"
__author__ = "AgentOS Team"
__description__ = "AgentOS v3 Capability System - 27 atomic capabilities with Golden Path enforcement"
