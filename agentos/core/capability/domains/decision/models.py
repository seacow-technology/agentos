"""
Decision Domain Data Models for AgentOS v3

This module defines the core data models for Decision Capabilities:
- Plan: Execution plan with steps and alternatives
- Option: Decision option with cost/benefit analysis
- EvaluationResult: Multi-option evaluation and ranking
- SelectedDecision: Final decision with rationale

Key Design Principles (ADR-013):
1. All Decisions must be freezable (immutable after freeze)
2. Decisions CANNOT trigger Actions directly
3. All Decisions must record rationale and evidence
4. Frozen Plans generate hash for verification
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
import hashlib
import json


class PlanStatus(str, Enum):
    """
    Plan lifecycle states.

    State transitions:
    - draft: Initial state, can be modified
    - frozen: Immutable state, ready for execution
    - archived: Plan completed or superseded
    - rolled_back: Emergency rollback executed
    """
    DRAFT = "draft"
    FROZEN = "frozen"
    ARCHIVED = "archived"
    ROLLED_BACK = "rolled_back"


class ConfidenceLevel(str, Enum):
    """Decision confidence levels"""
    VERY_LOW = "very_low"      # < 40% confidence
    LOW = "low"                # 40-60% confidence
    MEDIUM = "medium"          # 60-80% confidence
    HIGH = "high"              # 80-95% confidence
    VERY_HIGH = "very_high"    # > 95% confidence


class DecisionType(str, Enum):
    """Types of decisions supported"""
    PLAN_CREATION = "plan_creation"
    OPTION_SELECTION = "option_selection"
    CLASSIFICATION = "classification"
    APPROVAL = "approval"
    RISK_ASSESSMENT = "risk_assessment"


class PlanStep(BaseModel):
    """
    A single step in an execution plan.

    Each step represents an atomic action that can be executed
    and verified independently.
    """
    step_id: str = Field(
        description="Unique step identifier (within plan)"
    )
    description: str = Field(
        description="What this step does"
    )
    action_type: str = Field(
        description="Type of action (e.g., 'file.write', 'network.call')"
    )
    requires_capabilities: List[str] = Field(
        default_factory=list,
        description="Required capabilities for this step"
    )
    depends_on: List[str] = Field(
        default_factory=list,
        description="List of step_ids this step depends on"
    )
    estimated_time_ms: Optional[int] = Field(
        default=None,
        description="Estimated execution time in milliseconds"
    )
    estimated_cost: Optional[float] = Field(
        default=None,
        description="Estimated cost (tokens/dollars)"
    )
    rollback_action: Optional[str] = Field(
        default=None,
        description="How to rollback this step if it fails"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional step metadata"
    )

    def to_hash_dict(self) -> Dict[str, Any]:
        """
        Convert to dict for hash computation (frozen plan verification).

        Only includes immutable fields that affect execution semantics.
        """
        return {
            "step_id": self.step_id,
            "description": self.description,
            "action_type": self.action_type,
            "depends_on": sorted(self.depends_on),
            "requires_capabilities": sorted(self.requires_capabilities),
        }


class Alternative(BaseModel):
    """
    Alternative plan or approach.

    Every plan should record alternatives that were considered
    but not chosen, with rationale for rejection.
    """
    alternative_id: str = Field(
        description="Unique alternative identifier"
    )
    description: str = Field(
        description="Description of this alternative"
    )
    pros: List[str] = Field(
        default_factory=list,
        description="Advantages of this alternative"
    )
    cons: List[str] = Field(
        default_factory=list,
        description="Disadvantages of this alternative"
    )
    rejection_reason: str = Field(
        description="Why this alternative was not chosen"
    )
    estimated_cost: Optional[float] = Field(
        default=None,
        description="Estimated cost if chosen"
    )


class Plan(BaseModel):
    """
    Execution plan with freeze capability.

    Lifecycle:
    1. Created in DRAFT state (can be modified)
    2. Frozen to FROZEN state (immutable, hash generated)
    3. Eventually ARCHIVED or ROLLED_BACK

    Design Philosophy (ADR-004):
    - Semantic freeze: Once frozen, no modifications allowed
    - Hash verification: plan_hash ensures integrity
    - Alternatives: Must record rejected alternatives
    - Rationale: Must explain why this plan was chosen
    """
    plan_id: str = Field(
        description="Unique plan identifier (ulid)"
    )
    task_id: str = Field(
        description="Task this plan belongs to"
    )
    steps: List[PlanStep] = Field(
        description="Ordered list of execution steps"
    )
    alternatives: List[Alternative] = Field(
        default_factory=list,
        description="Alternative plans that were considered"
    )
    rationale: str = Field(
        description="Why this plan was chosen (human-readable)"
    )
    status: PlanStatus = Field(
        default=PlanStatus.DRAFT,
        description="Current plan status"
    )
    frozen_at_ms: Optional[int] = Field(
        default=None,
        description="When plan was frozen (epoch ms, None if not frozen)"
    )
    plan_hash: Optional[str] = Field(
        default=None,
        description="SHA-256 hash of frozen plan (for verification)"
    )
    created_by: str = Field(
        description="Agent/user who created this plan"
    )
    created_at_ms: int = Field(
        description="When plan was created (epoch ms)"
    )
    updated_at_ms: Optional[int] = Field(
        default=None,
        description="When plan was last updated (epoch ms)"
    )
    context_snapshot_id: Optional[str] = Field(
        default=None,
        description="Context snapshot this plan was based on"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional plan metadata"
    )

    def compute_hash(self) -> str:
        """
        Compute SHA-256 hash of plan for freeze verification.

        Only includes semantically significant fields:
        - plan_id
        - task_id
        - steps (hash representation)
        - created_by
        - created_at_ms

        Returns:
            SHA-256 hex digest
        """
        hash_data = {
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "steps": [step.to_hash_dict() for step in self.steps],
            "created_by": self.created_by,
            "created_at_ms": self.created_at_ms,
        }

        # Sort keys for consistent hashing
        hash_json = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_json.encode()).hexdigest()

    def verify_hash(self, expected_hash: str) -> bool:
        """
        Verify that plan hash matches expected value.

        Used by Executor to ensure plan hasn't been tampered with.

        Args:
            expected_hash: Expected SHA-256 hash

        Returns:
            True if hash matches, False otherwise
        """
        return self.compute_hash() == expected_hash

    def is_frozen(self) -> bool:
        """Check if plan is frozen (immutable)"""
        return self.status == PlanStatus.FROZEN


class Option(BaseModel):
    """
    Decision option with cost/benefit analysis.

    Used in multi-option evaluation (e.g., choosing classifier,
    selecting implementation approach, etc.)
    """
    option_id: str = Field(
        description="Unique option identifier"
    )
    description: str = Field(
        description="What this option does"
    )
    estimated_cost: float = Field(
        description="Estimated cost (tokens/dollars)"
    )
    estimated_time_ms: int = Field(
        description="Estimated execution time in milliseconds"
    )
    risks: List[str] = Field(
        default_factory=list,
        description="Potential risks of this option"
    )
    benefits: List[str] = Field(
        default_factory=list,
        description="Benefits of this option"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional option metadata"
    )


class EvaluationResult(BaseModel):
    """
    Result of multi-option evaluation.

    This is pure decision output - no actions are triggered.
    Governance or human must select from these options.
    """
    evaluation_id: str = Field(
        description="Unique evaluation identifier (ulid)"
    )
    decision_context_id: str = Field(
        description="Context this evaluation was performed in"
    )
    options: List[Option] = Field(
        description="Options that were evaluated"
    )
    scores: Dict[str, float] = Field(
        description="Scores for each option (option_id -> score 0-100)"
    )
    ranked_options: List[str] = Field(
        description="Option IDs ranked from best to worst"
    )
    recommendation: str = Field(
        description="Recommended option_id (top ranked)"
    )
    recommendation_rationale: str = Field(
        default="",
        description="Why this option is recommended"
    )
    confidence: float = Field(
        description="Confidence in evaluation (0-100)"
    )
    evaluated_by: str = Field(
        description="Agent/classifier that performed evaluation"
    )
    evaluated_at_ms: int = Field(
        description="When evaluation was performed (epoch ms)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional evaluation metadata"
    )

    def get_top_option(self) -> Optional[str]:
        """Get the top-ranked option ID"""
        return self.ranked_options[0] if self.ranked_options else None

    def get_option_by_id(self, option_id: str) -> Optional[Option]:
        """Get option by ID"""
        for opt in self.options:
            if opt.option_id == option_id:
                return opt
        return None


class SelectedDecision(BaseModel):
    """
    Final decision selection with rationale.

    This is the output of decision.judge.select capability.
    Records:
    - Which option was selected
    - Why it was selected (rationale)
    - Which alternatives were rejected (and why)
    - Evidence ID for audit trail
    """
    decision_id: str = Field(
        description="Unique decision identifier (ulid)"
    )
    evaluation_id: str = Field(
        description="Evaluation this decision is based on"
    )
    selected_option: Option = Field(
        description="Option that was selected"
    )
    rationale: str = Field(
        description="Detailed rationale for selection"
    )
    alternatives_rejected: List[Option] = Field(
        default_factory=list,
        description="Options that were not selected"
    )
    rejection_reasons: Dict[str, str] = Field(
        default_factory=dict,
        description="Why each alternative was rejected (option_id -> reason)"
    )
    confidence_level: ConfidenceLevel = Field(
        description="Confidence in this decision"
    )
    decided_by: str = Field(
        description="Who made this decision (agent/user)"
    )
    decided_at_ms: int = Field(
        description="When decision was made (epoch ms)"
    )
    evidence_id: Optional[str] = Field(
        default=None,
        description="Evidence record ID (for audit trail)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional decision metadata"
    )


class DecisionRationale(BaseModel):
    """
    Detailed rationale for a decision.

    This is stored separately to support rich rationale documentation
    with evidence references.
    """
    rationale_id: str = Field(
        description="Unique rationale identifier (ulid)"
    )
    decision_id: str = Field(
        description="Decision this rationale belongs to"
    )
    rationale: str = Field(
        description="Detailed explanation of decision"
    )
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="Evidence IDs supporting this rationale"
    )
    created_by: str = Field(
        description="Who created this rationale"
    )
    created_at_ms: int = Field(
        description="When rationale was created (epoch ms)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


class ImmutablePlanError(Exception):
    """
    Raised when attempting to modify a frozen plan.

    Frozen plans are immutable (ADR-004 semantic freeze).
    """
    def __init__(self, plan_id: str, message: str = "Cannot modify frozen plan"):
        self.plan_id = plan_id
        super().__init__(f"{message}: {plan_id}")


class InvalidPlanHashError(Exception):
    """
    Raised when plan hash verification fails.

    This indicates potential tampering or corruption.
    """
    def __init__(self, plan_id: str, expected: str, actual: str):
        self.plan_id = plan_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Plan hash mismatch for {plan_id}: expected {expected}, got {actual}"
        )


class PlanNotFrozenError(Exception):
    """
    Raised when attempting operation that requires frozen plan.

    Example: Executor cannot execute a DRAFT plan.
    """
    def __init__(self, plan_id: str, message: str = "Plan must be frozen first"):
        self.plan_id = plan_id
        super().__init__(f"{message}: {plan_id}")


class DecisionContextNotFrozenError(Exception):
    """
    Raised when creating plan without frozen context.

    Per ADR-004, decisions must be based on frozen context snapshots.
    """
    def __init__(self, message: str = "Decision requires frozen context snapshot"):
        super().__init__(message)
