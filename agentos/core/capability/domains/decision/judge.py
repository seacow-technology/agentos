"""
Decision Judge - Final decision selection with rationale

This service implements DC-004 and DC-005:
- decision.judge.select: Select option from evaluation
- decision.record.rationale: Record detailed rationale with evidence

Key Design Principles:
1. Selection must have detailed rationale
2. Rejected alternatives must be recorded
3. Evidence must be linked
4. No actions triggered (Decision → Action forbidden)
5. Confidence level must be recorded
"""

import sqlite3
import json
import logging
from typing import Dict, List, Optional
from ulid import ULID

from agentos.core.capability.domains.decision.models import (
    SelectedDecision,
    DecisionRationale,
    EvaluationResult,
    Option,
    ConfidenceLevel,
)
from agentos.core.time import utc_now_ms


logger = logging.getLogger(__name__)


class DecisionJudge:
    """
    Service for making final decisions.

    Capabilities implemented:
    - decision.judge.select (DC-004)
    - decision.record.rationale (DC-005)

    Usage:
        judge = DecisionJudge(db_path="...")

        # Select option from evaluation
        decision = judge.select_option(
            evaluation_result=eval_result,
            selection_criteria={"min_confidence": 80.0},
            decided_by="governance-agent"
        )

        # Record additional rationale
        rationale = judge.record_rationale(
            decision_id=decision.decision_id,
            rationale="Extended rationale with details...",
            evidence_refs=["evidence-123", "evidence-456"],
            created_by="user-alice"
        )
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize decision judge.

        Args:
            db_path: Path to SQLite database
        """
        if db_path is None:
            from agentos.store import get_db_path
            db_path = get_db_path()

        self.db_path = db_path
        logger.info(f"DecisionJudge initialized with db: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ===================================================================
    # DC-004: decision.judge.select
    # ===================================================================

    def select_option(
        self,
        evaluation_result: EvaluationResult,
        decided_by: str,
        selection_criteria: Optional[Dict] = None,
        override_option_id: Optional[str] = None,
        custom_rationale: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> SelectedDecision:
        """
        Select an option from evaluation result.

        Implements: decision.judge.select (DC-004)

        This is the final decision step. It:
        1. Selects an option (recommendation or override)
        2. Records detailed rationale
        3. Records rejected alternatives with reasons
        4. Links to evidence record
        5. Assigns confidence level

        Args:
            evaluation_result: Evaluation to select from
            decided_by: Who is making the decision (user/agent)
            selection_criteria: Criteria for selection (optional)
            override_option_id: Override recommendation (optional)
            custom_rationale: Custom rationale (optional)
            metadata: Additional metadata

        Returns:
            SelectedDecision with rationale and evidence

        Raises:
            ValueError: If override_option_id not found in evaluation
        """
        # Determine which option to select
        if override_option_id:
            # Human/governance override
            selected_option = evaluation_result.get_option_by_id(override_option_id)
            if selected_option is None:
                raise ValueError(
                    f"Override option {override_option_id} not found in evaluation"
                )
            selection_method = "override"
        else:
            # Use recommendation
            selected_option = evaluation_result.get_option_by_id(
                evaluation_result.recommendation
            )
            if selected_option is None:
                raise ValueError("No recommendation found in evaluation")
            selection_method = "recommendation"

        # Get alternatives (rejected options)
        alternatives_rejected = [
            opt for opt in evaluation_result.options if opt.option_id != selected_option.option_id
        ]

        # Generate rejection reasons
        rejection_reasons = self._generate_rejection_reasons(
            selected_option, alternatives_rejected, evaluation_result.scores
        )

        # Generate rationale
        if custom_rationale:
            rationale = custom_rationale
        else:
            rationale = self._generate_selection_rationale(
                selected_option,
                evaluation_result,
                selection_method,
                selection_criteria or {},
            )

        # Determine confidence level
        confidence_level = self._determine_confidence_level(
            evaluation_result.confidence,
            selection_method == "override",
        )

        # Generate decision ID
        decision_id = f"decision-{ULID()}"
        decided_at_ms = utc_now_ms()

        # Create decision
        decision = SelectedDecision(
            decision_id=decision_id,
            evaluation_id=evaluation_result.evaluation_id,
            selected_option=selected_option,
            rationale=rationale,
            alternatives_rejected=alternatives_rejected,
            rejection_reasons=rejection_reasons,
            confidence_level=confidence_level,
            decided_by=decided_by,
            decided_at_ms=decided_at_ms,
            evidence_id=None,  # Will be set after evidence recording
            metadata=metadata or {},
        )

        # Store in database
        self._store_decision(decision)

        # Record evidence
        evidence_id = self._record_evidence(decision)
        decision.evidence_id = evidence_id

        # Update decision with evidence_id
        self._update_decision_evidence(decision_id, evidence_id)

        logger.info(
            f"Selected option {selected_option.option_id} from evaluation "
            f"{evaluation_result.evaluation_id} (decision_id: {decision_id}, "
            f"confidence: {confidence_level.value})"
        )

        return decision

    def _generate_rejection_reasons(
        self,
        selected_option: Option,
        alternatives: List[Option],
        scores: Dict[str, float],
    ) -> Dict[str, str]:
        """
        Generate reasons for rejecting alternatives.

        Args:
            selected_option: Option that was selected
            alternatives: Options that were not selected
            scores: Scores from evaluation

        Returns:
            Dict mapping option_id to rejection reason
        """
        rejection_reasons = {}
        selected_score = scores.get(selected_option.option_id, 0)

        for alt in alternatives:
            alt_score = scores.get(alt.option_id, 0)
            score_diff = selected_score - alt_score

            reasons = []

            # Score comparison
            if score_diff > 10:
                reasons.append(f"Lower score ({alt_score:.1f} vs {selected_score:.1f})")

            # Cost comparison
            if alt.estimated_cost > selected_option.estimated_cost * 1.2:
                cost_diff = alt.estimated_cost - selected_option.estimated_cost
                reasons.append(f"Higher cost (+${cost_diff:.2f})")

            # Time comparison
            if alt.estimated_time_ms > selected_option.estimated_time_ms * 1.5:
                time_diff = alt.estimated_time_ms - selected_option.estimated_time_ms
                reasons.append(f"Slower execution (+{time_diff}ms)")

            # Risks comparison
            if len(alt.risks) > len(selected_option.risks):
                risk_diff = len(alt.risks) - len(selected_option.risks)
                reasons.append(f"More risks (+{risk_diff})")

            if not reasons:
                reasons.append("Lower overall score")

            rejection_reasons[alt.option_id] = " | ".join(reasons)

        return rejection_reasons

    def _generate_selection_rationale(
        self,
        selected_option: Option,
        evaluation_result: EvaluationResult,
        selection_method: str,
        selection_criteria: Dict,
    ) -> str:
        """
        Generate detailed rationale for selection.

        Args:
            selected_option: Option that was selected
            evaluation_result: Full evaluation result
            selection_method: "recommendation" or "override"
            selection_criteria: Selection criteria

        Returns:
            Detailed rationale string
        """
        rationale_parts = []

        # Selection method
        if selection_method == "override":
            rationale_parts.append(
                f"Human/governance override: Selected {selected_option.description}"
            )
        else:
            rationale_parts.append(
                f"Selected recommended option: {selected_option.description}"
            )

        # Score and confidence
        score = evaluation_result.scores.get(selected_option.option_id, 0)
        rationale_parts.append(
            f"Evaluation score: {score:.1f}/100 (confidence: {evaluation_result.confidence:.1f}%)"
        )

        # Cost and time
        rationale_parts.append(
            f"Cost: ${selected_option.estimated_cost:.2f}, Time: {selected_option.estimated_time_ms}ms"
        )

        # Benefits
        if selected_option.benefits:
            benefits_str = ", ".join(selected_option.benefits)
            rationale_parts.append(f"Key benefits: {benefits_str}")

        # Risks
        if selected_option.risks:
            risks_str = ", ".join(selected_option.risks)
            rationale_parts.append(f"Known risks: {risks_str}")

        # Number of alternatives considered
        num_alternatives = len(evaluation_result.options) - 1
        if num_alternatives > 0:
            rationale_parts.append(
                f"Considered {num_alternatives} alternative(s)"
            )

        # Selection criteria
        if selection_criteria:
            criteria_str = ", ".join([f"{k}={v}" for k, v in selection_criteria.items()])
            rationale_parts.append(f"Criteria: {criteria_str}")

        return " | ".join(rationale_parts)

    def _determine_confidence_level(
        self, confidence_score: float, is_override: bool
    ) -> ConfidenceLevel:
        """
        Determine confidence level from numeric score.

        Args:
            confidence_score: Numeric confidence (0-100)
            is_override: Whether this was a human override

        Returns:
            ConfidenceLevel enum
        """
        # Human overrides are treated as high confidence
        if is_override:
            return ConfidenceLevel.HIGH

        if confidence_score >= 95:
            return ConfidenceLevel.VERY_HIGH
        elif confidence_score >= 80:
            return ConfidenceLevel.HIGH
        elif confidence_score >= 60:
            return ConfidenceLevel.MEDIUM
        elif confidence_score >= 40:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    def _store_decision(self, decision: SelectedDecision):
        """Store decision in database"""
        conn = self._get_connection()
        cursor = conn.cursor()

        selected_option_json = decision.selected_option.model_dump_json()
        alternatives_json = json.dumps([alt.model_dump() for alt in decision.alternatives_rejected])
        rejection_reasons_json = json.dumps(decision.rejection_reasons)
        metadata_json = json.dumps(decision.metadata)

        cursor.execute(
            """
            INSERT INTO decision_selections (
                decision_id, evaluation_id, selected_option_id, selected_option_json,
                rationale, alternatives_rejected_json, rejection_reasons_json,
                confidence_level, decided_by, decided_at_ms, evidence_id, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision.decision_id,
                decision.evaluation_id,
                decision.selected_option.option_id,
                selected_option_json,
                decision.rationale,
                alternatives_json,
                rejection_reasons_json,
                decision.confidence_level.value,
                decision.decided_by,
                decision.decided_at_ms,
                decision.evidence_id,
                metadata_json,
            ),
        )

        conn.commit()
        conn.close()

    def _update_decision_evidence(self, decision_id: str, evidence_id: str):
        """Update decision with evidence ID"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE decision_selections SET evidence_id = ? WHERE decision_id = ?",
            (evidence_id, decision_id),
        )

        conn.commit()
        conn.close()

    def _record_evidence(self, decision: SelectedDecision) -> str:
        """
        Record evidence for decision.

        Returns:
            Evidence ID
        """
        # Generate evidence ID
        evidence_id = f"evidence-{ULID()}"

        # For now, just log
        # In production, this would call evidence.record capability
        logger.info(
            f"Evidence: decision.select on {decision.decision_id} | "
            f"selected={decision.selected_option.option_id}, "
            f"confidence={decision.confidence_level.value}"
        )

        # TODO: Integrate with evidence service
        # evidence_service.record(
        #     operation_type="decision.select",
        #     operation_id=decision.decision_id,
        #     params={"evaluation_id": decision.evaluation_id},
        #     result={"selected_option_id": decision.selected_option.option_id}
        # )

        return evidence_id

    # ===================================================================
    # DC-005: decision.record.rationale
    # ===================================================================

    def record_rationale(
        self,
        decision_id: str,
        rationale: str,
        created_by: str,
        evidence_refs: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ) -> DecisionRationale:
        """
        Record detailed rationale for a decision.

        Implements: decision.record.rationale (DC-005)

        This allows adding extended rationale with evidence references
        after the initial decision is made.

        Args:
            decision_id: Decision to add rationale to
            rationale: Detailed rationale text
            created_by: Who is recording this rationale
            evidence_refs: List of evidence IDs (optional)
            metadata: Additional metadata

        Returns:
            DecisionRationale record

        Raises:
            ValueError: If decision not found
        """
        # Verify decision exists
        decision = self.get_decision(decision_id)
        if decision is None:
            raise ValueError(f"Decision not found: {decision_id}")

        # Generate rationale ID
        rationale_id = f"rationale-{ULID()}"
        created_at_ms = utc_now_ms()

        # Create rationale
        rationale_obj = DecisionRationale(
            rationale_id=rationale_id,
            decision_id=decision_id,
            rationale=rationale,
            evidence_refs=evidence_refs or [],
            created_by=created_by,
            created_at_ms=created_at_ms,
            metadata=metadata or {},
        )

        # Store in database
        conn = self._get_connection()
        cursor = conn.cursor()

        evidence_refs_json = json.dumps(evidence_refs or [])
        metadata_json = json.dumps(metadata or {})

        cursor.execute(
            """
            INSERT INTO decision_rationales (
                rationale_id, decision_id, rationale, evidence_refs_json,
                created_by, created_at_ms, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rationale_id,
                decision_id,
                rationale,
                evidence_refs_json,
                created_by,
                created_at_ms,
                metadata_json,
            ),
        )

        conn.commit()
        conn.close()

        logger.info(
            f"Recorded rationale {rationale_id} for decision {decision_id} "
            f"(evidence_refs: {len(evidence_refs or [])})"
        )

        return rationale_obj

    # ===================================================================
    # Query Methods
    # ===================================================================

    def get_decision(self, decision_id: str) -> Optional[SelectedDecision]:
        """
        Get decision by ID.

        Args:
            decision_id: Decision identifier

        Returns:
            SelectedDecision or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT decision_id, evaluation_id, selected_option_id, selected_option_json,
                   rationale, alternatives_rejected_json, rejection_reasons_json,
                   confidence_level, decided_by, decided_at_ms, evidence_id, metadata
            FROM decision_selections
            WHERE decision_id = ?
            """,
            (decision_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        # Parse JSON fields
        selected_option = Option.model_validate_json(row["selected_option_json"])
        alternatives_data = json.loads(row["alternatives_rejected_json"] or "[]")
        alternatives_rejected = [Option(**alt) for alt in alternatives_data]
        rejection_reasons = json.loads(row["rejection_reasons_json"] or "{}")
        metadata = json.loads(row["metadata"] or "{}")

        return SelectedDecision(
            decision_id=row["decision_id"],
            evaluation_id=row["evaluation_id"],
            selected_option=selected_option,
            rationale=row["rationale"],
            alternatives_rejected=alternatives_rejected,
            rejection_reasons=rejection_reasons,
            confidence_level=ConfidenceLevel(row["confidence_level"]),
            decided_by=row["decided_by"],
            decided_at_ms=row["decided_at_ms"],
            evidence_id=row["evidence_id"],
            metadata=metadata,
        )

    def get_rationales(self, decision_id: str) -> List[DecisionRationale]:
        """
        Get all rationales for a decision.

        Args:
            decision_id: Decision identifier

        Returns:
            List of DecisionRationale objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT rationale_id, decision_id, rationale, evidence_refs_json,
                   created_by, created_at_ms, metadata
            FROM decision_rationales
            WHERE decision_id = ?
            ORDER BY created_at_ms ASC
            """,
            (decision_id,),
        )

        rows = cursor.fetchall()
        conn.close()

        rationales = []
        for row in rows:
            evidence_refs = json.loads(row["evidence_refs_json"] or "[]")
            metadata = json.loads(row["metadata"] or "{}")

            rationale = DecisionRationale(
                rationale_id=row["rationale_id"],
                decision_id=row["decision_id"],
                rationale=row["rationale"],
                evidence_refs=evidence_refs,
                created_by=row["created_by"],
                created_at_ms=row["created_at_ms"],
                metadata=metadata,
            )
            rationales.append(rationale)

        return rationales


# ===================================================================
# Global instance
# ===================================================================

_decision_judge_instance: Optional[DecisionJudge] = None


def get_decision_judge(db_path: Optional[str] = None) -> DecisionJudge:
    """
    Get global decision judge singleton.

    Args:
        db_path: Optional database path

    Returns:
        Singleton DecisionJudge instance
    """
    global _decision_judge_instance
    if _decision_judge_instance is None:
        _decision_judge_instance = DecisionJudge(db_path=db_path)
    return _decision_judge_instance
