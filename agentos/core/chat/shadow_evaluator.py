"""
Shadow Score Evaluator - Reality Alignment Score Computation

This module implements the Reality Alignment Score calculation engine for v3
Shadow Classifier System. The score measures "how little a decision was slapped
by reality" - not a loss function for optimization, but a ranking metric for
choosing better decisions.

Key Design Principles:
- Scores range from 0.0 (severe misalignment) to 1.0 (perfect alignment)
- Scoring is based on user behavior signals, NOT answer correctness
- Supports batch computation for historical data
- Provides explainability (signal contributions)
- Never modifies or triggers any actions - pure computation

Scoring Formula:
    base_score = 1.0
    score = base_score
            - 0.3 × contradiction_signals
            - 0.2 × forced_retry_signals
            - 0.1 × user_override_signals
            + 0.1 × smooth_completion_signals

Signal Mapping:
    Contradiction (-0.3 each):
        - phase_violation: Decision violated phase constraints
        - explicit_negative_feedback: User gave thumbs down

    Forced Retry (-0.2 each):
        - reask_same_question: User re-asked same question
        - abandoned_response: User abandoned without reading

    User Override (-0.1 each):
        - user_followup_override: User immediately contradicted
        - delayed_comm_request: User later manually searched

    Smooth Completion (+0.1 each):
        - smooth_completion: Clean interaction, no friction
        - explicit_positive_feedback: User gave thumbs up
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from uuid import uuid4

from agentos.core.time import utc_now
from agentos.core.audit import (

    get_decision_set_by_id,
    get_decision_set_by_message_id,
    get_user_behavior_signals_for_message,
    log_shadow_evaluation,
)

logger = logging.getLogger(__name__)


# ============================================
# Data Models
# ============================================

@dataclass
class SignalContribution:
    """Contribution of a single signal to the Reality Alignment Score.

    Attributes:
        signal_type: Type of user behavior signal
        weight: Weight applied to this signal (-0.3 to +0.1)
        count: Number of occurrences of this signal
        contribution: Total contribution to score (weight × count)
        description: Human-readable description
    """
    signal_type: str
    weight: float
    count: int
    contribution: float
    description: str


@dataclass
class RealityAlignmentScore:
    """Reality Alignment Score computation result.

    Attributes:
        decision_set_id: ID of decision set being evaluated
        message_id: Message ID
        session_id: Session ID
        candidate_id: ID of the decision candidate (active or shadow)
        decision_role: "active" or "shadow"

        # Score
        score: Final Reality Alignment Score (0.0-1.0)
        raw_score: Raw score before clamping (can be < 0.0)
        base_score: Starting score before signal adjustments

        # Signal contributions
        signal_contributions: List of signal contributions
        total_signals_count: Total number of signals used
        signals_by_category: Count of signals by category

        # Metadata
        evaluation_id: Unique evaluation identifier
        evaluation_timestamp: When evaluation was computed
        evaluation_time_ms: Computation time in milliseconds
    """
    decision_set_id: str
    message_id: str
    session_id: str
    candidate_id: str
    decision_role: str

    score: float
    raw_score: float
    base_score: float = 1.0

    signal_contributions: List[SignalContribution] = field(default_factory=list)
    total_signals_count: int = 0
    signals_by_category: Dict[str, int] = field(default_factory=dict)

    evaluation_id: str = field(default_factory=lambda: str(uuid4()))
    evaluation_timestamp: datetime = field(default_factory=utc_now)
    evaluation_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "decision_set_id": self.decision_set_id,
            "message_id": self.message_id,
            "session_id": self.session_id,
            "candidate_id": self.candidate_id,
            "decision_role": self.decision_role,
            "score": self.score,
            "raw_score": self.raw_score,
            "base_score": self.base_score,
            "signal_contributions": [
                {
                    "signal_type": sc.signal_type,
                    "weight": sc.weight,
                    "count": sc.count,
                    "contribution": sc.contribution,
                    "description": sc.description,
                }
                for sc in self.signal_contributions
            ],
            "total_signals_count": self.total_signals_count,
            "signals_by_category": self.signals_by_category,
            "evaluation_id": self.evaluation_id,
            "evaluation_timestamp": self.evaluation_timestamp.isoformat(),
            "evaluation_time_ms": self.evaluation_time_ms,
        }


# ============================================
# Signal Weights Configuration
# ============================================

# Signal weight categories and their weights
SIGNAL_WEIGHTS: Dict[str, Tuple[float, str, str]] = {
    # Format: signal_type -> (weight, category, description)

    # Contradiction signals (-0.3 each): Strong negative
    "phase_violation": (
        -0.3,
        "contradiction",
        "Decision violated phase constraints (e.g., REQUIRE_COMM in planning)"
    ),
    "explicit_negative_feedback": (
        -0.3,
        "contradiction",
        "User explicitly gave negative feedback (thumbs down)"
    ),

    # Forced retry signals (-0.2 each): Moderate negative
    "reask_same_question": (
        -0.2,
        "forced_retry",
        "User re-asked the same question (dissatisfied with answer)"
    ),
    "abandoned_response": (
        -0.2,
        "forced_retry",
        "User abandoned interaction without reading response"
    ),

    # User override signals (-0.1 each): Minor negative
    "user_followup_override": (
        -0.1,
        "user_override",
        "User immediately contradicted decision (e.g., ran /comm after DIRECT_ANSWER)"
    ),
    "delayed_comm_request": (
        -0.1,
        "user_override",
        "User later manually requested communication"
    ),

    # Smooth completion signals (+0.1 each): Positive
    "smooth_completion": (
        +0.1,
        "smooth_completion",
        "Clean interaction with no friction"
    ),
    "explicit_positive_feedback": (
        +0.1,
        "smooth_completion",
        "User explicitly gave positive feedback (thumbs up)"
    ),
}


# ============================================
# Shadow Score Calculator
# ============================================

class ShadowScoreCalculator:
    """Calculates Reality Alignment Scores for decision candidates.

    This class is responsible for:
    1. Extracting user behavior signals from audit log
    2. Computing Reality Alignment Scores based on signal weights
    3. Providing explainability for score computation
    4. Supporting batch computation for historical data

    Design Constraints:
    - Pure computation: No side effects, no state modification
    - Deterministic: Same signals always produce same score
    - Transparent: All signal contributions are tracked and explainable
    """

    def __init__(self, signal_weights: Optional[Dict[str, Tuple[float, str, str]]] = None):
        """Initialize calculator with signal weights.

        Args:
            signal_weights: Optional custom signal weights.
                           Defaults to SIGNAL_WEIGHTS if not provided.
        """
        self.signal_weights = signal_weights or SIGNAL_WEIGHTS

    def compute_score_for_message(
        self,
        message_id: str,
        decision_role: str = "active",
    ) -> Optional[RealityAlignmentScore]:
        """Compute Reality Alignment Score for a message's decision.

        This is the main entry point for single-message score computation.

        Args:
            message_id: Message ID to compute score for
            decision_role: "active" or "shadow" (default: "active")

        Returns:
            RealityAlignmentScore if decision set and signals found, None otherwise

        Example:
            >>> calculator = ShadowScoreCalculator()
            >>> score = calculator.compute_score_for_message("msg-123", "active")
            >>> print(f"Score: {score.score:.2f}")
            >>> for contrib in score.signal_contributions:
            ...     print(f"  {contrib.signal_type}: {contrib.contribution:+.2f}")
        """
        start_time = utc_now()

        # Load decision set
        decision_set_event = get_decision_set_by_message_id(message_id)
        if not decision_set_event:
            logger.warning(f"No decision set found for message_id={message_id}")
            return None

        payload = decision_set_event["payload"]
        decision_set_id = payload["decision_set_id"]
        session_id = payload["session_id"]

        # Get candidate ID based on role
        if decision_role == "active":
            candidate_id = payload["active_decision"].get("candidate_id", "active")
        else:
            # For shadow, we need version_id to identify which shadow
            # For now, just use first shadow if exists
            if payload.get("shadow_decisions"):
                candidate_id = payload["shadow_decisions"][0].get("candidate_id", "shadow-0")
            else:
                logger.warning(f"No shadow decisions in decision set {decision_set_id}")
                return None

        # Load user behavior signals
        signals = get_user_behavior_signals_for_message(message_id)

        # Compute score
        score_result = self._compute_score_from_signals(
            decision_set_id=decision_set_id,
            message_id=message_id,
            session_id=session_id,
            candidate_id=candidate_id,
            decision_role=decision_role,
            signals=signals,
        )

        # Calculate evaluation time
        end_time = utc_now()
        score_result.evaluation_time_ms = (end_time - start_time).total_seconds() * 1000

        return score_result

    def compute_scores_for_decision_set(
        self,
        decision_set_id: str,
    ) -> Dict[str, RealityAlignmentScore]:
        """Compute Reality Alignment Scores for all decisions in a decision set.

        This computes scores for both active and all shadow decisions in the set.

        Args:
            decision_set_id: Decision set ID

        Returns:
            Dictionary mapping decision role/version to RealityAlignmentScore
            Keys: "active", "shadow-v2.0-alpha", "shadow-v2.0-beta", etc.

        Example:
            >>> calculator = ShadowScoreCalculator()
            >>> scores = calculator.compute_scores_for_decision_set("ds-abc123")
            >>> print(f"Active score: {scores['active'].score:.2f}")
            >>> for version, score in scores.items():
            ...     if version.startswith("shadow-"):
            ...         print(f"{version}: {score.score:.2f}")
        """
        start_time = utc_now()

        # Load decision set
        decision_set_event = get_decision_set_by_id(decision_set_id)
        if not decision_set_event:
            logger.error(f"No decision set found for decision_set_id={decision_set_id}")
            return {}

        payload = decision_set_event["payload"]
        message_id = payload["message_id"]
        session_id = payload["session_id"]

        # Load user behavior signals
        signals = get_user_behavior_signals_for_message(message_id)

        results = {}

        # Compute score for active decision
        active_decision = payload["active_decision"]
        active_candidate_id = active_decision.get("candidate_id", "active")

        active_score = self._compute_score_from_signals(
            decision_set_id=decision_set_id,
            message_id=message_id,
            session_id=session_id,
            candidate_id=active_candidate_id,
            decision_role="active",
            signals=signals,
        )
        results["active"] = active_score

        # Compute scores for shadow decisions
        shadow_decisions = payload.get("shadow_decisions", [])
        shadow_versions = payload.get("shadow_versions", [])

        for idx, shadow_decision in enumerate(shadow_decisions):
            shadow_candidate_id = shadow_decision.get("candidate_id", f"shadow-{idx}")
            version_id = shadow_versions[idx] if idx < len(shadow_versions) else f"unknown-{idx}"

            shadow_score = self._compute_score_from_signals(
                decision_set_id=decision_set_id,
                message_id=message_id,
                session_id=session_id,
                candidate_id=shadow_candidate_id,
                decision_role="shadow",
                signals=signals,
            )

            # Use version_id as key
            results[f"shadow-{version_id}"] = shadow_score

        # Calculate evaluation time for all
        end_time = utc_now()
        evaluation_time_ms = (end_time - start_time).total_seconds() * 1000

        for score in results.values():
            score.evaluation_time_ms = evaluation_time_ms

        return results

    def compute_scores_batch(
        self,
        decision_set_ids: List[str],
    ) -> Dict[str, Dict[str, RealityAlignmentScore]]:
        """Compute Reality Alignment Scores for multiple decision sets (batch).

        This is useful for historical data analysis and periodic evaluation jobs.

        Args:
            decision_set_ids: List of decision set IDs to evaluate

        Returns:
            Dictionary mapping decision_set_id to scores dict
            Format: {decision_set_id: {"active": score, "shadow-v2.0": score, ...}}

        Example:
            >>> calculator = ShadowScoreCalculator()
            >>> batch_scores = calculator.compute_scores_batch([
            ...     "ds-001", "ds-002", "ds-003"
            ... ])
            >>> for ds_id, scores in batch_scores.items():
            ...     print(f"{ds_id}: active={scores['active'].score:.2f}")
        """
        results = {}

        for decision_set_id in decision_set_ids:
            try:
                scores = self.compute_scores_for_decision_set(decision_set_id)
                if scores:
                    results[decision_set_id] = scores
            except Exception as e:
                logger.error(f"Failed to compute scores for {decision_set_id}: {e}")
                continue

        return results

    def _compute_score_from_signals(
        self,
        decision_set_id: str,
        message_id: str,
        session_id: str,
        candidate_id: str,
        decision_role: str,
        signals: List[Dict[str, Any]],
    ) -> RealityAlignmentScore:
        """Compute score from user behavior signals (internal).

        This is the core scoring logic that applies signal weights.

        Args:
            decision_set_id: Decision set ID
            message_id: Message ID
            session_id: Session ID
            candidate_id: Candidate ID
            decision_role: "active" or "shadow"
            signals: List of user behavior signal events

        Returns:
            RealityAlignmentScore with detailed breakdown
        """
        base_score = 1.0
        raw_score = base_score

        signal_contributions = []
        signal_counts = {}
        signals_by_category = {}
        known_signal_count = 0

        # Count signals by type
        for signal_event in signals:
            signal_type = signal_event["payload"]["signal_type"]
            signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1

        # Apply weights for each signal type
        for signal_type, count in signal_counts.items():
            if signal_type not in self.signal_weights:
                logger.debug(f"Unknown signal type: {signal_type}, skipping")
                continue

            weight, category, description = self.signal_weights[signal_type]
            contribution = weight * count
            raw_score += contribution

            # Track contribution
            signal_contributions.append(SignalContribution(
                signal_type=signal_type,
                weight=weight,
                count=count,
                contribution=contribution,
                description=description,
            ))

            # Count by category
            signals_by_category[category] = signals_by_category.get(category, 0) + count
            known_signal_count += count

        # Clamp score to [0.0, 1.0]
        final_score = max(0.0, min(1.0, raw_score))

        return RealityAlignmentScore(
            decision_set_id=decision_set_id,
            message_id=message_id,
            session_id=session_id,
            candidate_id=candidate_id,
            decision_role=decision_role,
            score=final_score,
            raw_score=raw_score,
            base_score=base_score,
            signal_contributions=signal_contributions,
            total_signals_count=known_signal_count,
            signals_by_category=signals_by_category,
        )


# ============================================
# High-Level API
# ============================================

async def evaluate_decision_set(
    decision_set_id: str,
    log_to_audit: bool = True,
) -> Optional[Dict[str, RealityAlignmentScore]]:
    """Evaluate a decision set and compute Reality Alignment Scores.

    This is the main high-level API for evaluating decision sets.
    It computes scores for all decisions (active + shadows) and optionally
    logs the evaluation results to the audit trail.

    Args:
        decision_set_id: Decision set ID to evaluate
        log_to_audit: If True, log evaluation results to audit trail

    Returns:
        Dictionary mapping decision role to RealityAlignmentScore
        Keys: "active", "shadow-v2.0-alpha", etc.
        Returns None if decision set not found or no signals available.

    Example:
        >>> scores = await evaluate_decision_set("ds-abc123", log_to_audit=True)
        >>> if scores:
        ...     print(f"Active: {scores['active'].score:.2f}")
        ...     for key, score in scores.items():
        ...         if key.startswith("shadow-"):
        ...             print(f"{key}: {score.score:.2f}")
    """
    calculator = ShadowScoreCalculator()
    scores = calculator.compute_scores_for_decision_set(decision_set_id)

    if not scores:
        logger.warning(f"No scores computed for decision_set_id={decision_set_id}")
        return None

    # Log to audit trail if requested
    if log_to_audit:
        active_score = scores.get("active")
        if active_score:
            # Build shadow scores dict
            shadow_scores = {}
            signals_used = set()

            for key, score in scores.items():
                if key.startswith("shadow-"):
                    version_id = key.replace("shadow-", "")
                    shadow_scores[version_id] = score.score

                # Collect all signal types used
                for contrib in score.signal_contributions:
                    signals_used.add(contrib.signal_type)

            # Log evaluation result
            await log_shadow_evaluation(
                evaluation_id=active_score.evaluation_id,
                decision_set_id=decision_set_id,
                message_id=active_score.message_id,
                session_id=active_score.session_id,
                active_score=active_score.score,
                shadow_scores=shadow_scores,
                signals_used=list(signals_used),
                evaluation_time_ms=active_score.evaluation_time_ms,
            )

    return scores


async def evaluate_decision_set_batch(
    decision_set_ids: List[str],
    log_to_audit: bool = True,
) -> Dict[str, Dict[str, RealityAlignmentScore]]:
    """Evaluate multiple decision sets in batch.

    This is useful for periodic evaluation jobs that process historical data.

    Args:
        decision_set_ids: List of decision set IDs to evaluate
        log_to_audit: If True, log evaluation results to audit trail

    Returns:
        Dictionary mapping decision_set_id to scores dict
        Format: {decision_set_id: {"active": score, "shadow-v2.0": score, ...}}

    Example:
        >>> batch_results = await evaluate_decision_set_batch([
        ...     "ds-001", "ds-002", "ds-003"
        ... ], log_to_audit=True)
        >>> for ds_id, scores in batch_results.items():
        ...     print(f"{ds_id}: active={scores['active'].score:.2f}")
    """
    calculator = ShadowScoreCalculator()
    batch_scores = calculator.compute_scores_batch(decision_set_ids)

    # Log each evaluation if requested
    if log_to_audit:
        for decision_set_id, scores in batch_scores.items():
            active_score = scores.get("active")
            if not active_score:
                continue

            # Build shadow scores dict
            shadow_scores = {}
            signals_used = set()

            for key, score in scores.items():
                if key.startswith("shadow-"):
                    version_id = key.replace("shadow-", "")
                    shadow_scores[version_id] = score.score

                # Collect all signal types used
                for contrib in score.signal_contributions:
                    signals_used.add(contrib.signal_type)

            # Log evaluation result
            try:
                await log_shadow_evaluation(
                    evaluation_id=active_score.evaluation_id,
                    decision_set_id=decision_set_id,
                    message_id=active_score.message_id,
                    session_id=active_score.session_id,
                    active_score=active_score.score,
                    shadow_scores=shadow_scores,
                    signals_used=list(signals_used),
                    evaluation_time_ms=active_score.evaluation_time_ms,
                )
            except Exception as e:
                logger.error(f"Failed to log evaluation for {decision_set_id}: {e}")

    return batch_scores


def format_score_explanation(score: RealityAlignmentScore) -> str:
    """Format a human-readable explanation of the score computation.

    Args:
        score: RealityAlignmentScore to explain

    Returns:
        Multi-line string with detailed explanation

    Example:
        >>> calculator = ShadowScoreCalculator()
        >>> score = calculator.compute_score_for_message("msg-123")
        >>> print(format_score_explanation(score))
        Reality Alignment Score: 0.75

        Base Score: 1.00

        Signal Contributions:
          [+0.10] smooth_completion (1×): Clean interaction with no friction
          [-0.10] user_followup_override (1×): User immediately contradicted decision

        Categories:
          smooth_completion: 1 signal(s)
          user_override: 1 signal(s)

        Final Score: 0.75 (raw: 0.75)
    """
    lines = [
        f"Reality Alignment Score: {score.score:.2f}",
        "",
        f"Base Score: {score.base_score:.2f}",
        "",
        "Signal Contributions:",
    ]

    if score.signal_contributions:
        for contrib in sorted(score.signal_contributions, key=lambda c: c.contribution, reverse=True):
            sign = "+" if contrib.contribution >= 0 else ""
            lines.append(
                f"  [{sign}{contrib.contribution:.2f}] {contrib.signal_type} "
                f"({contrib.count}×): {contrib.description}"
            )
    else:
        lines.append("  No signals found")

    lines.append("")
    lines.append("Categories:")
    if score.signals_by_category:
        for category, count in sorted(score.signals_by_category.items()):
            lines.append(f"  {category}: {count} signal(s)")
    else:
        lines.append("  No signals found")

    lines.append("")
    lines.append(f"Final Score: {score.score:.2f} (raw: {score.raw_score:.2f})")

    return "\n".join(lines)


# ============================================
# Singleton Instance
# ============================================

_calculator = ShadowScoreCalculator()


def get_calculator() -> ShadowScoreCalculator:
    """Get singleton calculator instance."""
    return _calculator
