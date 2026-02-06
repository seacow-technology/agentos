"""
Evolution Review Queue (Phase E4)

Human review interface for trust evolution decisions.

Core Principles:
- Humans only participate in "trust evolution", not "execution"
- All human actions must have audit trail
- Timeout auto-reject after 24h (configurable)
- Cannot bypass Policy or Sandbox

Red Lines:
- ❌ Humans cannot directly execute extensions
- ❌ Cannot skip Policy / Sandbox
- ❌ Cannot "emergency override" without record
"""

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from agentos.core.time.clock import utc_now
from agentos.core.capabilities.audit import emit_audit_event
from .models import EvolutionDecision, EvolutionAction

logger = logging.getLogger(__name__)


# Default timeout for reviews (24 hours)
DEFAULT_REVIEW_TIMEOUT_HOURS = 24


@dataclass
class ReviewStatus:
    """Review status enumeration."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"


@dataclass
class EvolutionReview:
    """
    Evolution review record.

    Attributes:
        review_id: Unique review identifier
        decision_id: Associated evolution decision ID
        extension_id: Extension identifier
        action_id: Action identifier
        action: Evolution action being reviewed
        status: Review status (PENDING/APPROVED/REJECTED/TIMEOUT)
        risk_score: Risk score at submission
        trust_tier: Trust tier at submission
        trust_trajectory: Trust trajectory at submission
        context: Full decision context
        submitted_at: When review was submitted
        reviewed_at: When review was completed (if applicable)
        reviewer: Who reviewed (if applicable)
        reason: Review decision reason
        timeout_at: When review auto-rejects
        submitted_by: Who submitted for review
    """
    review_id: str
    decision_id: str
    extension_id: str
    action_id: str
    action: str
    status: str
    risk_score: float
    trust_tier: str
    trust_trajectory: str
    context: Dict
    submitted_at: datetime
    reviewed_at: Optional[datetime]
    reviewer: Optional[str]
    reason: Optional[str]
    timeout_at: datetime
    submitted_by: str

    def to_dict(self) -> Dict:
        """Convert to dictionary for API/CLI output."""
        return {
            "review_id": self.review_id,
            "decision_id": self.decision_id,
            "extension_id": self.extension_id,
            "action_id": self.action_id,
            "action": self.action,
            "status": self.status,
            "risk_score": round(self.risk_score, 2),
            "trust_tier": self.trust_tier,
            "trust_trajectory": self.trust_trajectory,
            "context": self.context,
            "submitted_at": int(self.submitted_at.timestamp() * 1000),
            "reviewed_at": int(self.reviewed_at.timestamp() * 1000) if self.reviewed_at else None,
            "reviewer": self.reviewer,
            "reason": self.reason,
            "timeout_at": int(self.timeout_at.timestamp() * 1000),
            "submitted_by": self.submitted_by
        }

    def is_pending(self) -> bool:
        """Check if review is still pending."""
        return self.status == ReviewStatus.PENDING

    def is_timeout(self) -> bool:
        """Check if review has timed out."""
        return utc_now() >= self.timeout_at and self.status == ReviewStatus.PENDING


class ReviewQueue:
    """
    Evolution Review Queue.

    Responsibilities:
    1. Submit evolution decisions for human review
    2. List pending reviews
    3. Approve/reject reviews with reason
    4. Handle timeout auto-reject
    5. Maintain complete audit trail

    Red Lines:
    - Never allow execution without review
    - Never skip timeout mechanism
    - Never allow approval without reason
    """

    def __init__(self, db_path: str):
        """
        Initialize review queue.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._init_tables()

    def _init_tables(self):
        """Initialize review queue tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            # Check if table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='evolution_reviews'
            """)
            if not cursor.fetchone():
                logger.warning("evolution_reviews table not found, please run migration v72")

    def submit_for_review(
        self,
        decision: EvolutionDecision,
        timeout_hours: int = DEFAULT_REVIEW_TIMEOUT_HOURS,
        submitted_by: str = "system"
    ) -> str:
        """
        Submit an evolution decision for human review.

        Args:
            decision: EvolutionDecision to review
            timeout_hours: Hours until auto-reject (default 24)
            submitted_by: Who submitted for review

        Returns:
            Review ID

        Raises:
            ValueError: If decision doesn't require review
        """
        # Validate decision requires review
        if not decision.action.requires_human_review():
            raise ValueError(
                f"Action {decision.action.value} does not require human review"
            )

        review_id = f"review_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        timeout_at = now + timedelta(hours=timeout_hours)

        # Build context from decision
        context = {
            "explanation": decision.explanation,
            "causal_chain": decision.causal_chain,
            "evidence": decision.evidence,
            "conditions_met": decision.conditions_met,
            "review_level": decision.review_level.value,
            "consequences": decision.action.get_consequences()
        }

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Insert review record
                conn.execute("""
                    INSERT INTO evolution_reviews (
                        review_id, decision_id, extension_id, action_id,
                        action, status, risk_score, trust_tier, trust_trajectory,
                        context, submitted_at, timeout_at, submitted_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    review_id,
                    decision.decision_id,
                    decision.extension_id,
                    decision.action_id,
                    decision.action.value,
                    ReviewStatus.PENDING,
                    decision.risk_score,
                    decision.trust_tier,
                    decision.trust_trajectory,
                    json.dumps(context),
                    now.isoformat(),
                    timeout_at.isoformat(),
                    submitted_by
                ))

                # Insert audit record
                self._audit_event(
                    conn,
                    review_id,
                    decision.decision_id,
                    "review_submitted",
                    actor=submitted_by,
                    reason="Evolution action requires human review",
                    details={
                        "action": decision.action.value,
                        "risk_score": decision.risk_score,
                        "trust_tier": decision.trust_tier,
                        "timeout_hours": timeout_hours
                    }
                )

                conn.commit()
                logger.info(f"Submitted evolution decision for review: {review_id}")

        except Exception as e:
            logger.error(f"Failed to submit evolution decision for review: {e}")
            raise

        # Emit audit event
        emit_audit_event(
            event_type="evolution_review_submitted",
            details={
                "review_id": review_id,
                "decision_id": decision.decision_id,
                "extension_id": decision.extension_id,
                "action": decision.action.value,
                "submitted_by": submitted_by,
                "timeout_at": timeout_at.isoformat()
            },
            level="info"
        )

        return review_id

    def list_pending_reviews(
        self,
        include_context: bool = True
    ) -> List[EvolutionReview]:
        """
        List all pending reviews.

        Args:
            include_context: Whether to include full context

        Returns:
            List of pending EvolutionReview objects
        """
        reviews = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT review_id, decision_id, extension_id, action_id,
                           action, status, risk_score, trust_tier, trust_trajectory,
                           context, submitted_at, reviewed_at, reviewer, reason,
                           timeout_at, submitted_by
                    FROM evolution_reviews
                    WHERE status = ?
                    ORDER BY submitted_at DESC
                """, (ReviewStatus.PENDING,))

                for row in cursor.fetchall():
                    context_data = json.loads(row[9]) if include_context else {}

                    review = EvolutionReview(
                        review_id=row[0],
                        decision_id=row[1],
                        extension_id=row[2],
                        action_id=row[3],
                        action=row[4],
                        status=row[5],
                        risk_score=row[6],
                        trust_tier=row[7],
                        trust_trajectory=row[8],
                        context=context_data,
                        submitted_at=datetime.fromisoformat(row[10]),
                        reviewed_at=datetime.fromisoformat(row[11]) if row[11] else None,
                        reviewer=row[12],
                        reason=row[13],
                        timeout_at=datetime.fromisoformat(row[14]),
                        submitted_by=row[15]
                    )
                    reviews.append(review)

        except Exception as e:
            logger.error(f"Failed to list pending reviews: {e}")

        return reviews

    def get_review(self, review_id: str) -> Optional[EvolutionReview]:
        """
        Get a specific review by ID.

        Args:
            review_id: Review identifier

        Returns:
            EvolutionReview object or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT review_id, decision_id, extension_id, action_id,
                           action, status, risk_score, trust_tier, trust_trajectory,
                           context, submitted_at, reviewed_at, reviewer, reason,
                           timeout_at, submitted_by
                    FROM evolution_reviews
                    WHERE review_id = ?
                """, (review_id,))

                row = cursor.fetchone()
                if row:
                    return EvolutionReview(
                        review_id=row[0],
                        decision_id=row[1],
                        extension_id=row[2],
                        action_id=row[3],
                        action=row[4],
                        status=row[5],
                        risk_score=row[6],
                        trust_tier=row[7],
                        trust_trajectory=row[8],
                        context=json.loads(row[9]),
                        submitted_at=datetime.fromisoformat(row[10]),
                        reviewed_at=datetime.fromisoformat(row[11]) if row[11] else None,
                        reviewer=row[12],
                        reason=row[13],
                        timeout_at=datetime.fromisoformat(row[14]),
                        submitted_by=row[15]
                    )
        except Exception as e:
            logger.error(f"Failed to get review {review_id}: {e}")

        return None

    def approve_review(
        self,
        review_id: str,
        reviewer: str,
        reason: str
    ) -> bool:
        """
        Approve an evolution review.

        Args:
            review_id: Review identifier
            reviewer: Human reviewer identifier
            reason: Reason for approval (REQUIRED)

        Returns:
            True if approval successful, False otherwise

        Red Line: reason is REQUIRED, cannot approve without justification
        """
        if not reason or not reason.strip():
            raise ValueError("Approval reason is REQUIRED and cannot be empty")

        now = utc_now()

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check review exists and is pending
                cursor = conn.execute("""
                    SELECT status, timeout_at FROM evolution_reviews
                    WHERE review_id = ?
                """, (review_id,))

                row = cursor.fetchone()
                if not row:
                    logger.warning(f"Review not found: {review_id}")
                    return False

                status, timeout_at_str = row

                if status != ReviewStatus.PENDING:
                    logger.warning(f"Review {review_id} is not pending (status: {status})")
                    return False

                # Check timeout
                timeout_at = datetime.fromisoformat(timeout_at_str)
                if now >= timeout_at:
                    logger.warning(f"Review {review_id} has timed out")
                    return False

                # Update review status
                conn.execute("""
                    UPDATE evolution_reviews
                    SET status = ?,
                        reviewed_at = ?,
                        reviewer = ?,
                        reason = ?
                    WHERE review_id = ?
                """, (
                    ReviewStatus.APPROVED,
                    now.isoformat(),
                    reviewer,
                    reason,
                    review_id
                ))

                # Get decision_id for audit
                cursor = conn.execute(
                    "SELECT decision_id, extension_id, action FROM evolution_reviews WHERE review_id = ?",
                    (review_id,)
                )
                decision_id, extension_id, action = cursor.fetchone()

                # Update associated evolution decision
                conn.execute("""
                    UPDATE evolution_decisions
                    SET status = 'APPROVED',
                        approved_by = ?,
                        approved_at = ?,
                        notes = ?
                    WHERE decision_id = ?
                """, (reviewer, now.isoformat(), f"APPROVED: {reason}", decision_id))

                # Insert audit record
                self._audit_event(
                    conn,
                    review_id,
                    decision_id,
                    "review_approved",
                    actor=reviewer,
                    reason=reason,
                    details={
                        "extension_id": extension_id,
                        "action": action
                    }
                )

                conn.commit()
                logger.info(f"Approved review {review_id} by {reviewer}")

        except Exception as e:
            logger.error(f"Failed to approve review {review_id}: {e}")
            return False

        # Emit audit event
        emit_audit_event(
            event_type="evolution_review_approved",
            details={
                "review_id": review_id,
                "decision_id": decision_id,
                "reviewer": reviewer,
                "reason": reason
            },
            level="info"
        )

        return True

    def reject_review(
        self,
        review_id: str,
        reviewer: str,
        reason: str
    ) -> bool:
        """
        Reject an evolution review.

        Args:
            review_id: Review identifier
            reviewer: Human reviewer identifier
            reason: Reason for rejection (REQUIRED)

        Returns:
            True if rejection successful, False otherwise

        Red Line: reason is REQUIRED, cannot reject without justification
        """
        if not reason or not reason.strip():
            raise ValueError("Rejection reason is REQUIRED and cannot be empty")

        now = utc_now()

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check review exists and is pending
                cursor = conn.execute("""
                    SELECT status FROM evolution_reviews
                    WHERE review_id = ?
                """, (review_id,))

                row = cursor.fetchone()
                if not row:
                    logger.warning(f"Review not found: {review_id}")
                    return False

                status = row[0]

                if status != ReviewStatus.PENDING:
                    logger.warning(f"Review {review_id} is not pending (status: {status})")
                    return False

                # Update review status
                conn.execute("""
                    UPDATE evolution_reviews
                    SET status = ?,
                        reviewed_at = ?,
                        reviewer = ?,
                        reason = ?
                    WHERE review_id = ?
                """, (
                    ReviewStatus.REJECTED,
                    now.isoformat(),
                    reviewer,
                    reason,
                    review_id
                ))

                # Get decision_id for audit
                cursor = conn.execute(
                    "SELECT decision_id, extension_id, action FROM evolution_reviews WHERE review_id = ?",
                    (review_id,)
                )
                decision_id, extension_id, action = cursor.fetchone()

                # Update associated evolution decision
                conn.execute("""
                    UPDATE evolution_decisions
                    SET status = 'REJECTED',
                        approved_by = ?,
                        approved_at = ?,
                        notes = ?
                    WHERE decision_id = ?
                """, (reviewer, now.isoformat(), f"REJECTED: {reason}", decision_id))

                # Insert audit record
                self._audit_event(
                    conn,
                    review_id,
                    decision_id,
                    "review_rejected",
                    actor=reviewer,
                    reason=reason,
                    details={
                        "extension_id": extension_id,
                        "action": action
                    }
                )

                conn.commit()
                logger.info(f"Rejected review {review_id} by {reviewer}")

        except Exception as e:
            logger.error(f"Failed to reject review {review_id}: {e}")
            return False

        # Emit audit event
        emit_audit_event(
            event_type="evolution_review_rejected",
            details={
                "review_id": review_id,
                "decision_id": decision_id,
                "reviewer": reviewer,
                "reason": reason
            },
            level="warning"
        )

        return True

    def process_timeouts(self) -> int:
        """
        Process timed out reviews (auto-reject).

        This should be called periodically (e.g., by a cron job or background task).

        Returns:
            Number of reviews timed out
        """
        now = utc_now()
        timed_out_count = 0

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Find timed out reviews
                cursor = conn.execute("""
                    SELECT review_id, decision_id, extension_id, action
                    FROM evolution_reviews
                    WHERE status = ? AND timeout_at <= ?
                """, (ReviewStatus.PENDING, now.isoformat()))

                timed_out = cursor.fetchall()

                for review_id, decision_id, extension_id, action in timed_out:
                    # Update review status
                    conn.execute("""
                        UPDATE evolution_reviews
                        SET status = ?,
                            reviewed_at = ?,
                            reason = ?
                        WHERE review_id = ?
                    """, (
                        ReviewStatus.TIMEOUT,
                        now.isoformat(),
                        "Review timed out after 24 hours",
                        review_id
                    ))

                    # Update associated evolution decision
                    conn.execute("""
                        UPDATE evolution_decisions
                        SET status = 'EXPIRED',
                            notes = ?
                        WHERE decision_id = ?
                    """, ("TIMEOUT: Review expired after 24 hours", decision_id))

                    # Insert audit record
                    self._audit_event(
                        conn,
                        review_id,
                        decision_id,
                        "review_timeout",
                        actor="system",
                        reason="Review timed out",
                        details={
                            "extension_id": extension_id,
                            "action": action,
                            "timeout_at": now.isoformat()
                        }
                    )

                    timed_out_count += 1

                    logger.warning(f"Review {review_id} timed out (decision: {decision_id})")

                    # Emit audit event
                    emit_audit_event(
                        event_type="evolution_review_timeout",
                        details={
                            "review_id": review_id,
                            "decision_id": decision_id,
                            "extension_id": extension_id,
                            "action": action
                        },
                        level="warning"
                    )

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to process timeouts: {e}")

        if timed_out_count > 0:
            logger.info(f"Processed {timed_out_count} timed out reviews")

        return timed_out_count

    def get_review_history(
        self,
        extension_id: Optional[str] = None,
        limit: int = 50
    ) -> List[EvolutionReview]:
        """
        Get review history.

        Args:
            extension_id: Filter by extension (optional)
            limit: Maximum number of records

        Returns:
            List of EvolutionReview objects
        """
        reviews = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                if extension_id:
                    query = """
                        SELECT review_id, decision_id, extension_id, action_id,
                               action, status, risk_score, trust_tier, trust_trajectory,
                               context, submitted_at, reviewed_at, reviewer, reason,
                               timeout_at, submitted_by
                        FROM evolution_reviews
                        WHERE extension_id = ?
                        ORDER BY submitted_at DESC
                        LIMIT ?
                    """
                    cursor = conn.execute(query, (extension_id, limit))
                else:
                    query = """
                        SELECT review_id, decision_id, extension_id, action_id,
                               action, status, risk_score, trust_tier, trust_trajectory,
                               context, submitted_at, reviewed_at, reviewer, reason,
                               timeout_at, submitted_by
                        FROM evolution_reviews
                        ORDER BY submitted_at DESC
                        LIMIT ?
                    """
                    cursor = conn.execute(query, (limit,))

                for row in cursor.fetchall():
                    review = EvolutionReview(
                        review_id=row[0],
                        decision_id=row[1],
                        extension_id=row[2],
                        action_id=row[3],
                        action=row[4],
                        status=row[5],
                        risk_score=row[6],
                        trust_tier=row[7],
                        trust_trajectory=row[8],
                        context=json.loads(row[9]),
                        submitted_at=datetime.fromisoformat(row[10]),
                        reviewed_at=datetime.fromisoformat(row[11]) if row[11] else None,
                        reviewer=row[12],
                        reason=row[13],
                        timeout_at=datetime.fromisoformat(row[14]),
                        submitted_by=row[15]
                    )
                    reviews.append(review)

        except Exception as e:
            logger.error(f"Failed to get review history: {e}")

        return reviews

    def _audit_event(
        self,
        conn: sqlite3.Connection,
        review_id: str,
        decision_id: str,
        event_type: str,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        """
        Insert audit event for review action.

        Args:
            conn: Database connection
            review_id: Review identifier
            decision_id: Decision identifier
            event_type: Event type
            actor: Who performed the action
            reason: Reason for action
            details: Additional details
        """
        audit_id = f"audit_{uuid.uuid4().hex[:12]}"

        conn.execute("""
            INSERT INTO evolution_review_audit (
                audit_id, review_id, decision_id, event_type,
                actor, reason, details, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            audit_id,
            review_id,
            decision_id,
            event_type,
            actor,
            reason,
            json.dumps(details) if details else None,
            utc_now().isoformat()
        ))
