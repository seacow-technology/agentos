"""
Decision Capabilities Domain for AgentOS v3

This is the core domain that differentiates AgentOS from other systems.

Five Capabilities Implemented:
1. DC-001: decision.plan.create - Create execution plans
2. DC-002: decision.plan.freeze - Freeze plans (make immutable)
3. DC-003: decision.option.evaluate - Evaluate and rank options
4. DC-004: decision.judge.select - Select option with rationale
5. DC-005: decision.record.rationale - Record detailed rationale

Core Design Principles (ADR-013):
- Decision CANNOT directly trigger Action (PathValidator enforces)
- All Plans must be freezable (semantic freeze)
- Frozen Plans generate SHA-256 hash for verification
- All Decisions must record rationale and evidence
- Plans must be based on frozen context snapshots

Usage:
    from agentos.core.capability.domains.decision import (
        get_plan_service,
        get_option_evaluator,
        get_decision_judge,
    )

    # Create and freeze plan
    plan_service = get_plan_service()
    plan = plan_service.create_plan(...)
    frozen_plan = plan_service.freeze_plan(plan.plan_id)

    # Evaluate options
    evaluator = get_option_evaluator()
    result = evaluator.evaluate_options(...)

    # Make final decision
    judge = get_decision_judge()
    decision = judge.select_option(result, decided_by="agent-1")
"""

from agentos.core.capability.domains.decision.models import (
    # Enums
    PlanStatus,
    ConfidenceLevel,
    DecisionType,

    # Models
    Plan,
    PlanStep,
    Alternative,
    Option,
    EvaluationResult,
    SelectedDecision,
    DecisionRationale,

    # Exceptions
    ImmutablePlanError,
    InvalidPlanHashError,
    PlanNotFrozenError,
    DecisionContextNotFrozenError,
)

from agentos.core.capability.domains.decision.plan_service import (
    PlanService,
    get_plan_service,
)

from agentos.core.capability.domains.decision.option_evaluator import (
    OptionEvaluator,
    get_option_evaluator,
)

from agentos.core.capability.domains.decision.judge import (
    DecisionJudge,
    get_decision_judge,
)


__all__ = [
    # Enums
    "PlanStatus",
    "ConfidenceLevel",
    "DecisionType",

    # Models
    "Plan",
    "PlanStep",
    "Alternative",
    "Option",
    "EvaluationResult",
    "SelectedDecision",
    "DecisionRationale",

    # Exceptions
    "ImmutablePlanError",
    "InvalidPlanHashError",
    "PlanNotFrozenError",
    "DecisionContextNotFrozenError",

    # Services
    "PlanService",
    "get_plan_service",
    "OptionEvaluator",
    "get_option_evaluator",
    "DecisionJudge",
    "get_decision_judge",
]
