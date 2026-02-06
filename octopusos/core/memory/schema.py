"""
Memory schemas for InfoNeed judgment history storage.

This module defines the data models for storing InfoNeed classification judgments
in MemoryOS, implementing the short-term memory subsystem.

Key Principle: Store HOW we judged, not WHAT we remembered
- ✅ Store: Question → Classification → Decision Basis → Outcome
- ❌ Don't store: External facts, content summaries, semantic analysis
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator
import hashlib


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class ConfidenceLevel(str, Enum):
    """LLM self-assessed confidence level."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class InfoNeedType(str, Enum):
    """Classification of question types based on information requirements."""
    LOCAL_DETERMINISTIC = "local_deterministic"
    LOCAL_KNOWLEDGE = "local_knowledge"
    AMBIENT_STATE = "ambient_state"
    EXTERNAL_FACT_UNCERTAIN = "external_fact_uncertain"
    OPINION = "opinion"


class DecisionAction(str, Enum):
    """Final decision action for responding to user query."""
    DIRECT_ANSWER = "direct_answer"
    LOCAL_CAPABILITY = "local_capability"
    REQUIRE_COMM = "require_comm"
    SUGGEST_COMM = "suggest_comm"


class JudgmentOutcome(str, Enum):
    """Outcome of the judgment (user feedback)."""
    USER_PROCEEDED = "user_proceeded"  # User accepted the decision and proceeded
    USER_DECLINED = "user_declined"  # User rejected the decision
    SYSTEM_FALLBACK = "system_fallback"  # System fallback due to error
    PENDING = "pending"  # No outcome yet


class InfoNeedJudgment(BaseModel):
    """
    InfoNeed judgment record (short-term memory).

    This model stores the judgment history of InfoNeed classifications,
    enabling pattern recognition and system evolution.

    Design Principle:
    - Store the judgment process, not the content
    - Store metadata and signals, not semantics
    - Store outcomes for feedback loop
    """

    # Identifiers
    judgment_id: str = Field(
        description="Unique judgment identifier (UUID)"
    )
    timestamp: datetime = Field(
        default_factory=utc_now,
        description="Timestamp when judgment was made"
    )
    session_id: str = Field(
        description="Session ID this judgment belongs to"
    )
    message_id: str = Field(
        description="Message ID for correlation with audit logs"
    )

    # Input
    question_text: str = Field(
        description="Original user question (for deduplication and analysis)"
    )
    question_hash: str = Field(
        description="Hash of question text for deduplication"
    )

    # Judgment process
    classified_type: InfoNeedType = Field(
        description="Classified information need type"
    )
    confidence_level: ConfidenceLevel = Field(
        description="Overall confidence in classification"
    )
    decision_action: DecisionAction = Field(
        description="Final decision action recommended"
    )

    # Judgment basis (metadata, not semantics)
    rule_signals: Dict[str, Any] = Field(
        default_factory=dict,
        description="Rule-based matching signals and patterns"
    )
    llm_confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="LLM confidence score (0-1)"
    )
    decision_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Decision latency in milliseconds"
    )

    # Outcome feedback
    outcome: JudgmentOutcome = Field(
        default=JudgmentOutcome.PENDING,
        description="Outcome of the judgment"
    )
    user_action: Optional[str] = Field(
        default=None,
        description="Specific user action taken (if any)"
    )
    outcome_timestamp: Optional[datetime] = Field(
        default=None,
        description="Timestamp when outcome was recorded"
    )

    # Context metadata
    phase: str = Field(
        description="Phase when judgment was made (planning/execution)"
    )
    mode: Optional[str] = Field(
        default=None,
        description="Mode when judgment was made (conversation/task/automation)"
    )
    trust_tier: Optional[str] = Field(
        default=None,
        description="Trust tier if external info was accessed"
    )

    @field_validator('llm_confidence_score')
    @classmethod
    def validate_confidence_score(cls, v: float) -> float:
        """Ensure confidence score is within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("llm_confidence_score must be between 0.0 and 1.0")
        return v

    @classmethod
    def create_question_hash(cls, question: str) -> str:
        """
        Create a hash of the question for deduplication.

        Args:
            question: Question text

        Returns:
            SHA256 hash (first 16 chars)
        """
        normalized = question.strip().lower()
        hash_obj = hashlib.sha256(normalized.encode('utf-8'))
        return hash_obj.hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "judgment_id": self.judgment_id,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "message_id": self.message_id,
            "question_text": self.question_text,
            "question_hash": self.question_hash,
            "classified_type": self.classified_type.value,
            "confidence_level": self.confidence_level.value,
            "decision_action": self.decision_action.value,
            "rule_signals": self.rule_signals,
            "llm_confidence_score": self.llm_confidence_score,
            "decision_latency_ms": self.decision_latency_ms,
            "outcome": self.outcome.value,
            "user_action": self.user_action,
            "outcome_timestamp": self.outcome_timestamp.isoformat() if self.outcome_timestamp else None,
            "phase": self.phase,
            "mode": self.mode,
            "trust_tier": self.trust_tier,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InfoNeedJudgment":
        """Deserialize from dictionary."""
        # Parse datetime fields
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if isinstance(data.get("outcome_timestamp"), str) and data["outcome_timestamp"]:
            data["outcome_timestamp"] = datetime.fromisoformat(data["outcome_timestamp"])

        # Parse enum fields
        if isinstance(data.get("classified_type"), str):
            data["classified_type"] = InfoNeedType(data["classified_type"])
        if isinstance(data.get("confidence_level"), str):
            data["confidence_level"] = ConfidenceLevel(data["confidence_level"])
        if isinstance(data.get("decision_action"), str):
            data["decision_action"] = DecisionAction(data["decision_action"])
        if isinstance(data.get("outcome"), str):
            data["outcome"] = JudgmentOutcome(data["outcome"])

        return cls(**data)


class JudgmentQuery(BaseModel):
    """Query parameters for searching judgment history."""

    session_id: Optional[str] = None
    classified_type: Optional[InfoNeedType] = None
    decision_action: Optional[DecisionAction] = None
    outcome: Optional[JudgmentOutcome] = None
    phase: Optional[str] = None
    mode: Optional[str] = None
    time_range_hours: int = Field(default=24, ge=1, le=720)  # Max 30 days
    limit: int = Field(default=100, ge=1, le=1000)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary, excluding None values."""
        result = {}
        if self.session_id:
            result["session_id"] = self.session_id
        if self.classified_type:
            result["classified_type"] = self.classified_type.value
        if self.decision_action:
            result["decision_action"] = self.decision_action.value
        if self.outcome:
            result["outcome"] = self.outcome.value
        if self.phase:
            result["phase"] = self.phase
        if self.mode:
            result["mode"] = self.mode
        result["time_range_hours"] = self.time_range_hours
        result["limit"] = self.limit
        return result
