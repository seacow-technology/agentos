"""SQLite storage backend for communication evidence.

This module provides a SQLite-based storage implementation
for persisting communication audit logs and evidence.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from agentos.core.storage.paths import component_db_path
from agentos.core.time import utc_now
from agentos.core.communication.models import (
    EvidenceRecord,
    ConnectorType,
    RequestStatus,
)

logger = logging.getLogger(__name__)


class SQLiteStore:
    """SQLite storage for communication evidence.

    Provides persistent storage for audit evidence with
    efficient querying and retrieval capabilities.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize SQLite store.

        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            db_path = component_db_path("communicationos")

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection.

        Returns:
            SQLite connection
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create evidence table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL,
                connector_type TEXT NOT NULL,
                operation TEXT NOT NULL,
                request_summary TEXT NOT NULL,
                response_summary TEXT,
                status TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(request_id)
            )
        """)

        # Create indexes for efficient querying
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_evidence_connector_type
            ON evidence(connector_type)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_evidence_operation
            ON evidence(operation)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_evidence_status
            ON evidence(status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_evidence_created_at
            ON evidence(created_at)
        """)

        # Create network_mode_state table (created here for shared database)
        # Note: NetworkModeManager also creates these tables, but we ensure
        # they exist when the store is initialized for consistency
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS network_mode_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                mode TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS network_mode_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                previous_mode TEXT,
                new_mode TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                changed_by TEXT,
                reason TEXT,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_network_mode_history_changed_at
            ON network_mode_history(changed_at DESC)
        """)

        conn.commit()
        conn.close()
        logger.info(f"Initialized SQLite store at: {self.db_path}")

    async def save_evidence(self, evidence: EvidenceRecord) -> None:
        """Save evidence record.

        Args:
            evidence: Evidence record to save
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO evidence
                (id, request_id, connector_type, operation, request_summary,
                 response_summary, status, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    response_summary = excluded.response_summary,
                    status = excluded.status,
                    metadata = excluded.metadata
                """,
                (
                    evidence.id,
                    evidence.request_id,
                    evidence.connector_type.value,
                    evidence.operation,
                    json.dumps(evidence.request_summary),
                    json.dumps(evidence.response_summary) if evidence.response_summary else None,
                    evidence.status.value,
                    json.dumps(evidence.metadata),
                    evidence.created_at.isoformat(),
                ),
            )
            conn.commit()
            logger.debug(f"Saved evidence: {evidence.id}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save evidence: {str(e)}")
            raise
        finally:
            conn.close()

    async def get_evidence(self, evidence_id: str) -> Optional[EvidenceRecord]:
        """Get evidence by ID.

        Args:
            evidence_id: Evidence ID

        Returns:
            Evidence record if found, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_evidence(row)

    async def get_evidence_by_request(self, request_id: str) -> Optional[EvidenceRecord]:
        """Get evidence by request ID.

        Args:
            request_id: Request ID

        Returns:
            Evidence record if found, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM evidence WHERE request_id = ?", (request_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_evidence(row)

    async def search_evidence(
        self,
        connector_type: Optional[str] = None,
        operation: Optional[str] = None,
        status: Optional[RequestStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[EvidenceRecord]:
        """Search evidence records.

        Args:
            connector_type: Filter by connector type
            operation: Filter by operation
            status: Filter by status
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of records

        Returns:
            List of evidence records
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM evidence WHERE 1=1"
        params = []

        if connector_type:
            query += " AND connector_type = ?"
            params.append(connector_type)

        if operation:
            query += " AND operation = ?"
            params.append(operation)

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date.isoformat())

        if end_date:
            query += " AND created_at <= ?"
            params.append(end_date.isoformat())

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_evidence(row) for row in rows]

    async def get_total_count(self) -> int:
        """Get total evidence count.

        Returns:
            Total count
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM evidence")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    async def get_count_by_status(self, status: RequestStatus) -> int:
        """Get count by status.

        Args:
            status: Request status

        Returns:
            Count
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM evidence WHERE status = ?", (status.value,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    async def get_stats_by_connector(self) -> Dict[str, int]:
        """Get statistics by connector type.

        Returns:
            Dictionary mapping connector types to counts
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT connector_type, COUNT(*) as count
            FROM evidence
            GROUP BY connector_type
        """)
        rows = cursor.fetchall()
        conn.close()

        return {row["connector_type"]: row["count"] for row in rows}

    def _row_to_evidence(self, row: sqlite3.Row) -> EvidenceRecord:
        """Convert database row to evidence record.

        Args:
            row: Database row

        Returns:
            Evidence record
        """
        return EvidenceRecord(
            id=row["id"],
            request_id=row["request_id"],
            connector_type=ConnectorType(row["connector_type"]),
            operation=row["operation"],
            request_summary=json.loads(row["request_summary"]),
            response_summary=json.loads(row["response_summary"]) if row["response_summary"] else None,
            status=RequestStatus(row["status"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    async def clear_old_evidence(self, days: int = 90) -> int:
        """Clear evidence older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of records deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff = utc_now()
        cutoff = cutoff.replace(day=cutoff.day - days)

        cursor.execute(
            "DELETE FROM evidence WHERE created_at < ?",
            (cutoff.isoformat(),)
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Cleared {deleted} old evidence records")
        return deleted
