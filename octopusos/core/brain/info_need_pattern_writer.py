"""
InfoNeed Pattern Writer - Write patterns to BrainOS knowledge graph

This module handles writing and querying InfoNeed decision patterns
in BrainOS SQLite database.

Key Operations:
1. Write pattern nodes to database
2. Update pattern statistics incrementally
3. Link patterns to signals
4. Query patterns by various criteria
5. Record pattern evolution history
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentos.core.storage.paths import component_db_path
from agentos.core.time import utc_now_iso
from agentos.core.brain.info_need_pattern_models import (
    DecisionSignalNode,
    EvolutionType,
    InfoNeedPatternNode,
    PatternEvolutionEdge,
    PatternSignalLink,
    PatternType,
    SignalType,
)
from agentos.core.brain.store import sqlite_schema

logger = logging.getLogger(__name__)


class InfoNeedPatternWriter:
    """
    Write and query InfoNeed patterns in BrainOS.

    This class provides the interface to BrainOS knowledge graph
    for pattern storage and retrieval.
    """

    def __init__(self, brain_db_path: Optional[str] = None):
        """
        Initialize pattern writer.

        Args:
            brain_db_path: Path to BrainOS SQLite database.
                          If None, uses brainos component database
        """
        if brain_db_path is None:
            # Use brainos component database
            self.db_path = None
        else:
            self.db_path = brain_db_path

    def _get_db_path(self) -> str:
        """Get database path (lazy initialization)."""
        if self.db_path is None:
            # Use brainos component database
            self.db_path = str(component_db_path("brainos"))

        return self.db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        db_path = self._get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def write_pattern(self, pattern: InfoNeedPatternNode) -> str:
        """
        Write pattern node to BrainOS.

        Args:
            pattern: InfoNeedPatternNode to write

        Returns:
            pattern_id: Pattern ID

        Raises:
            sqlite3.Error: If database write fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Serialize question features to JSON
            features_json = json.dumps(pattern.question_features)

            cursor.execute(
                """
                INSERT INTO info_need_patterns (
                    pattern_id, pattern_type,
                    question_features, classification_type, confidence_level,
                    occurrence_count, success_count, failure_count,
                    avg_confidence_score, avg_latency_ms, success_rate,
                    first_seen, last_seen, last_updated,
                    pattern_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pattern.pattern_id,
                    pattern.pattern_type.value,
                    features_json,
                    pattern.classification_type,
                    pattern.confidence_level,
                    pattern.occurrence_count,
                    pattern.success_count,
                    pattern.failure_count,
                    pattern.avg_confidence_score,
                    pattern.avg_latency_ms,
                    pattern.success_rate,
                    pattern.first_seen.isoformat(),
                    pattern.last_seen.isoformat(),
                    pattern.last_updated.isoformat(),
                    pattern.pattern_version,
                ),
            )

            conn.commit()
            conn.close()

            logger.info(f"Wrote pattern {pattern.pattern_id} to BrainOS")
            return pattern.pattern_id

        except Exception as e:
            logger.error(f"Failed to write pattern to BrainOS: {e}")
            raise

    async def update_pattern_statistics(
        self,
        pattern_id: str,
        success: bool,
        confidence_score: float,
        latency_ms: float,
    ) -> None:
        """
        Update pattern statistics incrementally.

        Args:
            pattern_id: Pattern ID to update
            success: Whether judgment was successful
            confidence_score: LLM confidence score
            latency_ms: Decision latency

        Raises:
            ValueError: If pattern_id not found
            sqlite3.Error: If database update fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Fetch current pattern
            cursor.execute(
                "SELECT * FROM info_need_patterns WHERE pattern_id = ?",
                (pattern_id,)
            )
            row = cursor.fetchone()

            if not row:
                raise ValueError(f"Pattern not found: {pattern_id}")

            # Parse current values
            n = row["occurrence_count"]
            old_avg_conf = row["avg_confidence_score"]
            old_avg_lat = row["avg_latency_ms"]
            success_count = row["success_count"]
            failure_count = row["failure_count"]

            # Calculate new values
            n_new = n + 1
            new_avg_conf = (old_avg_conf * n + confidence_score) / n_new
            new_avg_lat = (old_avg_lat * n + latency_ms) / n_new

            if success:
                success_count += 1
            else:
                failure_count += 1

            success_rate = success_count / n_new if n_new > 0 else 0.0

            # Update database
            cursor.execute(
                """
                UPDATE info_need_patterns
                SET occurrence_count = ?,
                    success_count = ?,
                    failure_count = ?,
                    avg_confidence_score = ?,
                    avg_latency_ms = ?,
                    success_rate = ?,
                    last_seen = ?,
                    last_updated = ?
                WHERE pattern_id = ?
                """,
                (
                    n_new,
                    success_count,
                    failure_count,
                    new_avg_conf,
                    new_avg_lat,
                    success_rate,
                    utc_now_iso(),
                    utc_now_iso(),
                    pattern_id,
                ),
            )

            conn.commit()
            conn.close()

            logger.info(f"Updated pattern {pattern_id} statistics")

        except Exception as e:
            logger.error(f"Failed to update pattern statistics: {e}")
            raise

    async def link_pattern_to_signals(
        self,
        pattern_id: str,
        signal_ids: List[str],
        weights: Optional[List[float]] = None,
    ) -> None:
        """
        Link pattern to decision signals.

        Args:
            pattern_id: Pattern ID
            signal_ids: List of signal IDs
            weights: Optional list of weights (parallel to signal_ids)

        Raises:
            sqlite3.Error: If database write fails
        """
        if weights is None:
            weights = [1.0] * len(signal_ids)

        if len(signal_ids) != len(weights):
            raise ValueError("signal_ids and weights must have same length")

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            for signal_id, weight in zip(signal_ids, weights):
                link = PatternSignalLink(
                    pattern_id=pattern_id,
                    signal_id=signal_id,
                    weight=weight,
                )

                cursor.execute(
                    """
                    INSERT INTO pattern_signal_links (
                        link_id, pattern_id, signal_id, weight
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (link.link_id, link.pattern_id, link.signal_id, link.weight),
                )

            conn.commit()
            conn.close()

            logger.info(f"Linked pattern {pattern_id} to {len(signal_ids)} signals")

        except Exception as e:
            logger.error(f"Failed to link pattern to signals: {e}")
            raise

    async def query_patterns(
        self,
        classification_type: Optional[str] = None,
        min_confidence: float = 0.0,
        min_occurrences: int = 0,
        min_success_rate: float = 0.0,
        limit: int = 100,
    ) -> List[InfoNeedPatternNode]:
        """
        Query patterns by criteria.

        Args:
            classification_type: Optional filter by classification type
            min_confidence: Minimum average confidence score
            min_occurrences: Minimum occurrence count
            min_success_rate: Minimum success rate
            limit: Maximum results to return

        Returns:
            List of InfoNeedPatternNode instances

        Raises:
            sqlite3.Error: If database query fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Build query
            query = "SELECT * FROM info_need_patterns WHERE 1=1"
            params: List[Any] = []

            if classification_type:
                query += " AND classification_type = ?"
                params.append(classification_type)

            if min_confidence > 0.0:
                query += " AND avg_confidence_score >= ?"
                params.append(min_confidence)

            if min_occurrences > 0:
                query += " AND occurrence_count >= ?"
                params.append(min_occurrences)

            if min_success_rate > 0.0:
                query += " AND success_rate >= ?"
                params.append(min_success_rate)

            query += " ORDER BY occurrence_count DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Convert to InfoNeedPatternNode objects
            patterns = []
            for row in rows:
                pattern_dict = self._row_to_dict(row)
                patterns.append(InfoNeedPatternNode.from_dict(pattern_dict))

            conn.close()

            logger.info(f"Queried {len(patterns)} patterns")
            return patterns

        except Exception as e:
            logger.error(f"Failed to query patterns: {e}")
            raise

    async def get_pattern_by_id(self, pattern_id: str) -> Optional[InfoNeedPatternNode]:
        """
        Get pattern by ID.

        Args:
            pattern_id: Pattern ID

        Returns:
            InfoNeedPatternNode if found, None otherwise

        Raises:
            sqlite3.Error: If database query fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM info_need_patterns WHERE pattern_id = ?",
                (pattern_id,)
            )
            row = cursor.fetchone()

            conn.close()

            if not row:
                return None

            pattern_dict = self._row_to_dict(row)
            return InfoNeedPatternNode.from_dict(pattern_dict)

        except Exception as e:
            logger.error(f"Failed to get pattern by ID: {e}")
            raise

    async def evolve_pattern(
        self,
        old_pattern_id: str,
        new_pattern: InfoNeedPatternNode,
        evolution_type: str,
        reason: str,
        triggered_by: Optional[str] = None,
    ) -> str:
        """
        Record pattern evolution.

        Args:
            old_pattern_id: Old pattern ID
            new_pattern: New pattern node
            evolution_type: Type of evolution (refined/split/merged/deprecated)
            reason: Reason for evolution
            triggered_by: What triggered the evolution

        Returns:
            New pattern ID

        Raises:
            sqlite3.Error: If database write fails
        """
        try:
            # Write new pattern
            new_pattern_id = await self.write_pattern(new_pattern)

            # Record evolution edge
            edge = PatternEvolutionEdge(
                from_pattern_id=old_pattern_id,
                to_pattern_id=new_pattern_id,
                evolution_type=EvolutionType(evolution_type),
                reason=reason,
                triggered_by=triggered_by,
            )

            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO pattern_evolution (
                    evolution_id, from_pattern_id, to_pattern_id,
                    evolution_type, reason, timestamp, triggered_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.evolution_id,
                    edge.from_pattern_id,
                    edge.to_pattern_id,
                    edge.evolution_type.value,
                    edge.reason,
                    edge.timestamp.isoformat(),
                    edge.triggered_by,
                ),
            )

            conn.commit()
            conn.close()

            logger.info(
                f"Recorded pattern evolution: {old_pattern_id} -> {new_pattern_id} "
                f"({evolution_type})"
            )

            return new_pattern_id

        except Exception as e:
            logger.error(f"Failed to record pattern evolution: {e}")
            raise

    async def write_signal(self, signal: DecisionSignalNode) -> str:
        """
        Write decision signal to BrainOS.

        Args:
            signal: DecisionSignalNode to write

        Returns:
            signal_id: Signal ID

        Raises:
            sqlite3.Error: If database write fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO decision_signals (
                    signal_id, signal_type, signal_value,
                    effectiveness_score,
                    true_positive_count, false_positive_count,
                    true_negative_count, false_negative_count,
                    created_at, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.signal_id,
                    signal.signal_type.value,
                    signal.signal_value,
                    signal.effectiveness_score,
                    signal.true_positive_count,
                    signal.false_positive_count,
                    signal.true_negative_count,
                    signal.false_negative_count,
                    signal.created_at.isoformat(),
                    signal.last_updated.isoformat(),
                ),
            )

            conn.commit()
            conn.close()

            logger.info(f"Wrote signal {signal.signal_id} to BrainOS")
            return signal.signal_id

        except Exception as e:
            logger.error(f"Failed to write signal to BrainOS: {e}")
            raise

    async def cleanup_low_quality_patterns(
        self,
        min_occurrences: int = 5,
        min_success_rate: float = 0.3,
    ) -> int:
        """
        Clean up low-quality patterns.

        Args:
            min_occurrences: Minimum occurrence threshold
            min_success_rate: Minimum success rate threshold

        Returns:
            Number of patterns deleted

        Raises:
            sqlite3.Error: If database delete fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM info_need_patterns
                WHERE occurrence_count < ? OR success_rate < ?
                """,
                (min_occurrences, min_success_rate),
            )

            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(f"Cleaned up {deleted_count} low-quality patterns")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup patterns: {e}")
            raise

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """
        Convert database row to dictionary.

        Args:
            row: SQLite row object

        Returns:
            Dictionary representation
        """
        return {
            "pattern_id": row["pattern_id"],
            "pattern_type": row["pattern_type"],
            "question_features": json.loads(row["question_features"]),
            "classification_type": row["classification_type"],
            "confidence_level": row["confidence_level"],
            "occurrence_count": row["occurrence_count"],
            "success_count": row["success_count"],
            "failure_count": row["failure_count"],
            "avg_confidence_score": row["avg_confidence_score"],
            "avg_latency_ms": row["avg_latency_ms"],
            "success_rate": row["success_rate"],
            "first_seen": row["first_seen"],
            "last_seen": row["last_seen"],
            "last_updated": row["last_updated"],
            "pattern_version": row["pattern_version"],
        }
