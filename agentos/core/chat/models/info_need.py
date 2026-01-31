"""
InfoNeedClassifier Data Models

This module defines the complete data model for classifying user information needs
and determining appropriate response strategies.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from agentos.core.time import utc_now



class InfoNeedType(str, Enum):
    """Classification of question types based on information requirements."""

    LOCAL_DETERMINISTIC = "local_deterministic"  # Code structure, API existence
    LOCAL_KNOWLEDGE = "local_knowledge"  # Best practices, documentation
    AMBIENT_STATE = "ambient_state"  # System state, runtime info
    EXTERNAL_FACT_UNCERTAIN = "external_fact_uncertain"  # Time-sensitive facts
    OPINION = "opinion"  # Subjective judgments, recommendations


class ConfidenceLevel(str, Enum):
    """LLM self-assessed confidence level."""

    HIGH = "high"  # Strong confidence in answer accuracy
    MEDIUM = "medium"  # Moderate confidence, some uncertainty
    LOW = "low"  # Low confidence, likely outdated or uncertain


class DecisionAction(str, Enum):
    """Final decision action for responding to user query."""

    DIRECT_ANSWER = "direct_answer"  # Answer directly from LLM knowledge
    LOCAL_CAPABILITY = "local_capability"  # Use local tools (file read, grep, etc.)
    REQUIRE_COMM = "require_comm"  # Must use communication capability
    SUGGEST_COMM = "suggest_comm"  # Suggest but not require communication


class ClassificationSignal(BaseModel):
    """Rule-based matching signals for classification."""

    has_time_sensitive_keywords: bool = Field(
        default=False,
        description="Question contains time-sensitive keywords (latest, current, now, etc.)"
    )
    has_authoritative_keywords: bool = Field(
        default=False,
        description="Question requires authoritative source (official, standard, compliance, etc.)"
    )
    has_ambient_state_keywords: bool = Field(
        default=False,
        description="Question about system state (status, running, active, etc.)"
    )
    matched_keywords: List[str] = Field(
        default_factory=list,
        description="List of matched keywords that triggered signals"
    )
    signal_strength: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall signal strength (0.0 - 1.0)"
    )

    @field_validator('signal_strength')
    @classmethod
    def validate_signal_strength(cls, v: float) -> float:
        """Ensure signal strength is within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("signal_strength must be between 0.0 and 1.0")
        return v

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "has_time_sensitive_keywords": self.has_time_sensitive_keywords,
            "has_authoritative_keywords": self.has_authoritative_keywords,
            "has_ambient_state_keywords": self.has_ambient_state_keywords,
            "matched_keywords": self.matched_keywords,
            "signal_strength": self.signal_strength,
        }


class LLMConfidenceResult(BaseModel):
    """LLM self-assessment confidence result."""

    confidence: ConfidenceLevel = Field(
        description="Self-assessed confidence level"
    )
    reason: str = Field(
        description="Primary reason for confidence level (time-sensitive / authoritative / stable)"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Optional detailed reasoning process"
    )

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Ensure reason is one of the expected values."""
        valid_reasons = {"time-sensitive", "authoritative", "stable", "uncertain", "outdated"}
        if v.lower() not in valid_reasons:
            # Allow custom reasons but warn in logs
            pass
        return v

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            "confidence": self.confidence.value,
            "reason": self.reason,
        }
        if self.reasoning:
            result["reasoning"] = self.reasoning
        return result


class ClassificationResult(BaseModel):
    """Final classification result with decision action."""

    info_need_type: InfoNeedType = Field(
        description="Classified information need type"
    )
    decision_action: DecisionAction = Field(
        description="Recommended action for handling this query"
    )
    confidence_level: ConfidenceLevel = Field(
        description="Overall confidence in the classification"
    )

    # Judgment basis
    rule_signals: ClassificationSignal = Field(
        description="Rule-based matching signals"
    )
    llm_confidence: Optional[LLMConfidenceResult] = Field(
        default=None,
        description="LLM self-assessment result (if applicable)"
    )

    # Metadata
    reasoning: str = Field(
        description="Human-readable explanation of the classification decision"
    )
    timestamp: datetime = Field(
        default_factory=utc_now,
        description="Timestamp when classification was performed"
    )
    message_id: Optional[str] = Field(
        default=None,
        description="Unique message ID for correlating with outcome events"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            "info_need_type": self.info_need_type.value,
            "decision_action": self.decision_action.value,
            "confidence_level": self.confidence_level.value,
            "rule_signals": self.rule_signals.to_dict(),
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.llm_confidence:
            result["llm_confidence"] = self.llm_confidence.to_dict()
        return result

    @classmethod
    def example_local_deterministic(cls) -> "ClassificationResult":
        """Example: Local deterministic question (code structure, API existence)."""
        return cls(
            info_need_type=InfoNeedType.LOCAL_DETERMINISTIC,
            decision_action=DecisionAction.LOCAL_CAPABILITY,
            confidence_level=ConfidenceLevel.HIGH,
            rule_signals=ClassificationSignal(
                has_time_sensitive_keywords=False,
                has_authoritative_keywords=False,
                has_ambient_state_keywords=False,
                matched_keywords=["function", "class", "exists"],
                signal_strength=0.9,
            ),
            llm_confidence=None,
            reasoning="Question about code structure can be answered using local file system tools",
            timestamp=utc_now(),
        )

    @classmethod
    def example_local_knowledge(cls) -> "ClassificationResult":
        """Example: Local knowledge question (best practices, documentation)."""
        return cls(
            info_need_type=InfoNeedType.LOCAL_KNOWLEDGE,
            decision_action=DecisionAction.DIRECT_ANSWER,
            confidence_level=ConfidenceLevel.HIGH,
            rule_signals=ClassificationSignal(
                has_time_sensitive_keywords=False,
                has_authoritative_keywords=False,
                has_ambient_state_keywords=False,
                matched_keywords=["best practice", "how to"],
                signal_strength=0.7,
            ),
            llm_confidence=LLMConfidenceResult(
                confidence=ConfidenceLevel.HIGH,
                reason="stable",
                reasoning="Question about established best practices in stable domain",
            ),
            reasoning="Question about best practices can be answered from LLM training data with high confidence",
            timestamp=utc_now(),
        )

    @classmethod
    def example_ambient_state(cls) -> "ClassificationResult":
        """Example: Ambient state question (system status, runtime info)."""
        return cls(
            info_need_type=InfoNeedType.AMBIENT_STATE,
            decision_action=DecisionAction.LOCAL_CAPABILITY,
            confidence_level=ConfidenceLevel.HIGH,
            rule_signals=ClassificationSignal(
                has_time_sensitive_keywords=True,
                has_authoritative_keywords=False,
                has_ambient_state_keywords=True,
                matched_keywords=["running", "status", "current"],
                signal_strength=0.95,
            ),
            llm_confidence=None,
            reasoning="Question about system state requires real-time information from local tools",
            timestamp=utc_now(),
        )

    @classmethod
    def example_external_fact_uncertain(cls) -> "ClassificationResult":
        """Example: External fact with uncertainty (time-sensitive, requires verification)."""
        return cls(
            info_need_type=InfoNeedType.EXTERNAL_FACT_UNCERTAIN,
            decision_action=DecisionAction.REQUIRE_COMM,
            confidence_level=ConfidenceLevel.LOW,
            rule_signals=ClassificationSignal(
                has_time_sensitive_keywords=True,
                has_authoritative_keywords=True,
                matched_keywords=["latest", "current", "official"],
                signal_strength=0.85,
            ),
            llm_confidence=LLMConfidenceResult(
                confidence=ConfidenceLevel.LOW,
                reason="time-sensitive",
                reasoning="Information may have changed since training cutoff",
            ),
            reasoning="Question requires up-to-date external information that LLM cannot reliably answer",
            timestamp=utc_now(),
        )

    @classmethod
    def example_opinion(cls) -> "ClassificationResult":
        """Example: Opinion question (subjective judgment, recommendation)."""
        return cls(
            info_need_type=InfoNeedType.OPINION,
            decision_action=DecisionAction.SUGGEST_COMM,
            confidence_level=ConfidenceLevel.MEDIUM,
            rule_signals=ClassificationSignal(
                has_time_sensitive_keywords=False,
                has_authoritative_keywords=True,
                matched_keywords=["recommend", "should", "better"],
                signal_strength=0.6,
            ),
            llm_confidence=LLMConfidenceResult(
                confidence=ConfidenceLevel.MEDIUM,
                reason="uncertain",
                reasoning="Opinion may benefit from external perspectives but can provide initial guidance",
            ),
            reasoning="Opinion question can be answered but external input may provide valuable perspective",
            timestamp=utc_now(),
        )


def get_decision_action(
    info_type: InfoNeedType,
    confidence: ConfidenceLevel
) -> DecisionAction:
    """
    Determine decision action based on information type and confidence level.

    Decision Matrix:
    - LOCAL_DETERMINISTIC -> LOCAL_CAPABILITY (always)
    - LOCAL_KNOWLEDGE + HIGH -> DIRECT_ANSWER
    - LOCAL_KNOWLEDGE + MEDIUM/LOW -> SUGGEST_COMM
    - AMBIENT_STATE -> LOCAL_CAPABILITY (always)
    - EXTERNAL_FACT_UNCERTAIN -> REQUIRE_COMM (always)
    - OPINION + HIGH/MEDIUM -> SUGGEST_COMM
    - OPINION + LOW -> REQUIRE_COMM

    Args:
        info_type: Classified information need type
        confidence: LLM confidence level

    Returns:
        Recommended decision action
    """
    # Local deterministic questions always use local capabilities
    if info_type == InfoNeedType.LOCAL_DETERMINISTIC:
        return DecisionAction.LOCAL_CAPABILITY

    # Local knowledge questions depend on confidence
    if info_type == InfoNeedType.LOCAL_KNOWLEDGE:
        if confidence == ConfidenceLevel.HIGH:
            return DecisionAction.DIRECT_ANSWER
        else:
            return DecisionAction.SUGGEST_COMM

    # Ambient state questions always use local capabilities
    if info_type == InfoNeedType.AMBIENT_STATE:
        return DecisionAction.LOCAL_CAPABILITY

    # External facts with uncertainty always require communication
    if info_type == InfoNeedType.EXTERNAL_FACT_UNCERTAIN:
        return DecisionAction.REQUIRE_COMM

    # Opinion questions suggest communication, require if low confidence
    if info_type == InfoNeedType.OPINION:
        if confidence == ConfidenceLevel.LOW:
            return DecisionAction.REQUIRE_COMM
        else:
            return DecisionAction.SUGGEST_COMM

    # Default fallback: suggest communication for safety
    return DecisionAction.SUGGEST_COMM


def create_classification_result(
    info_type: InfoNeedType,
    confidence: ConfidenceLevel,
    rule_signals: ClassificationSignal,
    reasoning: str,
    llm_confidence: Optional[LLMConfidenceResult] = None,
) -> ClassificationResult:
    """
    Factory function to create a ClassificationResult with automatic decision action.

    Args:
        info_type: Classified information need type
        confidence: Overall confidence level
        rule_signals: Rule-based matching signals
        reasoning: Human-readable explanation
        llm_confidence: Optional LLM self-assessment result

    Returns:
        Complete ClassificationResult instance
    """
    decision_action = get_decision_action(info_type, confidence)

    return ClassificationResult(
        info_need_type=info_type,
        decision_action=decision_action,
        confidence_level=confidence,
        rule_signals=rule_signals,
        llm_confidence=llm_confidence,
        reasoning=reasoning,
        timestamp=utc_now(),
    )
