"""
Evolution Decision Engine

Proposes trust evolution actions based on Trust Trajectory and Risk Timeline.
This engine PROPOSES actions but does NOT execute them.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from agentos.core.time.clock import utc_now
from agentos.core.capabilities.risk import RiskScorer
from agentos.core.capabilities.trust import TrustTierEngine
from .models import (
    EvolutionAction,
    EvolutionDecision,
    ReviewLevel,
    DecisionRecord
)
from .actions import (
    evaluate_promote,
    evaluate_freeze,
    evaluate_revoke,
    ActionProposal
)

logger = logging.getLogger(__name__)


class EvolutionEngine:
    """
    Evolution Decision Engine.

    Responsibilities:
    1. Gather evidence from E1 (Risk Timeline) and E2 (Trust Trajectory)
    2. Evaluate evolution action conditions
    3. Propose evolution actions with explanation
    4. Record all decisions in audit trail
    5. Provide decision replay capability

    Red Lines:
    - NEVER execute actions (only propose)
    - NEVER silent REVOKE
    - NEVER auto-promote to HIGH risk
    - NEVER skip explanation
    """

    def __init__(self, db_path: str):
        """
        Initialize evolution engine.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.risk_scorer = RiskScorer(db_path)
        self.trust_tier_engine = TrustTierEngine(db_path)
        self._init_tables()

    def _init_tables(self):
        """
        Initialize evolution decision tables if they don't exist.
        """
        with sqlite3.connect(self.db_path) as conn:
            # Check if table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='evolution_decisions'
            """)
            if not cursor.fetchone():
                logger.warning("evolution_decisions table not found, please run migration")

    def propose_action(
        self,
        extension_id: str,
        action_id: str = "*"
    ) -> EvolutionDecision:
        """
        Propose an evolution action for an extension/action.

        Steps:
        1. Gather evidence from Risk Timeline and Trust Trajectory
        2. Evaluate all action conditions (PROMOTE, FREEZE, REVOKE)
        3. Select highest priority action
        4. Build causal chain and explanation
        5. Record decision in database
        6. Return decision object

        Args:
            extension_id: Extension identifier
            action_id: Action identifier (default "*" for all actions)

        Returns:
            EvolutionDecision with proposed action and reasoning
        """
        # 1. Gather evidence
        evidence = self._gather_evidence(extension_id, action_id)

        # 2. Evaluate all actions
        promote_proposal = evaluate_promote(evidence)
        freeze_proposal = evaluate_freeze(evidence)
        revoke_proposal = evaluate_revoke(evidence)

        # 3. Select highest priority action (REVOKE > FREEZE > PROMOTE > NONE)
        selected_proposal = self._select_action(
            revoke_proposal, freeze_proposal, promote_proposal, evidence
        )

        # 4. Build causal chain and explanation
        causal_chain = self._build_causal_chain(selected_proposal, evidence)
        explanation = self._build_explanation(selected_proposal, evidence)

        # 5. Create decision object
        decision_id = f"evol_{uuid.uuid4().hex[:12]}"
        decision = EvolutionDecision(
            decision_id=decision_id,
            extension_id=extension_id,
            action_id=action_id,
            action=selected_proposal.action,
            risk_score=evidence.get("risk_score", 0),
            trust_tier=evidence.get("trust_tier", "UNKNOWN"),
            trust_trajectory=evidence.get("trust_trajectory", "UNKNOWN"),
            explanation=explanation,
            causal_chain=causal_chain,
            review_level=selected_proposal.review_level,
            conditions_met=selected_proposal.unmet_reasons,  # Store as list
            evidence=evidence,
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(days=7)  # Decisions expire after 7 days
        )

        # 6. Record decision
        self._record_decision(decision)

        # 7. Emit audit event
        self._emit_decision_audit(decision)

        return decision

    def _gather_evidence(self, extension_id: str, action_id: str) -> Dict:
        """
        Gather evidence from Risk Timeline and Trust Trajectory.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier

        Returns:
            Evidence dictionary with all relevant metrics
        """
        evidence = {
            "extension_id": extension_id,
            "action_id": action_id,
            "timestamp": utc_now().isoformat()
        }

        # Get risk score from E1 (Risk Timeline)
        try:
            risk_result = self.risk_scorer.calculate_risk(
                extension_id, action_id, window_days=30
            )
            evidence["risk_score"] = risk_result.score
            evidence["risk_dimensions"] = risk_result.dimensions
            evidence["risk_explanation"] = risk_result.explanation
        except Exception as e:
            logger.warning(f"Failed to get risk score: {e}")
            evidence["risk_score"] = 50.0  # Default to MEDIUM

        # Get trust tier
        try:
            tier_info = self.trust_tier_engine.get_tier(extension_id, action_id)
            evidence["trust_tier"] = tier_info.tier.value
        except Exception as e:
            logger.warning(f"Failed to get trust tier: {e}")
            evidence["trust_tier"] = "MEDIUM"

        # Get trust trajectory from E2
        trajectory_info = self._get_trust_trajectory(extension_id, action_id)
        evidence.update(trajectory_info)

        # Get execution history
        execution_stats = self._get_execution_stats(extension_id, action_id)
        evidence.update(execution_stats)

        # Get violation history
        violation_stats = self._get_violation_stats(extension_id, action_id)
        evidence.update(violation_stats)

        return evidence

    def _get_trust_trajectory(self, extension_id: str, action_id: str) -> Dict:
        """
        Get trust trajectory state from E2.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier

        Returns:
            Trajectory information dictionary
        """
        # TODO: Integration with E2 Trust Trajectory
        # For now, infer from execution history
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT state, consecutive_successes, consecutive_failures,
                           policy_rejections, time_in_state_seconds
                    FROM trust_trajectories
                    WHERE extension_id = ? AND action_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (extension_id, action_id))

                row = cursor.fetchone()
                if row:
                    return {
                        "trust_trajectory": row[0],
                        "consecutive_successes": row[1],
                        "consecutive_failures": row[2],
                        "policy_rejections": row[3],
                        "time_in_state_seconds": row[4]
                    }
        except Exception as e:
            logger.debug(f"Trust trajectory table not yet available: {e}")

        # Default trajectory based on execution stats
        return {
            "trust_trajectory": "EARNING",
            "consecutive_successes": 0,
            "consecutive_failures": 0,
            "policy_rejections": 0,
            "time_in_state_seconds": 0
        }

    def _get_execution_stats(self, extension_id: str, action_id: str) -> Dict:
        """
        Get execution statistics from capability audit.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier

        Returns:
            Execution statistics dictionary
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get total executions and success rate
                cursor = conn.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                           MIN(created_at) as first_execution,
                           MAX(created_at) as last_execution
                    FROM capability_audit
                    WHERE extension_id = ? AND (action_id = ? OR ? = '*')
                    AND created_at >= datetime('now', '-30 days')
                """, (extension_id, action_id, action_id))

                row = cursor.fetchone()
                if row and row[0] > 0:
                    total = row[0]
                    successes = row[1] or 0
                    first_exec = row[2]
                    last_exec = row[3]

                    # Calculate stable days
                    stable_days = 0
                    if first_exec and last_exec:
                        first_dt = datetime.fromisoformat(first_exec)
                        last_dt = datetime.fromisoformat(last_exec)
                        stable_days = (last_dt - first_dt).days

                    return {
                        "total_executions": total,
                        "successful_executions": successes,
                        "success_rate": successes / total if total > 0 else 0,
                        "stable_days": stable_days,
                        "first_execution": first_exec,
                        "last_execution": last_exec
                    }
        except Exception as e:
            logger.debug(f"Failed to get execution stats: {e}")

        return {
            "total_executions": 0,
            "successful_executions": 0,
            "success_rate": 0,
            "stable_days": 0
        }

    def _get_violation_stats(self, extension_id: str, action_id: str) -> Dict:
        """
        Get violation statistics.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier

        Returns:
            Violation statistics dictionary
        """
        violations = 0
        sandbox_violations = 0
        policy_denials = 0
        human_flags = 0

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check task_audits for violations
                cursor = conn.execute("""
                    SELECT event_type, COUNT(*) as count
                    FROM task_audits
                    WHERE json_extract(payload, '$.extension_id') = ?
                    AND event_type IN ('policy_violation', 'sandbox_violation', 'human_flag')
                    AND created_at >= datetime('now', '-30 days')
                    GROUP BY event_type
                """, (extension_id,))

                for row in cursor.fetchall():
                    event_type, count = row
                    if event_type == "policy_violation":
                        policy_denials = count
                        violations += count
                    elif event_type == "sandbox_violation":
                        sandbox_violations = count
                        violations += count
                    elif event_type == "human_flag":
                        human_flags = count
        except Exception as e:
            logger.debug(f"Failed to get violation stats: {e}")

        return {
            "violations": violations,
            "sandbox_violations": sandbox_violations,
            "policy_denials": policy_denials,
            "human_flags": human_flags,
            "sandbox_violation": sandbox_violations > 0,  # Boolean flag
            "policy_denial": policy_denials >= 3,  # Trigger flag
            "human_flag": human_flags > 0  # Boolean flag
        }

    def _select_action(
        self,
        revoke: ActionProposal,
        freeze: ActionProposal,
        promote: ActionProposal,
        evidence: Dict
    ) -> ActionProposal:
        """
        Select highest priority action from proposals.

        Priority order: REVOKE > FREEZE > PROMOTE > NONE

        Args:
            revoke: REVOKE proposal
            freeze: FREEZE proposal
            promote: PROMOTE proposal
            evidence: Evidence dictionary

        Returns:
            Selected ActionProposal
        """
        # REVOKE has highest priority (safety first)
        if revoke.conditions_met:
            return revoke

        # FREEZE has second priority
        if freeze.conditions_met:
            return freeze

        # PROMOTE has third priority
        if promote.conditions_met:
            return promote

        # No action needed
        return ActionProposal(
            action=EvolutionAction.NONE,
            conditions=None,
            conditions_met=True,
            unmet_reasons=[],
            review_level=ReviewLevel.NONE,
            evidence=evidence
        )

    def _build_causal_chain(self, proposal: ActionProposal, evidence: Dict) -> List[str]:
        """
        Build causal chain from evidence to action.

        Args:
            proposal: Selected action proposal
            evidence: Evidence dictionary

        Returns:
            List of causal chain steps
        """
        chain = []

        # Add evidence summary
        chain.append(
            f"Extension: {evidence.get('extension_id')}, "
            f"Action: {evidence.get('action_id')}"
        )

        # Add risk context
        risk_score = evidence.get("risk_score", 0)
        trust_tier = evidence.get("trust_tier", "UNKNOWN")
        chain.append(f"Risk Score: {risk_score:.2f}/100 (Tier: {trust_tier})")

        # Add trajectory context
        trajectory = evidence.get("trust_trajectory", "UNKNOWN")
        chain.append(f"Trust Trajectory: {trajectory}")

        # Add execution context
        total_execs = evidence.get("total_executions", 0)
        success_rate = evidence.get("success_rate", 0)
        chain.append(
            f"Execution History: {total_execs} total, "
            f"{success_rate * 100:.1f}% success rate"
        )

        # Add violation context if any
        violations = evidence.get("violations", 0)
        if violations > 0:
            chain.append(f"Violations Detected: {violations} in last 30 days")

        # Add decision
        chain.append(f"Proposed Action: {proposal.action.value}")

        # Add reasoning
        if proposal.conditions_met:
            chain.append("Conditions Met: All requirements satisfied")
        else:
            chain.append(f"Conditions Not Met: {len(proposal.unmet_reasons)} requirements unmet")

        return chain

    def _build_explanation(self, proposal: ActionProposal, evidence: Dict) -> str:
        """
        Build human-readable explanation for decision.

        Args:
            proposal: Selected action proposal
            evidence: Evidence dictionary

        Returns:
            Multi-line explanation string
        """
        lines = []

        # Header with extension context
        lines.append(f"Evolution Decision: {proposal.action.value}")
        lines.append(f"Extension: {evidence.get('extension_id', 'UNKNOWN')}, Action: {evidence.get('action_id', '*')}")
        lines.append("")

        # Action description
        lines.append("Action Description:")
        lines.append(f"  {proposal.action.get_description()}")
        lines.append("")

        # For REVOKE, add trigger reasons prominently
        if proposal.action == EvolutionAction.REVOKE and "revoke_triggers" in evidence:
            lines.append("⚠️  REVOKE Triggers:")
            for trigger in evidence["revoke_triggers"]:
                lines.append(f"  - {trigger}")
            lines.append("")

        # Conditions
        if proposal.action != EvolutionAction.NONE:
            lines.append("Conditions:")
            if proposal.conditions_met:
                lines.append("  ✅ All conditions satisfied")
            else:
                lines.append(f"  ❌ Unmet requirements ({len(proposal.unmet_reasons)}):")
                for reason in proposal.unmet_reasons:
                    lines.append(f"     - {reason}")
            lines.append("")

        # Evidence summary
        lines.append("Evidence Summary:")
        lines.append(f"  - Risk Score: {evidence.get('risk_score', 0):.2f}/100")
        lines.append(f"  - Trust Tier: {evidence.get('trust_tier', 'UNKNOWN')}")
        lines.append(f"  - Trust Trajectory: {evidence.get('trust_trajectory', 'UNKNOWN')}")
        lines.append(f"  - Total Executions: {evidence.get('total_executions', 0)}")
        lines.append(f"  - Success Rate: {evidence.get('success_rate', 0) * 100:.1f}%")
        lines.append(f"  - Stable Days: {evidence.get('stable_days', 0)}")
        lines.append(f"  - Violations: {evidence.get('violations', 0)}")

        # Add violation details for REVOKE/FREEZE
        if proposal.action in [EvolutionAction.REVOKE, EvolutionAction.FREEZE]:
            sandbox_viol = evidence.get('sandbox_violations', 0)
            policy_viol = evidence.get('policy_denials', 0)
            if sandbox_viol > 0:
                lines.append(f"  - Sandbox Violations: {sandbox_viol} ⚠️")
            if policy_viol > 0:
                lines.append(f"  - Policy Denials: {policy_viol} ⚠️")

        lines.append("")

        # Consequences
        if proposal.action != EvolutionAction.NONE:
            consequences = proposal.action.get_consequences()
            if consequences:
                lines.append("Consequences:")
                for consequence in consequences:
                    lines.append(f"  - {consequence}")
                lines.append("")

        # Review requirement
        lines.append(f"Review Level: {proposal.review_level.value}")
        if proposal.action.requires_human_review():
            lines.append("⚠️  Human review required before execution")
        lines.append("")

        # Causal chain reference
        lines.append("See causal_chain field for detailed decision path")

        return "\n".join(lines)

    def _record_decision(self, decision: EvolutionDecision):
        """
        Record decision in database for audit trail.

        Args:
            decision: EvolutionDecision to record
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO evolution_decisions (
                        decision_id, extension_id, action_id, action,
                        status, risk_score, trust_tier, trust_trajectory,
                        explanation, causal_chain, review_level,
                        evidence, created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    decision.decision_id,
                    decision.extension_id,
                    decision.action_id,
                    decision.action.value,
                    "PROPOSED",  # Initial status
                    decision.risk_score,
                    decision.trust_tier,
                    decision.trust_trajectory,
                    decision.explanation,
                    json.dumps(decision.causal_chain),
                    decision.review_level.value,
                    json.dumps(decision.evidence),
                    decision.created_at.isoformat(),
                    decision.expires_at.isoformat() if decision.expires_at else None
                ))
                conn.commit()
                logger.info(f"Recorded evolution decision: {decision.decision_id}")
        except Exception as e:
            logger.error(f"Failed to record evolution decision: {e}")

    def _emit_decision_audit(self, decision: EvolutionDecision):
        """
        Emit audit event for evolution decision.

        Args:
            decision: EvolutionDecision to audit
        """
        from agentos.core.capabilities.audit import emit_audit_event

        emit_audit_event(
            event_type="evolution_decision",
            details={
                "decision_id": decision.decision_id,
                "extension_id": decision.extension_id,
                "action_id": decision.action_id,
                "action": decision.action.value,
                "risk_score": decision.risk_score,
                "trust_tier": decision.trust_tier,
                "trust_trajectory": decision.trust_trajectory,
                "review_level": decision.review_level.value,
                "requires_review": decision.action.requires_human_review()
            },
            level="warning" if decision.action == EvolutionAction.REVOKE else "info"
        )

    def get_decision_history(
        self,
        extension_id: str,
        action_id: str = "*",
        limit: int = 10
    ) -> List[DecisionRecord]:
        """
        Get decision history for an extension/action.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier
            limit: Maximum number of records to return

        Returns:
            List of DecisionRecord objects
        """
        records = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT decision_id, extension_id, action_id, action,
                           status, risk_score, trust_tier, trust_trajectory,
                           explanation, approved_by, approved_at, created_at
                    FROM evolution_decisions
                    WHERE extension_id = ? AND (action_id = ? OR ? = '*')
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                cursor = conn.execute(query, (extension_id, action_id, action_id, limit))

                for row in cursor.fetchall():
                    record = DecisionRecord(
                        record_id=row[0],  # Using decision_id as record_id
                        decision_id=row[0],
                        extension_id=row[1],
                        action_id=row[2],
                        action=row[3],
                        status=row[4],
                        risk_score=row[5],
                        trust_tier=row[6],
                        trust_trajectory=row[7],
                        explanation=row[8],
                        approved_by=row[9],
                        approved_at=datetime.fromisoformat(row[10]) if row[10] else None,
                        created_at=datetime.fromisoformat(row[11])
                    )
                    records.append(record)
        except Exception as e:
            logger.error(f"Failed to get decision history: {e}")

        return records

    def approve_decision(
        self,
        decision_id: str,
        approved_by: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Approve an evolution decision (for E4 Human Review).

        Args:
            decision_id: Decision identifier
            approved_by: Who approved (username/email)
            notes: Optional approval notes

        Returns:
            True if approval successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE evolution_decisions
                    SET status = 'APPROVED',
                        approved_by = ?,
                        approved_at = ?,
                        notes = COALESCE(?, notes)
                    WHERE decision_id = ?
                """, (approved_by, utc_now().isoformat(), notes, decision_id))
                conn.commit()

                logger.info(f"Approved evolution decision: {decision_id} by {approved_by}")
                return True
        except Exception as e:
            logger.error(f"Failed to approve decision: {e}")
            return False

    def reject_decision(
        self,
        decision_id: str,
        rejected_by: str,
        reason: str
    ) -> bool:
        """
        Reject an evolution decision (for E4 Human Review).

        Args:
            decision_id: Decision identifier
            rejected_by: Who rejected (username/email)
            reason: Rejection reason

        Returns:
            True if rejection successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE evolution_decisions
                    SET status = 'REJECTED',
                        approved_by = ?,
                        approved_at = ?,
                        notes = ?
                    WHERE decision_id = ?
                """, (rejected_by, utc_now().isoformat(), f"REJECTED: {reason}", decision_id))
                conn.commit()

                logger.info(f"Rejected evolution decision: {decision_id} by {rejected_by}")
                return True
        except Exception as e:
            logger.error(f"Failed to reject decision: {e}")
            return False

    def submit_for_review(
        self,
        decision: EvolutionDecision,
        timeout_hours: int = 24
    ) -> Optional[str]:
        """
        Submit an evolution decision for human review (E4 integration).

        This integrates E3 (Evolution Decision Engine) with E4 (Human Review Queue).

        Args:
            decision: EvolutionDecision to submit for review
            timeout_hours: Hours until auto-reject (default 24)

        Returns:
            Review ID if submitted, None if not required or failed

        Note:
            Only PROMOTE and REVOKE actions require human review.
            FREEZE and NONE actions are auto-executed.
        """
        # Check if review is required
        if not decision.action.requires_human_review():
            logger.info(
                f"Decision {decision.decision_id} does not require review "
                f"(action: {decision.action.value})"
            )
            return None

        try:
            # Import here to avoid circular dependency
            from .review_queue import ReviewQueue

            queue = ReviewQueue(self.db_path)
            review_id = queue.submit_for_review(
                decision=decision,
                timeout_hours=timeout_hours,
                submitted_by="evolution_engine"
            )

            logger.info(
                f"Submitted decision {decision.decision_id} for human review: {review_id}"
            )
            return review_id

        except Exception as e:
            logger.error(f"Failed to submit decision for review: {e}")
            return None
