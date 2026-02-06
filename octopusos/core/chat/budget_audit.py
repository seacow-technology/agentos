"""
Budget Audit API - Query budget snapshots for auditability

P1-7: Budget Snapshot → Audit/TaskDB
Enables full reconstruction of "what budget was in effect" for any model invocation.

Key Features:
- Query snapshot by message_id or task_id
- Extract budget breakdown and threshold state
- Identify truncation risk
- Backward compatibility for old messages/tasks
"""

import json
import sqlite3
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from agentos.store import get_db

logger = logging.getLogger(__name__)


class ThresholdState(Enum):
    """Budget threshold watermarks"""
    SAFE = "safe"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class BudgetSnapshot:
    """Budget snapshot data for audit"""
    snapshot_id: str
    session_id: str
    created_at: int
    reason: str
    provider: Optional[str]
    model: Optional[str]

    # Budget totals
    budget_tokens: int
    total_tokens_est: int

    # Breakdown by source
    tokens_system: int
    tokens_window: int
    tokens_rag: int
    tokens_memory: int
    tokens_summary: int
    tokens_policy: int

    # Composition details
    composition: Dict[str, Any]
    assembled_hash: Optional[str]

    # Threshold state
    usage_ratio: float
    watermark: ThresholdState
    truncation_expected: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "snapshot_id": self.snapshot_id,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "reason": self.reason,
            "provider": self.provider,
            "model": self.model,
            "budget_tokens": self.budget_tokens,
            "total_tokens_est": self.total_tokens_est,
            "breakdown": {
                "system": self.tokens_system,
                "window": self.tokens_window,
                "rag": self.tokens_rag,
                "memory": self.tokens_memory,
                "summary": self.tokens_summary,
                "policy": self.tokens_policy,
            },
            "composition": self.composition,
            "assembled_hash": self.assembled_hash,
            "usage_ratio": self.usage_ratio,
            "watermark": self.watermark.value,
            "truncation_expected": self.truncation_expected,
        }


class BudgetAuditAPI:
    """API for querying budget snapshots"""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize budget audit API

        Args:
            db_path: Optional path to database (defaults to store default)
        """
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection"""
        if self.db_path:
            conn = sqlite3.connect(self.db_path)
        else:
            conn = get_db()
        conn.row_factory = sqlite3.Row
        return conn

    def get_snapshot_by_id(self, snapshot_id: str) -> Optional[BudgetSnapshot]:
        """Get snapshot by snapshot_id

        Args:
            snapshot_id: Snapshot ID

        Returns:
            BudgetSnapshot or None if not found
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM context_snapshots
                WHERE snapshot_id = ?
            """, (snapshot_id,))

            row = cursor.fetchone()
            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

            if not row:
                logger.warning(f"Snapshot {snapshot_id} not found")
                return None

            return self._parse_snapshot(row)

        except Exception as e:
            logger.error(f"Failed to get snapshot: {e}")
            return None

    def get_snapshot_for_message(self, message_id: str) -> Optional[BudgetSnapshot]:
        """Get snapshot associated with a message

        Args:
            message_id: Message ID

        Returns:
            BudgetSnapshot or None if not found or not linked
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            # Get message metadata
            cursor.execute("""
                SELECT metadata FROM chat_messages
                WHERE message_id = ?
            """, (message_id,))

            row = cursor.fetchone()
            if not row:
                logger.warning(f"Message {message_id} not found")
                # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
                if self.db_path:
                    conn.close()
                return None

            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            snapshot_id = metadata.get("context_snapshot_id")

            # Do NOT close: get_db() returns shared thread-local connection (unless db_path provided)
            if self.db_path:
                conn.close()

            if not snapshot_id:
                logger.info(f"Message {message_id} has no linked snapshot (pre-P1-7)")
                return None

            return self.get_snapshot_by_id(snapshot_id)

        except Exception as e:
            logger.error(f"Failed to get snapshot for message: {e}")
            return None

    def get_snapshot_for_task(self, task_id: str) -> Optional[BudgetSnapshot]:
        """Get snapshot associated with a task

        Args:
            task_id: Task ID

        Returns:
            BudgetSnapshot or None if not found or not linked
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            # Get task metadata
            cursor.execute("""
                SELECT metadata FROM tasks
                WHERE task_id = ?
            """, (task_id,))

            row = cursor.fetchone()
            if not row:
                logger.warning(f"Task {task_id} not found")
                # Do NOT close: get_db() returns shared thread-local connection
                return None

            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            snapshot_id = metadata.get("context_snapshot_id")

            # Do NOT close: get_db() returns shared thread-local connection
            # conn.close()  # REMOVED

            if not snapshot_id:
                logger.info(f"Task {task_id} has no linked snapshot (pre-P1-7)")
                return None

            return self.get_snapshot_by_id(snapshot_id)

        except Exception as e:
            logger.error(f"Failed to get snapshot for task: {e}")
            return None

    def _parse_snapshot(self, row: sqlite3.Row) -> BudgetSnapshot:
        """Parse database row into BudgetSnapshot

        Args:
            row: Database row

        Returns:
            BudgetSnapshot object
        """
        # Parse composition JSON
        composition = json.loads(row["composition_json"]) if row["composition_json"] else {}

        # Parse metadata
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        usage_ratio = metadata.get("usage_ratio", 0.0)
        watermark_str = metadata.get("watermark", "safe")

        # Map watermark string to enum
        watermark = ThresholdState.SAFE
        if watermark_str == "warning":
            watermark = ThresholdState.WARNING
        elif watermark_str == "critical":
            watermark = ThresholdState.CRITICAL

        # Determine if truncation is expected (>90% usage)
        truncation_expected = usage_ratio > 0.9

        return BudgetSnapshot(
            snapshot_id=row["snapshot_id"],
            session_id=row["session_id"],
            created_at=row["created_at"],
            reason=row["reason"],
            provider=row["provider"],
            model=row["model"],
            budget_tokens=row["budget_tokens"],
            total_tokens_est=row["total_tokens_est"],
            tokens_system=row["tokens_system"],
            tokens_window=row["tokens_window"],
            tokens_rag=row["tokens_rag"],
            tokens_memory=row["tokens_memory"],
            tokens_summary=row["tokens_summary"],
            tokens_policy=row["tokens_policy"],
            composition=composition,
            assembled_hash=row["assembled_hash"],
            usage_ratio=usage_ratio,
            watermark=watermark,
            truncation_expected=truncation_expected,
        )

    def get_audit_summary(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """Get audit summary for a message or task

        Args:
            entity_type: "message" or "task"
            entity_id: Entity ID

        Returns:
            Audit summary dictionary
        """
        if entity_type == "message":
            snapshot = self.get_snapshot_for_message(entity_id)
        elif entity_type == "task":
            snapshot = self.get_snapshot_for_task(entity_id)
        else:
            return {
                "status": "error",
                "reason": f"Invalid entity_type: {entity_type}"
            }

        if not snapshot:
            return {
                "status": "not_auditable",
                "reason": "no_snapshot_linked",
                "entity_type": entity_type,
                "entity_id": entity_id,
                "note": "This entity was created before P1-7 implementation"
            }

        return {
            "status": "auditable",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "snapshot": snapshot.to_dict()
        }


# Convenience functions
def get_budget_for_message(message_id: str) -> Optional[Dict[str, Any]]:
    """Get budget audit for a message

    Args:
        message_id: Message ID

    Returns:
        Audit summary dictionary
    """
    api = BudgetAuditAPI()
    return api.get_audit_summary("message", message_id)


def get_budget_for_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Get budget audit for a task

    Args:
        task_id: Task ID

    Returns:
        Audit summary dictionary
    """
    api = BudgetAuditAPI()
    return api.get_audit_summary("task", task_id)
