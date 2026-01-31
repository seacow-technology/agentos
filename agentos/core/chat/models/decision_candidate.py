"""
DecisionCandidate Data Models for v3 Shadow Classifier System

This module implements the v3 core data structure for parallel decision-making:
- DecisionCandidate: Single decision (active or shadow)
- DecisionSet: Collection of active + shadow decisions
- ClassifierVersion: Versioning for classifier implementations

Key Constraints (Red Lines):
- Shadow decisions NEVER affect user behavior
- Shadow decisions NEVER trigger external operations
- Shadow decisions are ONLY for post-hoc comparison and learning
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from agentos.core.time import utc_now
from agentos.core.chat.models.info_need import (
    ClassificationResult,
    InfoNeedType,
    DecisionAction,
    ConfidenceLevel,
)


class DecisionRole(str, Enum):
    """Decision role in parallel decision-making.

    - ACTIVE: Actually executed decision (affects user)
    - SHADOW: Observation-only decision (never executed)
    """
    ACTIVE = "active"      # Actually executed decision
    SHADOW = "shadow"      # Shadow decision (observation only)


class ClassifierVersion(BaseModel):
    """Classifier version metadata.

    Tracks different implementations of the InfoNeed classifier,
    including experimental shadow versions.
    """
    version_id: str  # e.g., "v1", "v2-shadow-expand-keywords"
    version_type: str  # "active" | "shadow"
    change_description: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator('version_type')
    @classmethod
    def validate_version_type(cls, v: str) -> str:
        """Ensure version_type is valid."""
        if v not in ["active", "shadow"]:
            raise ValueError("version_type must be 'active' or 'shadow'")
        return v

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "version_id": self.version_id,
            "version_type": self.version_type,
            "change_description": self.change_description,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClassifierVersion":
        """Deserialize from dictionary."""
        return cls(
            version_id=data["version_id"],
            version_type=data["version_type"],
            change_description=data.get("change_description"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    @classmethod
    def create_active_v1(cls) -> "ClassifierVersion":
        """Create version metadata for active v1."""
        return cls(
            version_id="v1-active",
            version_type="active",
            change_description="Initial production classifier with rule-based and LLM confidence signals",
        )

    @classmethod
    def create_shadow(
        cls,
        version_id: str,
        change_description: str,
    ) -> "ClassifierVersion":
        """Create version metadata for a shadow classifier."""
        return cls(
            version_id=version_id,
            version_type="shadow",
            change_description=change_description,
        )


class DecisionCandidate(BaseModel):
    """Decision candidate (active or shadow).

    Represents a single classification decision with full context.
    Shadow candidates are never executed - they are observation-only.

    Key Constraints:
    - Shadow decisions do NOT trigger any operations
    - Shadow decisions do NOT affect user responses
    - Shadow decisions are ONLY for post-hoc evaluation

    Attributes:
        candidate_id: Unique identifier for this decision
        decision_role: ACTIVE (executed) or SHADOW (observation)
        classifier_version: Version of classifier that made this decision

        # Input (must be identical for active + shadow in same DecisionSet)
        question_text: Raw question text
        question_hash: Content hash for deduplication
        context: Additional context (phase, mode, session info)
        phase: Execution phase at time of decision
        mode: Conversation mode at time of decision

        # Classification output
        info_need_type: Classified information need type
        confidence_level: Overall confidence level
        decision_action: Recommended action
        reason_codes: List of reason codes for this decision

        # Signals (for post-hoc analysis)
        rule_signals: Rule-based matching signals (JSON)
        llm_confidence_score: LLM confidence score (0.0-1.0)

        # Metadata
        timestamp: When this decision was made
        message_id: Related message ID
        session_id: Related session ID

        # Shadow-specific
        shadow_metadata: Additional metadata for shadow decisions
    """
    # Basic info
    candidate_id: str = Field(default_factory=lambda: str(uuid4()))
    decision_role: DecisionRole
    classifier_version: ClassifierVersion

    # Input (must be identical across active + shadow)
    question_text: str
    question_hash: str
    context: Dict[str, Any] = Field(default_factory=dict)
    phase: str
    mode: Optional[str] = None

    # Classification result
    info_need_type: str  # InfoNeedType enum value
    confidence_level: str  # ConfidenceLevel enum value
    decision_action: str  # DecisionAction enum value
    reason_codes: List[str] = Field(default_factory=list)

    # Signals (for analysis)
    rule_signals: Dict[str, Any] = Field(default_factory=dict)
    llm_confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Time and relationships
    timestamp: datetime = Field(default_factory=utc_now)
    message_id: str
    session_id: str

    # Shadow-specific metadata
    shadow_metadata: Optional[Dict[str, Any]] = None

    # Legacy field for backward compatibility
    latency_ms: Optional[float] = Field(default=None, ge=0.0)

    @model_validator(mode='after')
    def validate_shadow_constraints(self) -> 'DecisionCandidate':
        """Validate shadow decision constraints."""
        # Ensure shadow decisions have shadow_metadata
        if self.decision_role == DecisionRole.SHADOW and self.shadow_metadata is None:
            self.shadow_metadata = {}

        # Ensure shadow metadata does NOT contain execution results
        if self.decision_role == DecisionRole.SHADOW and self.shadow_metadata:
            if "execution_result" in self.shadow_metadata:
                raise ValueError("Shadow decisions MUST NOT have execution results")

        return self

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            "candidate_id": self.candidate_id,
            "decision_role": self.decision_role.value,
            "classifier_version": self.classifier_version.to_dict(),
            "question_text": self.question_text,
            "question_hash": self.question_hash,
            "context": self.context,
            "phase": self.phase,
            "mode": self.mode,
            "info_need_type": self.info_need_type,
            "confidence_level": self.confidence_level,
            "decision_action": self.decision_action,
            "reason_codes": self.reason_codes,
            "rule_signals": self.rule_signals,
            "llm_confidence_score": self.llm_confidence_score,
            "timestamp": self.timestamp.isoformat(),
            "message_id": self.message_id,
            "session_id": self.session_id,
            "shadow_metadata": self.shadow_metadata,
        }
        if self.latency_ms is not None:
            result["latency_ms"] = self.latency_ms
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionCandidate":
        """Deserialize from dictionary."""
        return cls(
            candidate_id=data["candidate_id"],
            decision_role=DecisionRole(data["decision_role"]),
            classifier_version=ClassifierVersion.from_dict(data["classifier_version"]),
            question_text=data["question_text"],
            question_hash=data["question_hash"],
            context=data.get("context", {}),
            phase=data["phase"],
            mode=data.get("mode"),
            info_need_type=data["info_need_type"],
            confidence_level=data["confidence_level"],
            decision_action=data["decision_action"],
            reason_codes=data.get("reason_codes", []),
            rule_signals=data.get("rule_signals", {}),
            llm_confidence_score=data.get("llm_confidence_score"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            message_id=data["message_id"],
            session_id=data["session_id"],
            shadow_metadata=data.get("shadow_metadata"),
            latency_ms=data.get("latency_ms"),
        )

    # Legacy compatibility methods
    def get_info_need_type(self) -> str:
        """Get the classified information need type (legacy compatibility)."""
        return self.info_need_type

    def get_decision_action(self) -> str:
        """Get the recommended decision action (legacy compatibility)."""
        return self.decision_action

    def get_confidence_level(self) -> str:
        """Get the confidence level (legacy compatibility)."""
        return self.confidence_level


class DecisionSet(BaseModel):
    """Decision set: active + shadow decisions for a single question.

    A DecisionSet contains:
    - Exactly 1 active decision (actually executed)
    - 0-N shadow decisions (observation-only)

    All decisions in a set share:
    - Same question_text and question_hash
    - Same input context
    - Same timestamp (same moment in time)

    Differences:
    - Different classifier versions
    - Potentially different classification results
    - Potentially different decision actions

    Attributes:
        decision_set_id: Unique identifier for this set
        message_id: Related message ID
        session_id: Related session ID
        question_text: Original question text
        question_hash: Content hash of question
        active_decision: The decision that was actually executed
        shadow_decisions: List of shadow decisions (observation-only)
        timestamp: When this decision set was created
        context_snapshot: Snapshot of context at decision time
    """
    decision_set_id: str = Field(default_factory=lambda: str(uuid4()))
    message_id: str
    session_id: str
    question_text: str
    question_hash: str

    # Decisions
    active_decision: DecisionCandidate
    shadow_decisions: List[DecisionCandidate] = Field(default_factory=list)

    # Metadata
    timestamp: datetime = Field(default_factory=utc_now)
    context_snapshot: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('active_decision')
    @classmethod
    def validate_active_decision(cls, v: DecisionCandidate) -> DecisionCandidate:
        """Ensure active_decision is actually ACTIVE role."""
        if v.decision_role != DecisionRole.ACTIVE:
            raise ValueError("active_decision must have ACTIVE role")
        return v

    @field_validator('shadow_decisions')
    @classmethod
    def validate_shadow_decisions(cls, v: List[DecisionCandidate]) -> List[DecisionCandidate]:
        """Ensure all shadow_decisions have SHADOW role."""
        for decision in v:
            if decision.decision_role != DecisionRole.SHADOW:
                raise ValueError("All shadow_decisions must have SHADOW role")
        return v

    def get_decision_by_role(self, role: DecisionRole) -> Optional[DecisionCandidate]:
        """Get decision by role.

        Args:
            role: DecisionRole to find

        Returns:
            DecisionCandidate if found, None otherwise
        """
        if role == DecisionRole.ACTIVE:
            return self.active_decision
        # Return first shadow decision (multiple shadow decisions would need version_id)
        return next((d for d in self.shadow_decisions), None)

    def get_shadow_by_version(self, version_id: str) -> Optional[DecisionCandidate]:
        """Get shadow decision by version ID.

        Args:
            version_id: Classifier version ID to find

        Returns:
            DecisionCandidate if found, None otherwise
        """
        return next(
            (d for d in self.shadow_decisions if d.classifier_version.version_id == version_id),
            None
        )

    def has_shadow_decisions(self) -> bool:
        """Check if this set has any shadow decisions."""
        return len(self.shadow_decisions) > 0

    def count_shadow_decisions(self) -> int:
        """Count shadow decisions in this set."""
        return len(self.shadow_decisions)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "decision_set_id": self.decision_set_id,
            "message_id": self.message_id,
            "session_id": self.session_id,
            "question_text": self.question_text,
            "question_hash": self.question_hash,
            "active_decision": self.active_decision.to_dict(),
            "shadow_decisions": [d.to_dict() for d in self.shadow_decisions],
            "timestamp": self.timestamp.isoformat(),
            "context_snapshot": self.context_snapshot,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionSet":
        """Deserialize from dictionary."""
        return cls(
            decision_set_id=data["decision_set_id"],
            message_id=data["message_id"],
            session_id=data["session_id"],
            question_text=data["question_text"],
            question_hash=data["question_hash"],
            active_decision=DecisionCandidate.from_dict(data["active_decision"]),
            shadow_decisions=[
                DecisionCandidate.from_dict(d) for d in data.get("shadow_decisions", [])
            ],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            context_snapshot=data.get("context_snapshot", {}),
        )


def validate_shadow_isolation(decision_set: DecisionSet) -> None:
    """Validate shadow decision isolation constraints.

    Ensures shadow decisions comply with red-line constraints:
    - Must have SHADOW role
    - Must have shadow_metadata
    - Must NOT have execution results

    Args:
        decision_set: DecisionSet to validate

    Raises:
        AssertionError: If any shadow constraint is violated
    """
    for shadow in decision_set.shadow_decisions:
        # Must be SHADOW role
        assert shadow.decision_role == DecisionRole.SHADOW, \
            f"Shadow decision {shadow.candidate_id} has non-SHADOW role"

        # Must have shadow_metadata
        assert shadow.shadow_metadata is not None, \
            f"Shadow decision {shadow.candidate_id} missing shadow_metadata"

        # Must NOT have execution result
        assert "execution_result" not in shadow.shadow_metadata, \
            f"Shadow decision {shadow.candidate_id} MUST NOT have execution_result"
