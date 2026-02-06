"""
InfoNeed Decision Pattern Models for BrainOS

This module defines the data models for storing InfoNeed decision patterns
in BrainOS knowledge graph (long-term memory).

Key Principle: Store HOW we judge, not WHAT we know
- ✅ Store: Decision patterns, rule effectiveness, confidence evolution
- ✅ Store: Question features → Classification type mappings
- ❌ Don't store: External facts, content, semantic summaries
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
import uuid
from agentos.core.time import utc_now



class PatternType(str, Enum):
    """Types of decision patterns."""
    QUESTION_KEYWORD_PATTERN = "question_keyword_pattern"  # Keyword-based patterns
    RULE_SIGNAL_PATTERN = "rule_signal_pattern"  # Signal-based patterns
    LLM_CONFIDENCE_PATTERN = "llm_confidence_pattern"  # LLM confidence patterns
    COMBINED_PATTERN = "combined_pattern"  # Combined patterns


class SignalType(str, Enum):
    """Types of decision signals."""
    KEYWORD = "keyword"  # Keyword match
    LENGTH = "length"  # Question length
    TENSE = "tense"  # Time tense
    INTERROGATIVE = "interrogative"  # Question type
    SENTIMENT = "sentiment"  # Sentiment indicator
    STRUCTURE = "structure"  # Code structure pattern


class EvolutionType(str, Enum):
    """Pattern evolution types."""
    REFINED = "refined"  # Adjusted feature weights
    SPLIT = "split"  # Split into sub-patterns
    MERGED = "merged"  # Merged from multiple patterns
    DEPRECATED = "deprecated"  # Pattern no longer effective


class InfoNeedPatternNode(BaseModel):
    """
    InfoNeed judgment pattern node in BrainOS.

    This represents a learned decision pattern extracted from MemoryOS
    judgment history. Patterns are long-term knowledge that help improve
    classification accuracy over time.
    """

    # Identifiers
    pattern_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique pattern identifier (UUID)"
    )
    pattern_type: PatternType = Field(
        description="Type of pattern"
    )

    # Pattern features (non-semantic)
    question_features: Dict[str, Any] = Field(
        default_factory=dict,
        description="Question features that define this pattern (keywords, length, structure)"
    )
    classification_type: str = Field(
        description="InfoNeedType this pattern maps to"
    )
    confidence_level: str = Field(
        description="ConfidenceLevel this pattern typically produces"
    )

    # Statistical data
    occurrence_count: int = Field(
        default=0,
        ge=0,
        description="Number of times this pattern has occurred"
    )
    success_count: int = Field(
        default=0,
        ge=0,
        description="Number of successful judgments (user didn't decline)"
    )
    failure_count: int = Field(
        default=0,
        ge=0,
        description="Number of failed judgments (user declined or system fallback)"
    )
    avg_confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Average LLM confidence score for this pattern"
    )
    avg_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Average decision latency in milliseconds"
    )

    # Effectiveness metrics
    success_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Success rate (success_count / occurrence_count)"
    )

    # Time metadata
    first_seen: datetime = Field(
        default_factory=utc_now,
        description="First time this pattern was observed"
    )
    last_seen: datetime = Field(
        default_factory=utc_now,
        description="Last time this pattern was observed"
    )
    last_updated: datetime = Field(
        default_factory=utc_now,
        description="Last time this pattern was updated"
    )

    # Version control
    pattern_version: int = Field(
        default=1,
        ge=1,
        description="Pattern evolution version"
    )

    @field_validator('avg_confidence_score')
    @classmethod
    def validate_confidence_score(cls, v: float) -> float:
        """Ensure confidence score is within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("avg_confidence_score must be between 0.0 and 1.0")
        return v

    @field_validator('success_rate')
    @classmethod
    def validate_success_rate(cls, v: float) -> float:
        """Ensure success rate is within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("success_rate must be between 0.0 and 1.0")
        return v

    def calculate_success_rate(self) -> float:
        """Calculate success rate from counts."""
        if self.occurrence_count == 0:
            return 0.0
        return self.success_count / self.occurrence_count

    def update_statistics(
        self,
        success: bool,
        confidence_score: float,
        latency_ms: float
    ) -> None:
        """
        Update pattern statistics with new judgment result.

        Args:
            success: Whether judgment was successful
            confidence_score: LLM confidence score
            latency_ms: Decision latency
        """
        self.occurrence_count += 1

        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

        # Update averages using incremental average formula
        n = self.occurrence_count
        self.avg_confidence_score = (
            (self.avg_confidence_score * (n - 1) + confidence_score) / n
        )
        self.avg_latency_ms = (
            (self.avg_latency_ms * (n - 1) + latency_ms) / n
        )

        # Recalculate success rate
        self.success_rate = self.calculate_success_rate()

        # Update timestamps
        self.last_seen = utc_now()
        self.last_updated = utc_now()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "question_features": self.question_features,
            "classification_type": self.classification_type,
            "confidence_level": self.confidence_level,
            "occurrence_count": self.occurrence_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "avg_confidence_score": self.avg_confidence_score,
            "avg_latency_ms": self.avg_latency_ms,
            "success_rate": self.success_rate,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "pattern_version": self.pattern_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InfoNeedPatternNode":
        """Deserialize from dictionary."""
        # Parse datetime fields
        if isinstance(data.get("first_seen"), str):
            data["first_seen"] = datetime.fromisoformat(data["first_seen"])
        if isinstance(data.get("last_seen"), str):
            data["last_seen"] = datetime.fromisoformat(data["last_seen"])
        if isinstance(data.get("last_updated"), str):
            data["last_updated"] = datetime.fromisoformat(data["last_updated"])

        # Parse enum fields
        if isinstance(data.get("pattern_type"), str):
            data["pattern_type"] = PatternType(data["pattern_type"])

        return cls(**data)


class DecisionSignalNode(BaseModel):
    """
    Decision signal node representing a rule matching signal.

    Signals are atomic indicators used in decision-making, such as
    keyword matches, length thresholds, or structural patterns.
    """

    # Identifiers
    signal_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique signal identifier (UUID)"
    )
    signal_type: SignalType = Field(
        description="Type of signal"
    )
    signal_value: str = Field(
        description="Signal value (e.g., keyword, pattern)"
    )

    # Effectiveness metrics
    effectiveness_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Signal effectiveness score (0-1)"
    )
    true_positive_count: int = Field(
        default=0,
        ge=0,
        description="True positive count"
    )
    false_positive_count: int = Field(
        default=0,
        ge=0,
        description="False positive count"
    )
    true_negative_count: int = Field(
        default=0,
        ge=0,
        description="True negative count"
    )
    false_negative_count: int = Field(
        default=0,
        ge=0,
        description="False negative count"
    )

    # Time metadata
    created_at: datetime = Field(
        default_factory=utc_now,
        description="When signal was created"
    )
    last_updated: datetime = Field(
        default_factory=utc_now,
        description="Last update timestamp"
    )

    @field_validator('effectiveness_score')
    @classmethod
    def validate_effectiveness_score(cls, v: float) -> float:
        """Ensure effectiveness score is within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("effectiveness_score must be between 0.0 and 1.0")
        return v

    def calculate_effectiveness(self) -> float:
        """Calculate effectiveness score from counts."""
        total = (
            self.true_positive_count + self.false_positive_count +
            self.true_negative_count + self.false_negative_count
        )
        if total == 0:
            return 0.0

        # Effectiveness = (TP + TN) / Total
        correct = self.true_positive_count + self.true_negative_count
        return correct / total

    def update_statistics(
        self,
        true_positive: int = 0,
        false_positive: int = 0,
        true_negative: int = 0,
        false_negative: int = 0
    ) -> None:
        """
        Update signal statistics.

        Args:
            true_positive: Increment TP count
            false_positive: Increment FP count
            true_negative: Increment TN count
            false_negative: Increment FN count
        """
        self.true_positive_count += true_positive
        self.false_positive_count += false_positive
        self.true_negative_count += true_negative
        self.false_negative_count += false_negative

        # Recalculate effectiveness
        self.effectiveness_score = self.calculate_effectiveness()

        # Update timestamp
        self.last_updated = utc_now()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type.value,
            "signal_value": self.signal_value,
            "effectiveness_score": self.effectiveness_score,
            "true_positive_count": self.true_positive_count,
            "false_positive_count": self.false_positive_count,
            "true_negative_count": self.true_negative_count,
            "false_negative_count": self.false_negative_count,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionSignalNode":
        """Deserialize from dictionary."""
        # Parse datetime fields
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("last_updated"), str):
            data["last_updated"] = datetime.fromisoformat(data["last_updated"])

        # Parse enum fields
        if isinstance(data.get("signal_type"), str):
            data["signal_type"] = SignalType(data["signal_type"])

        return cls(**data)


class PatternEvolutionEdge(BaseModel):
    """
    Pattern evolution relationship edge.

    Tracks how patterns evolve over time, providing audit trail
    for pattern refinement and deprecation.
    """

    # Identifiers
    evolution_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique evolution identifier (UUID)"
    )
    from_pattern_id: str = Field(
        description="Source pattern ID"
    )
    to_pattern_id: str = Field(
        description="Target pattern ID"
    )

    # Evolution details
    evolution_type: EvolutionType = Field(
        description="Type of evolution"
    )
    reason: str = Field(
        description="Reason for evolution"
    )

    # Metadata
    timestamp: datetime = Field(
        default_factory=utc_now,
        description="When evolution occurred"
    )
    triggered_by: Optional[str] = Field(
        default=None,
        description="What triggered this evolution (job name, manual, etc.)"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "evolution_id": self.evolution_id,
            "from_pattern_id": self.from_pattern_id,
            "to_pattern_id": self.to_pattern_id,
            "evolution_type": self.evolution_type.value,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "triggered_by": self.triggered_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatternEvolutionEdge":
        """Deserialize from dictionary."""
        # Parse datetime fields
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])

        # Parse enum fields
        if isinstance(data.get("evolution_type"), str):
            data["evolution_type"] = EvolutionType(data["evolution_type"])

        return cls(**data)


class PatternSignalLink(BaseModel):
    """
    Link between pattern and signal nodes.

    Represents which signals contribute to a pattern and with what weight.
    """

    link_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique link identifier"
    )
    pattern_id: str = Field(
        description="Pattern ID"
    )
    signal_id: str = Field(
        description="Signal ID"
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Weight/importance of this signal in the pattern"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "link_id": self.link_id,
            "pattern_id": self.pattern_id,
            "signal_id": self.signal_id,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatternSignalLink":
        """Deserialize from dictionary."""
        return cls(**data)
