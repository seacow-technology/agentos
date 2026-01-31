"""
DecisionCandidate Storage Service

Provides storage and query operations for DecisionCandidate and DecisionSet data.
Uses unified database access through registry_db.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any

from agentos.core.db import registry_db
from agentos.core.chat.models.decision_candidate import (
    DecisionCandidate,
    DecisionSet,
    ClassifierVersion,
    DecisionRole,
    validate_shadow_isolation,
)

logger = logging.getLogger(__name__)


class DecisionCandidateStore:
    """Storage service for DecisionCandidate and DecisionSet.

    Provides CRUD operations and querying capabilities for decision data.
    Ensures shadow isolation constraints are enforced at storage layer.
    """

    def __init__(self):
        """Initialize the store."""
        pass

    async def save_classifier_version(self, version: ClassifierVersion) -> None:
        """Save or update classifier version.

        Args:
            version: ClassifierVersion to save
        """
        sql = """
        INSERT INTO classifier_versions (
            version_id, version_type, change_description,
            created_at, metadata
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(version_id) DO UPDATE SET
            version_type = excluded.version_type,
            change_description = excluded.change_description
        """

        with registry_db.transaction() as conn:
            conn.execute(
                sql,
                (
                    version.version_id,
                    version.version_type,
                    version.change_description,
                    version.created_at.isoformat(),
                    json.dumps({}),  # metadata
                ),
            )

        logger.info(f"Saved classifier version: {version.version_id}")

    async def get_classifier_version(self, version_id: str) -> Optional[ClassifierVersion]:
        """Get classifier version by ID.

        Args:
            version_id: Version ID to retrieve

        Returns:
            ClassifierVersion if found, None otherwise
        """
        sql = """
        SELECT version_id, version_type, change_description, created_at
        FROM classifier_versions
        WHERE version_id = ?
        """

        row = registry_db.query_one(sql, (version_id,))
        if not row:
            return None

        return ClassifierVersion(
            version_id=row["version_id"],
            version_type=row["version_type"],
            change_description=row["change_description"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    async def save_decision_set(self, decision_set: DecisionSet) -> None:
        """Save decision set (active + shadow decisions).

        Validates shadow isolation constraints before saving.

        Args:
            decision_set: DecisionSet to save

        Raises:
            AssertionError: If shadow isolation constraints are violated
        """
        # Validate shadow isolation
        validate_shadow_isolation(decision_set)

        with registry_db.transaction() as conn:
            # Save active decision candidate
            self._insert_candidate(conn, decision_set.active_decision, decision_set.decision_set_id)

            # Save shadow decision candidates
            for shadow in decision_set.shadow_decisions:
                self._insert_candidate(conn, shadow, decision_set.decision_set_id)

            # Save decision set
            conn.execute(
                """
                INSERT INTO decision_sets (
                    decision_set_id, message_id, session_id,
                    question_text, question_hash,
                    active_candidate_id, timestamp, context_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_set.decision_set_id,
                    decision_set.message_id,
                    decision_set.session_id,
                    decision_set.question_text,
                    decision_set.question_hash,
                    decision_set.active_decision.candidate_id,
                    decision_set.timestamp.isoformat(),
                    json.dumps(decision_set.context_snapshot),
                ),
            )

        logger.info(
            f"Saved decision set {decision_set.decision_set_id} "
            f"with {len(decision_set.shadow_decisions)} shadow decisions"
        )

    def _insert_candidate(
        self, conn, candidate: DecisionCandidate, decision_set_id: str
    ) -> None:
        """Insert a decision candidate into database.

        Args:
            conn: Database connection
            candidate: DecisionCandidate to insert
            decision_set_id: ID of parent decision set
        """
        conn.execute(
            """
            INSERT INTO decision_candidates (
                candidate_id, decision_role, version_id,
                question_text, question_hash, context, phase, mode,
                info_need_type, confidence_level, decision_action, reason_codes,
                rule_signals, llm_confidence_score,
                timestamp, message_id, session_id, decision_set_id,
                shadow_metadata, latency_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.candidate_id,
                candidate.decision_role.value,
                candidate.classifier_version.version_id,
                candidate.question_text,
                candidate.question_hash,
                json.dumps(candidate.context),
                candidate.phase,
                candidate.mode,
                candidate.info_need_type,
                candidate.confidence_level,
                candidate.decision_action,
                json.dumps(candidate.reason_codes),
                json.dumps(candidate.rule_signals),
                candidate.llm_confidence_score,
                candidate.timestamp.isoformat(),
                candidate.message_id,
                candidate.session_id,
                decision_set_id,
                json.dumps(candidate.shadow_metadata) if candidate.shadow_metadata else None,
                candidate.latency_ms,
            ),
        )

    async def get_decision_set(self, decision_set_id: str) -> Optional[DecisionSet]:
        """Get decision set by ID.

        Args:
            decision_set_id: Decision set ID

        Returns:
            DecisionSet if found, None otherwise
        """
        # Get decision set metadata
        set_row = registry_db.query_one(
            """
            SELECT decision_set_id, message_id, session_id,
                   question_text, question_hash,
                   active_candidate_id, timestamp, context_snapshot
            FROM decision_sets
            WHERE decision_set_id = ?
            """,
            (decision_set_id,),
        )

        if not set_row:
            return None

        # Get all candidates for this set
        candidate_rows = registry_db.query_all(
            """
            SELECT candidate_id, decision_role, version_id,
                   question_text, question_hash, context, phase, mode,
                   info_need_type, confidence_level, decision_action, reason_codes,
                   rule_signals, llm_confidence_score,
                   timestamp, message_id, session_id,
                   shadow_metadata, latency_ms
            FROM decision_candidates
            WHERE decision_set_id = ?
            """,
            (decision_set_id,),
        )

        # Separate active and shadow candidates
        active_candidate = None
        shadow_candidates = []

        for row in candidate_rows:
            candidate = self._row_to_candidate(row)
            if candidate.decision_role == DecisionRole.ACTIVE:
                active_candidate = candidate
            else:
                shadow_candidates.append(candidate)

        if not active_candidate:
            logger.error(f"Decision set {decision_set_id} has no active candidate")
            return None

        return DecisionSet(
            decision_set_id=set_row["decision_set_id"],
            message_id=set_row["message_id"],
            session_id=set_row["session_id"],
            question_text=set_row["question_text"],
            question_hash=set_row["question_hash"],
            active_decision=active_candidate,
            shadow_decisions=shadow_candidates,
            timestamp=datetime.fromisoformat(set_row["timestamp"]),
            context_snapshot=json.loads(set_row["context_snapshot"]),
        )

    def _row_to_candidate(self, row) -> DecisionCandidate:
        """Convert database row to DecisionCandidate.

        Args:
            row: Database row

        Returns:
            DecisionCandidate instance
        """
        # Get classifier version
        version_row = registry_db.query_one(
            "SELECT version_id, version_type, change_description, created_at "
            "FROM classifier_versions WHERE version_id = ?",
            (row["version_id"],),
        )

        classifier_version = ClassifierVersion(
            version_id=version_row["version_id"],
            version_type=version_row["version_type"],
            change_description=version_row["change_description"],
            created_at=datetime.fromisoformat(version_row["created_at"]),
        )

        return DecisionCandidate(
            candidate_id=row["candidate_id"],
            decision_role=DecisionRole(row["decision_role"]),
            classifier_version=classifier_version,
            question_text=row["question_text"],
            question_hash=row["question_hash"],
            context=json.loads(row["context"]),
            phase=row["phase"],
            mode=row["mode"],
            info_need_type=row["info_need_type"],
            confidence_level=row["confidence_level"],
            decision_action=row["decision_action"],
            reason_codes=json.loads(row["reason_codes"]),
            rule_signals=json.loads(row["rule_signals"]),
            llm_confidence_score=row["llm_confidence_score"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            message_id=row["message_id"],
            session_id=row["session_id"],
            shadow_metadata=json.loads(row["shadow_metadata"]) if row["shadow_metadata"] else None,
            latency_ms=row["latency_ms"],
        )

    async def query_decision_sets(
        self,
        session_id: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        has_shadow: bool = False,
        limit: int = 100,
    ) -> List[DecisionSet]:
        """Query decision sets with filters.

        Args:
            session_id: Filter by session ID
            time_range: Filter by timestamp range (start, end)
            has_shadow: If True, only return sets with shadow decisions
            limit: Maximum number of results

        Returns:
            List of DecisionSet instances
        """
        # Build query
        conditions = []
        params = []

        if session_id:
            conditions.append("ds.session_id = ?")
            params.append(session_id)

        if time_range:
            conditions.append("ds.timestamp >= ? AND ds.timestamp <= ?")
            params.extend([time_range[0].isoformat(), time_range[1].isoformat()])

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        # Query decision sets
        sql = f"""
        SELECT ds.decision_set_id
        FROM decision_sets ds
        {where_clause}
        ORDER BY ds.timestamp DESC
        LIMIT ?
        """
        params.append(limit)

        rows = registry_db.query_all(sql, tuple(params))

        # Load full decision sets
        decision_sets = []
        for row in rows:
            decision_set = await self.get_decision_set(row["decision_set_id"])
            if decision_set:
                # Apply has_shadow filter
                if has_shadow and not decision_set.has_shadow_decisions():
                    continue
                decision_sets.append(decision_set)

        return decision_sets

    async def get_shadow_decisions_for_comparison(
        self,
        version_id: str,
        time_range: Tuple[datetime, datetime],
        limit: int = 1000,
    ) -> List[DecisionCandidate]:
        """Get shadow decisions for comparison analysis.

        Args:
            version_id: Classifier version ID to filter
            time_range: Time range (start, end)
            limit: Maximum number of results

        Returns:
            List of shadow DecisionCandidate instances
        """
        sql = """
        SELECT candidate_id, decision_role, version_id,
               question_text, question_hash, context, phase, mode,
               info_need_type, confidence_level, decision_action, reason_codes,
               rule_signals, llm_confidence_score,
               timestamp, message_id, session_id,
               shadow_metadata, latency_ms
        FROM decision_candidates
        WHERE decision_role = 'shadow'
          AND version_id = ?
          AND timestamp >= ?
          AND timestamp <= ?
        ORDER BY timestamp DESC
        LIMIT ?
        """

        rows = registry_db.query_all(
            sql,
            (
                version_id,
                time_range[0].isoformat(),
                time_range[1].isoformat(),
                limit,
            ),
        )

        return [self._row_to_candidate(row) for row in rows]

    async def get_decision_by_message_id(
        self, message_id: str
    ) -> Optional[DecisionSet]:
        """Get decision set by message ID.

        Args:
            message_id: Message ID

        Returns:
            DecisionSet if found, None otherwise
        """
        row = registry_db.query_one(
            "SELECT decision_set_id FROM decision_sets WHERE message_id = ?",
            (message_id,),
        )

        if not row:
            return None

        return await self.get_decision_set(row["decision_set_id"])

    async def count_decisions_by_role(
        self, session_id: Optional[str] = None
    ) -> Dict[str, int]:
        """Count decisions by role.

        Args:
            session_id: Optional session ID filter

        Returns:
            Dictionary with counts: {"active": N, "shadow": M}
        """
        where_clause = ""
        params = []

        if session_id:
            where_clause = "WHERE session_id = ?"
            params.append(session_id)

        sql = f"""
        SELECT decision_role, COUNT(*) as count
        FROM decision_candidates
        {where_clause}
        GROUP BY decision_role
        """

        rows = registry_db.query_all(sql, tuple(params) if params else None)

        result = {"active": 0, "shadow": 0}
        for row in rows:
            result[row["decision_role"]] = row["count"]

        return result


# Singleton instance
_store = DecisionCandidateStore()


def get_store() -> DecisionCandidateStore:
    """Get singleton store instance."""
    return _store
