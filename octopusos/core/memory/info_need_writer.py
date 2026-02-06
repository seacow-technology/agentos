"""
InfoNeed Memory Writer - Write judgment history to MemoryOS

This module implements the writer for InfoNeed classification judgments,
providing structured storage for pattern recognition and system evolution.

Key Features:
- Async non-blocking writes
- Deduplication detection
- Outcome feedback updates
- Time-range queries
- TTL-based cleanup
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from agentos.core.db import registry_db
from agentos.core.time import utc_now, utc_now_iso
from agentos.core.memory.schema import (
    InfoNeedJudgment,
    JudgmentQuery,
    JudgmentOutcome,
    InfoNeedType,
    ConfidenceLevel,
    DecisionAction,
)

logger = logging.getLogger(__name__)


class InfoNeedMemoryWriter:
    """
    Write InfoNeed judgments to MemoryOS.

    This class provides methods to:
    - Write new judgment records
    - Update judgment outcomes (user feedback)
    - Query recent judgment history
    - Find similar judgments for deduplication
    - Clean up old judgments (TTL)
    """

    def __init__(self, ttl_days: int = 30):
        """
        Initialize InfoNeed memory writer.

        Args:
            ttl_days: Time-to-live in days (default 30)
        """
        self.ttl_days = ttl_days

    async def write_judgment(
        self,
        classification_result: Any,
        session_id: str,
        message_id: str,
        question_text: str,
        phase: str = "planning",
        mode: Optional[str] = None,
        trust_tier: Optional[str] = None,
        latency_ms: float = 0.0,
    ) -> str:
        """
        Write judgment record to MemoryOS.

        Args:
            classification_result: ClassificationResult from InfoNeedClassifier
            session_id: Session ID
            message_id: Message ID for correlation
            question_text: Original user question
            phase: Current phase (planning/execution)
            mode: Current mode (conversation/task/automation)
            trust_tier: Trust tier if external info accessed
            latency_ms: Classification latency in milliseconds

        Returns:
            judgment_id: Unique identifier for this judgment

        Raises:
            ValueError: If required fields are missing
            sqlite3.Error: If database write fails
        """
        # Generate judgment ID
        judgment_id = str(uuid.uuid4())

        # Create question hash for deduplication
        question_hash = InfoNeedJudgment.create_question_hash(question_text)

        # Extract rule signals
        rule_signals = {}
        if hasattr(classification_result, 'rule_signals'):
            rule_signals = classification_result.rule_signals.to_dict()

        # Extract LLM confidence score
        llm_confidence_score = 0.0
        if hasattr(classification_result, 'llm_confidence') and classification_result.llm_confidence:
            # Map confidence level to numeric score
            confidence_map = {
                "high": 0.9,
                "medium": 0.6,
                "low": 0.3,
            }
            llm_confidence_score = confidence_map.get(
                classification_result.llm_confidence.confidence.value, 0.5
            )

        # Create judgment record
        judgment = InfoNeedJudgment(
            judgment_id=judgment_id,
            timestamp=utc_now(),
            session_id=session_id,
            message_id=message_id,
            question_text=question_text,
            question_hash=question_hash,
            classified_type=InfoNeedType(classification_result.info_need_type.value),
            confidence_level=ConfidenceLevel(classification_result.confidence_level.value),
            decision_action=DecisionAction(classification_result.decision_action.value),
            rule_signals=rule_signals,
            llm_confidence_score=llm_confidence_score,
            decision_latency_ms=latency_ms,
            outcome=JudgmentOutcome.PENDING,
            phase=phase,
            mode=mode,
            trust_tier=trust_tier,
        )

        # Write to database
        try:
            conn = registry_db.get_db()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO info_need_judgments (
                    judgment_id, timestamp, session_id, message_id,
                    question_text, question_hash,
                    classified_type, confidence_level, decision_action,
                    rule_signals, llm_confidence_score, decision_latency_ms,
                    outcome, user_action, outcome_timestamp,
                    phase, mode, trust_tier
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    judgment.judgment_id,
                    judgment.timestamp.isoformat(),
                    judgment.session_id,
                    judgment.message_id,
                    judgment.question_text,
                    judgment.question_hash,
                    judgment.classified_type.value,
                    judgment.confidence_level.value,
                    judgment.decision_action.value,
                    json.dumps(judgment.rule_signals),
                    judgment.llm_confidence_score,
                    judgment.decision_latency_ms,
                    judgment.outcome.value,
                    judgment.user_action,
                    judgment.outcome_timestamp.isoformat() if judgment.outcome_timestamp else None,
                    judgment.phase,
                    judgment.mode,
                    judgment.trust_tier,
                ),
            )

            conn.commit()
            logger.info(f"Wrote judgment {judgment_id} to MemoryOS")
            return judgment_id

        except Exception as e:
            logger.error(f"Failed to write judgment to MemoryOS: {e}")
            raise

    async def update_judgment_outcome(
        self,
        judgment_id: str,
        outcome: str,
        user_action: Optional[str] = None,
    ) -> None:
        """
        Update judgment outcome (user feedback).

        Args:
            judgment_id: Judgment ID to update
            outcome: Outcome value (user_proceeded/user_declined/system_fallback)
            user_action: Optional specific user action taken

        Raises:
            ValueError: If judgment_id not found or outcome invalid
            sqlite3.Error: If database update fails
        """
        # Validate outcome
        try:
            outcome_enum = JudgmentOutcome(outcome)
        except ValueError:
            raise ValueError(
                f"Invalid outcome: {outcome}. Must be one of: "
                f"{', '.join(o.value for o in JudgmentOutcome)}"
            )

        # Update database
        try:
            conn = registry_db.get_db()
            cursor = conn.cursor()

            outcome_timestamp = utc_now_iso()

            cursor.execute(
                """
                UPDATE info_need_judgments
                SET outcome = ?,
                    user_action = ?,
                    outcome_timestamp = ?
                WHERE judgment_id = ?
                """,
                (outcome_enum.value, user_action, outcome_timestamp, judgment_id),
            )

            if cursor.rowcount == 0:
                raise ValueError(f"Judgment not found: {judgment_id}")

            conn.commit()
            logger.info(f"Updated judgment {judgment_id} outcome: {outcome}")

        except Exception as e:
            logger.error(f"Failed to update judgment outcome: {e}")
            raise

    async def update_judgment_outcome_by_message_id(
        self,
        message_id: str,
        outcome: str,
        user_action: Optional[str] = None,
    ) -> bool:
        """
        Update judgment outcome by message ID.

        This is a convenience method for when you have the message_id
        but not the judgment_id.

        Args:
            message_id: Message ID to look up
            outcome: Outcome value
            user_action: Optional specific user action taken

        Returns:
            True if judgment was found and updated, False otherwise

        Raises:
            ValueError: If outcome invalid
            sqlite3.Error: If database update fails
        """
        # Validate outcome
        try:
            outcome_enum = JudgmentOutcome(outcome)
        except ValueError:
            raise ValueError(
                f"Invalid outcome: {outcome}. Must be one of: "
                f"{', '.join(o.value for o in JudgmentOutcome)}"
            )

        try:
            conn = registry_db.get_db()
            cursor = conn.cursor()

            outcome_timestamp = utc_now_iso()

            cursor.execute(
                """
                UPDATE info_need_judgments
                SET outcome = ?,
                    user_action = ?,
                    outcome_timestamp = ?
                WHERE message_id = ?
                """,
                (outcome_enum.value, user_action, outcome_timestamp, message_id),
            )

            if cursor.rowcount == 0:
                logger.warning(f"No judgment found for message_id: {message_id}")
                return False

            conn.commit()
            logger.info(f"Updated judgment for message {message_id} outcome: {outcome}")
            return True

        except Exception as e:
            logger.error(f"Failed to update judgment outcome by message_id: {e}")
            raise

    async def query_recent_judgments(
        self,
        session_id: Optional[str] = None,
        time_range: str = "24h",
        limit: int = 100,
        classified_type: Optional[str] = None,
        outcome: Optional[str] = None,
    ) -> List[InfoNeedJudgment]:
        """
        Query recent judgment history.

        Args:
            session_id: Optional filter by session ID
            time_range: Time range (e.g., "24h", "7d", "30d")
            limit: Maximum results to return
            classified_type: Optional filter by classified type
            outcome: Optional filter by outcome

        Returns:
            List of InfoNeedJudgment records, newest first

        Raises:
            ValueError: If time_range format invalid
            sqlite3.Error: If database query fails
        """
        # Parse time range
        time_hours = self._parse_time_range(time_range)
        cutoff_time = utc_now() - timedelta(hours=time_hours)

        try:
            conn = registry_db.get_db()
            cursor = conn.cursor()

            # Build query
            query = """
                SELECT * FROM info_need_judgments
                WHERE timestamp >= ?
            """
            params: List[Any] = [cutoff_time.isoformat()]

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            if classified_type:
                query += " AND classified_type = ?"
                params.append(classified_type)

            if outcome:
                query += " AND outcome = ?"
                params.append(outcome)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Convert to InfoNeedJudgment objects
            judgments = []
            for row in rows:
                judgment_dict = self._row_to_dict(row)
                judgments.append(InfoNeedJudgment.from_dict(judgment_dict))

            logger.info(f"Queried {len(judgments)} recent judgments")
            return judgments

        except Exception as e:
            logger.error(f"Failed to query recent judgments: {e}")
            raise

    async def find_similar_judgment(
        self,
        question_hash: str,
        time_window: timedelta = timedelta(hours=24),
    ) -> Optional[InfoNeedJudgment]:
        """
        Find similar judgment by question hash (for deduplication).

        Args:
            question_hash: Question hash to search for
            time_window: Time window to search within (default 24 hours)

        Returns:
            Most recent matching judgment, or None if not found

        Raises:
            sqlite3.Error: If database query fails
        """
        cutoff_time = utc_now() - time_window

        try:
            conn = registry_db.get_db()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM info_need_judgments
                WHERE question_hash = ?
                  AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (question_hash, cutoff_time.isoformat()),
            )

            row = cursor.fetchone()
            if not row:
                return None

            judgment_dict = self._row_to_dict(row)
            return InfoNeedJudgment.from_dict(judgment_dict)

        except Exception as e:
            logger.error(f"Failed to find similar judgment: {e}")
            raise

    async def cleanup_old_judgments(self) -> int:
        """
        Clean up old judgments based on TTL.

        Returns:
            Number of judgments deleted

        Raises:
            sqlite3.Error: If database delete fails
        """
        cutoff_time = utc_now() - timedelta(days=self.ttl_days)

        try:
            conn = registry_db.get_db()
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM info_need_judgments
                WHERE timestamp < ?
                """,
                (cutoff_time.isoformat(),),
            )

            deleted_count = cursor.rowcount
            conn.commit()

            logger.info(f"Cleaned up {deleted_count} old judgments (TTL: {self.ttl_days} days)")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old judgments: {e}")
            raise

    async def get_judgment_by_id(self, judgment_id: str) -> Optional[InfoNeedJudgment]:
        """
        Get judgment by ID.

        Args:
            judgment_id: Judgment ID to retrieve

        Returns:
            InfoNeedJudgment if found, None otherwise

        Raises:
            sqlite3.Error: If database query fails
        """
        try:
            conn = registry_db.get_db()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM info_need_judgments
                WHERE judgment_id = ?
                """,
                (judgment_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            judgment_dict = self._row_to_dict(row)
            return InfoNeedJudgment.from_dict(judgment_dict)

        except Exception as e:
            logger.error(f"Failed to get judgment by ID: {e}")
            raise

    async def get_judgment_stats(
        self,
        session_id: Optional[str] = None,
        time_range: str = "24h",
    ) -> Dict[str, Any]:
        """
        Get judgment statistics.

        Args:
            session_id: Optional filter by session ID
            time_range: Time range for stats

        Returns:
            Dictionary with statistics:
            - total_judgments: Total count
            - by_type: Count by classified type
            - by_action: Count by decision action
            - by_outcome: Count by outcome
            - avg_latency_ms: Average decision latency

        Raises:
            sqlite3.Error: If database query fails
        """
        time_hours = self._parse_time_range(time_range)
        cutoff_time = utc_now() - timedelta(hours=time_hours)

        try:
            conn = registry_db.get_db()
            cursor = conn.cursor()

            # Build base query
            base_query = "FROM info_need_judgments WHERE timestamp >= ?"
            params: List[Any] = [cutoff_time.isoformat()]

            if session_id:
                base_query += " AND session_id = ?"
                params.append(session_id)

            # Total count
            cursor.execute(f"SELECT COUNT(*) {base_query}", params)
            total_judgments = cursor.fetchone()[0]

            # By type
            cursor.execute(
                f"SELECT classified_type, COUNT(*) {base_query} GROUP BY classified_type",
                params
            )
            by_type = {row[0]: row[1] for row in cursor.fetchall()}

            # By action
            cursor.execute(
                f"SELECT decision_action, COUNT(*) {base_query} GROUP BY decision_action",
                params
            )
            by_action = {row[0]: row[1] for row in cursor.fetchall()}

            # By outcome
            cursor.execute(
                f"SELECT outcome, COUNT(*) {base_query} GROUP BY outcome",
                params
            )
            by_outcome = {row[0]: row[1] for row in cursor.fetchall()}

            # Average latency
            cursor.execute(
                f"SELECT AVG(decision_latency_ms) {base_query}",
                params
            )
            avg_latency_ms = cursor.fetchone()[0] or 0.0

            return {
                "total_judgments": total_judgments,
                "by_type": by_type,
                "by_action": by_action,
                "by_outcome": by_outcome,
                "avg_latency_ms": avg_latency_ms,
                "time_range": time_range,
                "session_id": session_id,
            }

        except Exception as e:
            logger.error(f"Failed to get judgment stats: {e}")
            raise

    def _parse_time_range(self, time_range: str) -> int:
        """
        Parse time range string to hours.

        Args:
            time_range: Time range string (e.g., "24h", "7d", "30d")

        Returns:
            Hours as integer

        Raises:
            ValueError: If format invalid
        """
        time_range = time_range.strip().lower()

        if time_range.endswith('h'):
            return int(time_range[:-1])
        elif time_range.endswith('d'):
            return int(time_range[:-1]) * 24
        elif time_range.endswith('w'):
            return int(time_range[:-1]) * 24 * 7
        else:
            raise ValueError(
                f"Invalid time range format: {time_range}. "
                f"Use format like '24h', '7d', or '2w'"
            )

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """
        Convert database row to dictionary.

        Args:
            row: SQLite row object

        Returns:
            Dictionary representation
        """
        return {
            "judgment_id": row["judgment_id"],
            "timestamp": row["timestamp"],
            "session_id": row["session_id"],
            "message_id": row["message_id"],
            "question_text": row["question_text"],
            "question_hash": row["question_hash"],
            "classified_type": row["classified_type"],
            "confidence_level": row["confidence_level"],
            "decision_action": row["decision_action"],
            "rule_signals": json.loads(row["rule_signals"]),
            "llm_confidence_score": row["llm_confidence_score"],
            "decision_latency_ms": row["decision_latency_ms"],
            "outcome": row["outcome"],
            "user_action": row["user_action"],
            "outcome_timestamp": row["outcome_timestamp"],
            "phase": row["phase"],
            "mode": row["mode"],
            "trust_tier": row["trust_tier"],
        }


# Convenience function for quick writes
async def write_classification_judgment(
    classification_result: Any,
    session_id: str,
    message_id: str,
    question_text: str,
    **kwargs
) -> str:
    """
    Convenience function to write a judgment.

    Args:
        classification_result: ClassificationResult from InfoNeedClassifier
        session_id: Session ID
        message_id: Message ID
        question_text: Original question
        **kwargs: Additional arguments for write_judgment()

    Returns:
        judgment_id
    """
    writer = InfoNeedMemoryWriter()
    return await writer.write_judgment(
        classification_result,
        session_id,
        message_id,
        question_text,
        **kwargs
    )
