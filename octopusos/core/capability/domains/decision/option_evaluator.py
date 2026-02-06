"""
Option Evaluator - Multi-option evaluation for Decision Domain

This service implements DC-003:
- decision.option.evaluate: Evaluate multiple options and rank them

Key Design Principles:
1. Pure evaluation - no selection made
2. Support Shadow Classifier comparison
3. Score and rank all options
4. Record confidence metrics
5. No actions triggered (Decision → Action forbidden)
"""

import sqlite3
import json
import logging
from typing import Dict, List, Optional
from ulid import ULID

from agentos.core.capability.domains.decision.models import (
    Option,
    EvaluationResult,
)
from agentos.core.time import utc_now_ms


logger = logging.getLogger(__name__)


class OptionEvaluator:
    """
    Service for evaluating multiple options.

    Capabilities implemented:
    - decision.option.evaluate (DC-003)

    Usage:
        evaluator = OptionEvaluator(db_path="...")

        # Define options
        options = [
            Option(option_id="opt-1", description="Use Classifier A", ...),
            Option(option_id="opt-2", description="Use Classifier B", ...),
        ]

        # Evaluate
        result = evaluator.evaluate_options(
            decision_context_id="ctx-123",
            options=options,
            evaluated_by="governance-agent"
        )

        # Result contains:
        # - scores: {"opt-1": 85.0, "opt-2": 92.0}
        # - ranked_options: ["opt-2", "opt-1"]
        # - recommendation: "opt-2"
        # - confidence: 87.5
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize option evaluator.

        Args:
            db_path: Path to SQLite database
        """
        if db_path is None:
            from agentos.store import get_db_path
            db_path = get_db_path()

        self.db_path = db_path
        logger.info(f"OptionEvaluator initialized with db: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ===================================================================
    # DC-003: decision.option.evaluate
    # ===================================================================

    def evaluate_options(
        self,
        decision_context_id: str,
        options: List[Option],
        evaluated_by: str,
        evaluation_criteria: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> EvaluationResult:
        """
        Evaluate multiple options and rank them.

        Implements: decision.option.evaluate (DC-003)

        This is pure evaluation - no actions are triggered.
        The result can be used by:
        - decision.judge.select (human/governance selection)
        - Shadow Classifier comparison
        - A/B testing frameworks

        Args:
            decision_context_id: Context for this evaluation
            options: List of options to evaluate
            evaluated_by: Agent performing evaluation
            evaluation_criteria: Criteria for evaluation (optional)
            metadata: Additional metadata

        Returns:
            EvaluationResult with scores and rankings

        Raises:
            ValueError: If options list is empty or invalid
        """
        if not options:
            raise ValueError("Options list cannot be empty")

        # Generate evaluation ID
        evaluation_id = f"eval-{ULID()}"
        evaluated_at_ms = utc_now_ms()

        # Score each option
        scores = self._score_options(options, evaluation_criteria or {})

        # Rank options by score (descending)
        ranked_options = sorted(
            options, key=lambda opt: scores.get(opt.option_id, 0), reverse=True
        )
        ranked_option_ids = [opt.option_id for opt in ranked_options]

        # Recommendation is top-ranked option
        recommendation = ranked_option_ids[0] if ranked_option_ids else ""

        # Generate recommendation rationale
        if recommendation:
            top_option = self._get_option_by_id(options, recommendation)
            recommendation_rationale = self._generate_rationale(
                top_option, scores[recommendation], ranked_options
            )
        else:
            recommendation_rationale = ""

        # Compute confidence
        confidence = self._compute_confidence(scores, ranked_option_ids)

        # Create evaluation result
        result = EvaluationResult(
            evaluation_id=evaluation_id,
            decision_context_id=decision_context_id,
            options=options,
            scores=scores,
            ranked_options=ranked_option_ids,
            recommendation=recommendation,
            recommendation_rationale=recommendation_rationale,
            confidence=confidence,
            evaluated_by=evaluated_by,
            evaluated_at_ms=evaluated_at_ms,
            metadata=metadata or {},
        )

        # Store in database
        self._store_evaluation(result)

        logger.info(
            f"Evaluated {len(options)} options (eval_id: {evaluation_id}, "
            f"recommendation: {recommendation}, confidence: {confidence:.1f}%)"
        )

        return result

    def _score_options(
        self, options: List[Option], criteria: Dict
    ) -> Dict[str, float]:
        """
        Score each option based on evaluation criteria.

        Scoring algorithm:
        - Base score: 50.0
        - Cost: Lower cost increases score (max +20)
        - Time: Lower time increases score (max +15)
        - Benefits: Each benefit adds +5 (max +15)
        - Risks: Each risk subtracts -5 (no min)

        Returns:
            Dict mapping option_id to score (0-100)
        """
        scores = {}

        # Extract cost/time ranges for normalization
        costs = [opt.estimated_cost for opt in options]
        times = [opt.estimated_time_ms for opt in options]

        min_cost = min(costs) if costs else 0
        max_cost = max(costs) if costs else 1
        min_time = min(times) if times else 0
        max_time = max(times) if times else 1

        for opt in options:
            score = 50.0  # Base score

            # Cost component (lower is better, +0 to +20)
            if max_cost > min_cost:
                cost_norm = (max_cost - opt.estimated_cost) / (max_cost - min_cost)
                score += cost_norm * 20

            # Time component (lower is better, +0 to +15)
            if max_time > min_time:
                time_norm = (max_time - opt.estimated_time_ms) / (max_time - min_time)
                score += time_norm * 15

            # Benefits component (more benefits is better, +0 to +15)
            benefit_score = min(len(opt.benefits) * 5, 15)
            score += benefit_score

            # Risks component (fewer risks is better, -5 per risk)
            risk_penalty = len(opt.risks) * 5
            score -= risk_penalty

            # Clamp to 0-100 range
            score = max(0, min(100, score))

            scores[opt.option_id] = score

        return scores

    def _generate_rationale(
        self, top_option: Optional[Option], top_score: float, all_options: List[Option]
    ) -> str:
        """
        Generate human-readable rationale for recommendation.

        Args:
            top_option: Recommended option
            top_score: Score of top option
            all_options: All ranked options

        Returns:
            Rationale string
        """
        if not top_option:
            return "No options available for evaluation"

        rationale_parts = [
            f"Recommended option: {top_option.description}",
            f"Score: {top_score:.1f}/100",
            f"Estimated cost: ${top_option.estimated_cost:.2f}",
            f"Estimated time: {top_option.estimated_time_ms}ms",
        ]

        if top_option.benefits:
            benefits_str = ", ".join(top_option.benefits)
            rationale_parts.append(f"Key benefits: {benefits_str}")

        if top_option.risks:
            risks_str = ", ".join(top_option.risks)
            rationale_parts.append(f"Known risks: {risks_str}")

        # Compare to second-best option
        if len(all_options) > 1:
            second_option = all_options[1]
            rationale_parts.append(
                f"Alternative: {second_option.description} "
                f"(cost: ${second_option.estimated_cost:.2f}, "
                f"time: {second_option.estimated_time_ms}ms)"
            )

        return " | ".join(rationale_parts)

    def _compute_confidence(
        self, scores: Dict[str, float], ranked_option_ids: List[str]
    ) -> float:
        """
        Compute confidence in evaluation.

        Confidence factors:
        - Score spread: Wider spread = higher confidence
        - Top score: Higher top score = higher confidence
        - Number of options: More options = lower confidence

        Returns:
            Confidence (0-100)
        """
        if not ranked_option_ids or not scores:
            return 0.0

        top_score = scores[ranked_option_ids[0]]

        # Base confidence from top score
        confidence = top_score * 0.6

        # Score spread component
        if len(ranked_option_ids) > 1:
            second_score = scores[ranked_option_ids[1]]
            spread = top_score - second_score
            spread_confidence = min(spread / 20 * 40, 40)  # Max +40 for 20+ point spread
            confidence += spread_confidence

        # Number of options penalty
        num_options = len(ranked_option_ids)
        if num_options > 5:
            confidence *= 0.9  # -10% for many options

        # Clamp to 0-100
        return max(0, min(100, confidence))

    def _get_option_by_id(
        self, options: List[Option], option_id: str
    ) -> Optional[Option]:
        """Get option by ID"""
        for opt in options:
            if opt.option_id == option_id:
                return opt
        return None

    def _store_evaluation(self, result: EvaluationResult):
        """Store evaluation result in database"""
        conn = self._get_connection()
        cursor = conn.cursor()

        options_json = json.dumps([opt.model_dump() for opt in result.options])
        scores_json = json.dumps(result.scores)
        ranked_options_json = json.dumps(result.ranked_options)
        metadata_json = json.dumps(result.metadata)

        cursor.execute(
            """
            INSERT INTO decision_evaluations (
                evaluation_id, decision_context_id, options_json, scores_json,
                ranked_options_json, recommendation, recommendation_rationale,
                confidence, evaluated_by, evaluated_at_ms, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.evaluation_id,
                result.decision_context_id,
                options_json,
                scores_json,
                ranked_options_json,
                result.recommendation,
                result.recommendation_rationale,
                result.confidence,
                result.evaluated_by,
                result.evaluated_at_ms,
                metadata_json,
            ),
        )

        conn.commit()
        conn.close()

    # ===================================================================
    # Query Methods
    # ===================================================================

    def get_evaluation(self, evaluation_id: str) -> Optional[EvaluationResult]:
        """
        Get evaluation by ID.

        Args:
            evaluation_id: Evaluation identifier

        Returns:
            EvaluationResult or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT evaluation_id, decision_context_id, options_json, scores_json,
                   ranked_options_json, recommendation, recommendation_rationale,
                   confidence, evaluated_by, evaluated_at_ms, metadata
            FROM decision_evaluations
            WHERE evaluation_id = ?
            """,
            (evaluation_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        # Parse JSON fields
        options_data = json.loads(row["options_json"])
        options = [Option(**opt) for opt in options_data]

        scores = json.loads(row["scores_json"])
        ranked_options = json.loads(row["ranked_options_json"])
        metadata = json.loads(row["metadata"] or "{}")

        return EvaluationResult(
            evaluation_id=row["evaluation_id"],
            decision_context_id=row["decision_context_id"],
            options=options,
            scores=scores,
            ranked_options=ranked_options,
            recommendation=row["recommendation"],
            recommendation_rationale=row["recommendation_rationale"],
            confidence=row["confidence"],
            evaluated_by=row["evaluated_by"],
            evaluated_at_ms=row["evaluated_at_ms"],
            metadata=metadata,
        )

    def list_evaluations(
        self,
        decision_context_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[EvaluationResult]:
        """
        List evaluations with optional filters.

        Args:
            decision_context_id: Filter by context (optional)
            limit: Max results

        Returns:
            List of evaluations
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
            SELECT evaluation_id, decision_context_id, options_json, scores_json,
                   ranked_options_json, recommendation, recommendation_rationale,
                   confidence, evaluated_by, evaluated_at_ms, metadata
            FROM decision_evaluations
            WHERE 1=1
        """
        params = []

        if decision_context_id:
            query += " AND decision_context_id = ?"
            params.append(decision_context_id)

        query += " ORDER BY evaluated_at_ms DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        evaluations = []
        for row in rows:
            options_data = json.loads(row["options_json"])
            options = [Option(**opt) for opt in options_data]

            scores = json.loads(row["scores_json"])
            ranked_options = json.loads(row["ranked_options_json"])
            metadata = json.loads(row["metadata"] or "{}")

            evaluation = EvaluationResult(
                evaluation_id=row["evaluation_id"],
                decision_context_id=row["decision_context_id"],
                options=options,
                scores=scores,
                ranked_options=ranked_options,
                recommendation=row["recommendation"],
                recommendation_rationale=row["recommendation_rationale"],
                confidence=row["confidence"],
                evaluated_by=row["evaluated_by"],
                evaluated_at_ms=row["evaluated_at_ms"],
                metadata=metadata,
            )
            evaluations.append(evaluation)

        return evaluations


# ===================================================================
# Global instance
# ===================================================================

_option_evaluator_instance: Optional[OptionEvaluator] = None


def get_option_evaluator(db_path: Optional[str] = None) -> OptionEvaluator:
    """
    Get global option evaluator singleton.

    Args:
        db_path: Optional database path

    Returns:
        Singleton OptionEvaluator instance
    """
    global _option_evaluator_instance
    if _option_evaluator_instance is None:
        _option_evaluator_instance = OptionEvaluator(db_path=db_path)
    return _option_evaluator_instance
