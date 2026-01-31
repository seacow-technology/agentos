"""
Shadow Classifier Base Classes and Implementations

This module defines the base class for shadow classifiers and implements
concrete shadow classifier versions for parallel evaluation.

Shadow Classifier Constraints:
- Must be read-only (no side effects, no external calls)
- Must use same input/output format as active classifier
- Must provide change description for comparison
- Used only for parallel evaluation, never for direct replacement
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import uuid

from agentos.core.chat.models.decision_candidate import (
    DecisionCandidate,
    DecisionRole,
    ClassifierVersion,
)
from agentos.core.chat.models.info_need import (
    ClassificationResult,
    ClassificationSignal,
    ConfidenceLevel,
    InfoNeedType,
    LLMConfidenceResult,
    create_classification_result,
)

logger = logging.getLogger(__name__)


class BaseShadowClassifier(ABC):
    """
    Shadow classifier base class.

    Constraints:
    - Must be a read-only variant of InfoNeedClassifier
    - Cannot have any side effects (writes, network calls)
    - Input/output format must match active classifier exactly
    - Used only for parallel evaluation, not for production decisions
    """

    def __init__(self, version: ClassifierVersion):
        """
        Initialize shadow classifier.

        Args:
            version: Version metadata for this classifier
        """
        self.version = version
        self._validate_shadow_constraints()
        logger.info(
            f"Initialized shadow classifier: {version.version_id} - {version.change_description}"
        )

    @abstractmethod
    async def classify_shadow(
        self,
        question: str,
        context: Dict[str, Any],
    ) -> DecisionCandidate:
        """
        Perform shadow classification (computation only, no execution).

        Args:
            question: User's question to classify
            context: Additional context (conversation history, metadata)

        Returns:
            DecisionCandidate with role=SHADOW
        """
        pass

    def _validate_shadow_constraints(self) -> None:
        """
        Validate that shadow classifier meets constraints.

        This is a placeholder for runtime constraint validation.
        In production, this could check for:
        - No network access capabilities
        - No database write operations
        - No file system modifications
        """
        if self.version.version_type != "shadow":
            raise ValueError(
                f"Shadow classifier must have version_type='shadow', got '{self.version.version_type}'"
            )

    @abstractmethod
    def get_change_description(self) -> str:
        """
        Return detailed description of changes compared to active version.

        Returns:
            Human-readable description of what changed
        """
        pass

    def _create_decision_candidate(
        self,
        message_id: str,
        question_text: str,
        classification: ClassificationResult,
        latency_ms: float,
        session_id: str = "unknown",
        phase: str = "planning",
    ) -> DecisionCandidate:
        """
        Create a DecisionCandidate from classification result.

        Args:
            message_id: Message ID this decision applies to
            question_text: The original question text
            classification: Classification result
            latency_ms: Time taken to compute
            session_id: Session ID (default: "unknown")
            phase: Execution phase (default: "planning")

        Returns:
            DecisionCandidate with SHADOW role
        """
        import hashlib

        # Create question hash
        question_hash = hashlib.sha256(question_text.encode()).hexdigest()[:16]

        return DecisionCandidate(
            message_id=message_id,
            decision_role=DecisionRole.SHADOW,
            classifier_version=self.version,
            question_text=question_text,
            question_hash=question_hash,
            phase=phase,
            session_id=session_id,
            info_need_type=classification.info_need_type.value,
            confidence_level=classification.confidence_level.value,
            decision_action=classification.decision_action.value,
            reason_codes=[],
            rule_signals=classification.rule_signals.to_dict(),
            llm_confidence_score=(
                classification.llm_confidence.confidence.value
                if classification.llm_confidence
                else None
            ),
            latency_ms=latency_ms,
            shadow_metadata={
                "reasoning": classification.reasoning,
            },
        )


class ShadowClassifierV2ExpandKeywords(BaseShadowClassifier):
    """
    Shadow v2.a: Expanded keyword lists (lowest risk).

    Changes:
    - Expanded EXTERNAL_FACT_UNCERTAIN keyword list
    - Expanded AMBIENT_STATE time keyword list
    - No changes to decision matrix
    - No changes to confidence thresholds

    This is the most conservative shadow variant, only expanding
    the coverage of existing rule categories without changing logic.
    """

    def __init__(self):
        """Initialize v2.a shadow classifier."""
        version = ClassifierVersion(
            version_id="v2-shadow-expand-keywords",
            version_type="shadow",
            change_description="Expand keyword lists for EXTERNAL_FACT and AMBIENT_STATE",
        )
        super().__init__(version)

        # Base keywords (from v1 active)
        self.base_external_keywords = [
            "latest", "current", "recent", "now",
            "official", "authoritative", "standard",
        ]

        # Additional keywords for v2.a
        self.additional_external_keywords = [
            "最新", "latest update", "current status",
            "政策", "policy", "regulation", "法规",
            "趋势", "trend", "动态", "dynamics",
            "实时", "real-time", "live",
        ]

        # Base ambient keywords
        self.base_ambient_keywords = [
            "running", "status", "active", "current state",
        ]

        # Additional ambient keywords for v2.a
        self.additional_ambient_keywords = [
            "现在", "当前", "目前", "此刻",
            "now", "currently", "present",
            "实时状态", "runtime", "live status",
        ]

        # Combined keyword lists
        self.all_external_keywords = (
            self.base_external_keywords + self.additional_external_keywords
        )
        self.all_ambient_keywords = (
            self.base_ambient_keywords + self.additional_ambient_keywords
        )

    async def classify_shadow(
        self,
        question: str,
        context: Dict[str, Any],
    ) -> DecisionCandidate:
        """
        Classify using expanded keyword lists.

        Args:
            question: User's question
            context: Additional context

        Returns:
            DecisionCandidate with expanded rule matching
        """
        start_time = time.perf_counter()

        # Extract context info
        message_id = context.get("message_id", "unknown")
        session_id = context.get("session_id", "unknown")
        phase = context.get("phase", "planning")

        # Perform rule-based classification with expanded keywords
        classification = await self._classify_with_expanded_rules(question, context)

        # Calculate latency
        latency_ms = (time.perf_counter() - start_time) * 1000

        # Create decision candidate
        return self._create_decision_candidate(
            message_id=message_id,
            question_text=question,
            classification=classification,
            latency_ms=latency_ms,
            session_id=session_id,
            phase=phase,
        )

    async def _classify_with_expanded_rules(
        self,
        question: str,
        context: Dict[str, Any],
    ) -> ClassificationResult:
        """
        Classify using expanded rule-based matching.

        Args:
            question: User's question
            context: Additional context

        Returns:
            ClassificationResult using expanded keywords
        """
        question_lower = question.lower()

        # Check for external fact keywords (expanded list)
        has_external_keywords = False
        matched_external = []
        for keyword in self.all_external_keywords:
            if keyword.lower() in question_lower:
                has_external_keywords = True
                matched_external.append(keyword)

        # Check for ambient state keywords (expanded list)
        has_ambient_keywords = False
        matched_ambient = []
        for keyword in self.all_ambient_keywords:
            if keyword.lower() in question_lower:
                has_ambient_keywords = True
                matched_ambient.append(keyword)

        # Determine classification based on expanded rules
        if has_external_keywords and has_ambient_keywords:
            # Both signals: prioritize external facts
            info_type = InfoNeedType.EXTERNAL_FACT_UNCERTAIN
            confidence = ConfidenceLevel.LOW
            reasoning = (
                f"Detected both external fact and ambient state signals. "
                f"External keywords: {matched_external[:3]}. "
                f"Ambient keywords: {matched_ambient[:3]}. "
                f"Prioritizing external fact classification."
            )
            signal_strength = 0.85
        elif has_external_keywords:
            # External fact signals only
            info_type = InfoNeedType.EXTERNAL_FACT_UNCERTAIN
            confidence = ConfidenceLevel.LOW
            reasoning = (
                f"Detected external fact signals with expanded keyword coverage. "
                f"Matched: {matched_external[:3]}"
            )
            signal_strength = 0.80
        elif has_ambient_keywords:
            # Ambient state signals only
            info_type = InfoNeedType.AMBIENT_STATE
            confidence = ConfidenceLevel.HIGH
            reasoning = (
                f"Detected ambient state signals with expanded keyword coverage. "
                f"Matched: {matched_ambient[:3]}"
            )
            signal_strength = 0.90
        else:
            # No special signals: default to local knowledge
            info_type = InfoNeedType.LOCAL_KNOWLEDGE
            confidence = ConfidenceLevel.MEDIUM
            reasoning = "No time-sensitive or ambient state signals detected. Treating as local knowledge."
            signal_strength = 0.50

        # Build classification signals
        rule_signals = ClassificationSignal(
            has_time_sensitive_keywords=has_external_keywords,
            has_authoritative_keywords=has_external_keywords,
            has_ambient_state_keywords=has_ambient_keywords,
            matched_keywords=(matched_external + matched_ambient)[:10],
            signal_strength=signal_strength,
        )

        # Create classification result
        return create_classification_result(
            info_type=info_type,
            confidence=confidence,
            rule_signals=rule_signals,
            reasoning=reasoning,
            llm_confidence=None,
        )

    def get_change_description(self) -> str:
        """Return detailed change description."""
        return (
            "Shadow v2.a: Expanded Keyword Coverage\n"
            "=========================================\n\n"
            f"External Fact Keywords:\n"
            f"  Base: {len(self.base_external_keywords)} keywords\n"
            f"  Added: {len(self.additional_external_keywords)} keywords\n"
            f"  Total: {len(self.all_external_keywords)} keywords\n\n"
            f"Ambient State Keywords:\n"
            f"  Base: {len(self.base_ambient_keywords)} keywords\n"
            f"  Added: {len(self.additional_ambient_keywords)} keywords\n"
            f"  Total: {len(self.all_ambient_keywords)} keywords\n\n"
            "Impact: More aggressive detection of time-sensitive and ambient state questions.\n"
            "Risk Level: LOW - Only expands coverage, no logic changes."
        )


class ShadowClassifierV2AdjustThreshold(BaseShadowClassifier):
    """
    Shadow v2.b: Adjusted confidence thresholds.

    Changes:
    - Lowered EXTERNAL_FACT_UNCERTAIN confidence threshold from 0.6 to 0.5
    - More aggressive in triggering external information requirements
    - Decision matrix remains the same, but boundary shifts

    This variant tests whether lowering thresholds improves recall
    for external fact questions without excessive false positives.
    """

    def __init__(self):
        """Initialize v2.b shadow classifier."""
        version = ClassifierVersion(
            version_id="v2-shadow-adjust-threshold",
            version_type="shadow",
            change_description="Lower EXTERNAL_FACT confidence threshold from 0.6 to 0.5",
        )
        super().__init__(version)

        # Threshold adjustments
        self.external_fact_threshold = 0.5  # v1 active uses 0.6
        self.ambient_state_threshold = 0.7  # unchanged from v1

        # Base keywords (same as v1)
        self.external_keywords = [
            "latest", "current", "recent", "now",
            "official", "authoritative", "standard",
        ]
        self.ambient_keywords = [
            "running", "status", "active", "current state",
        ]

    async def classify_shadow(
        self,
        question: str,
        context: Dict[str, Any],
    ) -> DecisionCandidate:
        """
        Classify using adjusted thresholds.

        Args:
            question: User's question
            context: Additional context

        Returns:
            DecisionCandidate with adjusted threshold logic
        """
        start_time = time.perf_counter()

        # Extract context info
        message_id = context.get("message_id", "unknown")
        session_id = context.get("session_id", "unknown")
        phase = context.get("phase", "planning")

        # Perform classification with adjusted thresholds
        classification = await self._classify_with_adjusted_thresholds(question, context)

        # Calculate latency
        latency_ms = (time.perf_counter() - start_time) * 1000

        # Create decision candidate
        return self._create_decision_candidate(
            message_id=message_id,
            question_text=question,
            classification=classification,
            latency_ms=latency_ms,
            session_id=session_id,
            phase=phase,
        )

    async def _classify_with_adjusted_thresholds(
        self,
        question: str,
        context: Dict[str, Any],
    ) -> ClassificationResult:
        """
        Classify using adjusted confidence thresholds.

        Args:
            question: User's question
            context: Additional context

        Returns:
            ClassificationResult with adjusted thresholds
        """
        question_lower = question.lower()

        # Check for keywords (same as v1)
        has_external_keywords = any(
            kw.lower() in question_lower for kw in self.external_keywords
        )
        has_ambient_keywords = any(
            kw.lower() in question_lower for kw in self.ambient_keywords
        )

        matched_keywords = []
        if has_external_keywords:
            matched_keywords.extend([
                kw for kw in self.external_keywords
                if kw.lower() in question_lower
            ])
        if has_ambient_keywords:
            matched_keywords.extend([
                kw for kw in self.ambient_keywords
                if kw.lower() in question_lower
            ])

        # Compute signal strength (with adjusted threshold)
        if has_external_keywords:
            # v2.b: Lower threshold makes this trigger more easily
            signal_strength = 0.55  # Just above new threshold of 0.5
            info_type = InfoNeedType.EXTERNAL_FACT_UNCERTAIN
            confidence = ConfidenceLevel.MEDIUM  # Upgraded from LOW due to threshold change
            reasoning = (
                f"Detected external fact signals. "
                f"Signal strength {signal_strength} exceeds adjusted threshold {self.external_fact_threshold}. "
                f"Matched: {matched_keywords[:3]}"
            )
        elif has_ambient_keywords:
            signal_strength = 0.80
            info_type = InfoNeedType.AMBIENT_STATE
            confidence = ConfidenceLevel.HIGH
            reasoning = (
                f"Detected ambient state signals. "
                f"Signal strength {signal_strength} exceeds threshold {self.ambient_state_threshold}. "
                f"Matched: {matched_keywords[:3]}"
            )
        else:
            signal_strength = 0.40
            info_type = InfoNeedType.LOCAL_KNOWLEDGE
            confidence = ConfidenceLevel.MEDIUM
            reasoning = "No strong signals detected. Signal strength below thresholds. Treating as local knowledge."

        # Build classification signals
        rule_signals = ClassificationSignal(
            has_time_sensitive_keywords=has_external_keywords,
            has_authoritative_keywords=has_external_keywords,
            has_ambient_state_keywords=has_ambient_keywords,
            matched_keywords=matched_keywords,
            signal_strength=signal_strength,
        )

        # Create classification result
        return create_classification_result(
            info_type=info_type,
            confidence=confidence,
            rule_signals=rule_signals,
            reasoning=reasoning,
            llm_confidence=None,
        )

    def get_change_description(self) -> str:
        """Return detailed change description."""
        return (
            "Shadow v2.b: Adjusted Confidence Thresholds\n"
            "=============================================\n\n"
            f"Threshold Changes:\n"
            f"  External Fact Threshold: 0.6 -> {self.external_fact_threshold}\n"
            f"  Ambient State Threshold: {self.ambient_state_threshold} (unchanged)\n\n"
            "Impact: More aggressive triggering of EXTERNAL_FACT classification.\n"
            "Expected Result: Higher recall for time-sensitive questions, possible increase in false positives.\n"
            "Risk Level: MEDIUM - Changes decision boundaries, may affect production behavior if promoted."
        )
