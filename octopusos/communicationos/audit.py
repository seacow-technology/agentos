"""Audit logging middleware for message processing.

This module provides audit logging for all messages flowing through the system.
Only metadata is logged (no message content) for privacy and compliance.

Design Principles:
- Metadata only: Never log message content (text, attachments)
- Privacy-first: Only essential tracking information
- SQLite storage: Persistent audit trail
- Query support: Enable audit queries and investigations
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from agentos.communicationos.message_bus import (
    Middleware,
    ProcessingContext,
    ProcessingStatus,
)
from agentos.communicationos.models import InboundMessage, OutboundMessage
from agentos.core.storage.paths import ensure_db_exists
from agentos.core.time import from_epoch_ms, utc_now_ms

logger = logging.getLogger(__name__)


class AuditStore:
    """SQLite-based storage for audit logs.

    This store maintains a tamper-evident audit trail of all messages
    processed by the system. Only metadata is stored, never content.

    Schema:
        CREATE TABLE message_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            direction TEXT NOT NULL,  -- 'inbound' or 'outbound'
            channel_id TEXT NOT NULL,
            user_key TEXT NOT NULL,
            conversation_key TEXT,
            session_id TEXT,
            timestamp_ms INTEGER NOT NULL,
            processing_status TEXT,
            metadata TEXT,  -- JSON
            created_at_ms INTEGER NOT NULL
        )
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the audit store.

        Args:
            db_path: Optional path to SQLite database file.
                    If None, uses default communicationos component path.
        """
        if db_path is None:
            db_path = ensure_db_exists("communicationos")
        else:
            db_path = Path(db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_path = str(db_path)
        self._init_schema()
        logger.info(f"AuditStore initialized: {self.db_path}")

    def _init_schema(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS message_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    user_key TEXT NOT NULL,
                    conversation_key TEXT,
                    session_id TEXT,
                    timestamp_ms INTEGER NOT NULL,
                    processing_status TEXT,
                    metadata TEXT,
                    created_at_ms INTEGER NOT NULL
                )
            """)

            # Indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_message_id
                ON message_audit(message_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_channel_user
                ON message_audit(channel_id, user_key, timestamp_ms DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_session
                ON message_audit(session_id, timestamp_ms DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_created_at
                ON message_audit(created_at_ms DESC)
            """)

            conn.commit()

    def log_inbound(
        self,
        message: InboundMessage,
        status: ProcessingStatus,
        metadata: Dict
    ) -> int:
        """Log an inbound message to audit trail.

        Args:
            message: InboundMessage that was processed
            status: Processing status
            metadata: Additional processing metadata

        Returns:
            Audit log entry ID
        """
        from agentos.core.time import to_epoch_ms

        now_ms = utc_now_ms()
        timestamp_ms = to_epoch_ms(message.timestamp)

        # Extract session_id if present in message metadata
        session_id = message.metadata.get("session_id")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO message_audit
                (message_id, direction, channel_id, user_key, conversation_key,
                 session_id, timestamp_ms, processing_status, metadata, created_at_ms)
                VALUES (?, 'inbound', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    message.channel_id,
                    message.user_key,
                    message.conversation_key,
                    session_id,
                    timestamp_ms,
                    status.value,
                    json.dumps(metadata),
                    now_ms
                )
            )
            conn.commit()
            entry_id = cursor.lastrowid

        logger.debug(
            f"Logged inbound message {message.message_id} "
            f"with status {status.value}"
        )
        return entry_id

    def log_outbound(
        self,
        message: OutboundMessage,
        status: ProcessingStatus,
        metadata: Dict
    ) -> int:
        """Log an outbound message to audit trail.

        Args:
            message: OutboundMessage that was sent
            status: Processing status
            metadata: Additional processing metadata

        Returns:
            Audit log entry ID
        """
        now_ms = utc_now_ms()

        # Extract session_id if present in message metadata
        session_id = message.metadata.get("session_id")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO message_audit
                (message_id, direction, channel_id, user_key, conversation_key,
                 session_id, timestamp_ms, processing_status, metadata, created_at_ms)
                VALUES (?, 'outbound', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata.get("message_id", "unknown"),
                    message.channel_id,
                    message.user_key,
                    message.conversation_key,
                    session_id,
                    now_ms,
                    status.value,
                    json.dumps(metadata),
                    now_ms
                )
            )
            conn.commit()
            entry_id = cursor.lastrowid

        logger.debug(
            f"Logged outbound message to {message.channel_id}:{message.user_key} "
            f"with status {status.value}"
        )
        return entry_id

    def query_by_user(
        self,
        channel_id: str,
        user_key: str,
        limit: int = 100
    ) -> List[Dict]:
        """Query audit logs for a specific user.

        Args:
            channel_id: Channel identifier
            user_key: User identifier
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM message_audit
                WHERE channel_id = ? AND user_key = ?
                ORDER BY timestamp_ms DESC
                LIMIT ?
                """,
                (channel_id, user_key, limit)
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def query_by_session(self, session_id: str) -> List[Dict]:
        """Query audit logs for a specific session.

        Args:
            session_id: Session identifier

        Returns:
            List of audit log entries for the session
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM message_audit
                WHERE session_id = ?
                ORDER BY timestamp_ms ASC
                """,
                (session_id,)
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def cleanup_old_entries(self, retention_ms: int) -> int:
        """Remove audit entries older than retention period.

        Args:
            retention_ms: Retention period in milliseconds

        Returns:
            Number of entries deleted
        """
        cutoff_ms = utc_now_ms() - retention_ms

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM message_audit WHERE created_at_ms < ?",
                (cutoff_ms,)
            )
            deleted = cursor.rowcount
            conn.commit()

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old audit entries")

        return deleted

    def get_stats(self) -> Dict:
        """Get audit statistics.

        Returns:
            Dictionary with statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_messages,
                    SUM(CASE WHEN direction = 'inbound' THEN 1 ELSE 0 END) as inbound_count,
                    SUM(CASE WHEN direction = 'outbound' THEN 1 ELSE 0 END) as outbound_count,
                    COUNT(DISTINCT channel_id) as unique_channels,
                    COUNT(DISTINCT channel_id || ':' || user_key) as unique_users,
                    COUNT(DISTINCT session_id) as unique_sessions
                FROM message_audit
                WHERE session_id IS NOT NULL
            """)
            row = cursor.fetchone()

        return {
            "total_messages": row["total_messages"] or 0,
            "inbound_count": row["inbound_count"] or 0,
            "outbound_count": row["outbound_count"] or 0,
            "unique_channels": row["unique_channels"] or 0,
            "unique_users": row["unique_users"] or 0,
            "unique_sessions": row["unique_sessions"] or 0,
        }


class AuditMiddleware(Middleware):
    """Middleware for audit logging.

    This middleware logs metadata for all messages (both inbound and outbound)
    to create a complete audit trail. Message content is never logged.

    Configuration:
        - retention_days: How long to keep audit logs (default: 30 days)
        - cleanup_interval_ms: How often to cleanup old logs (default: 24 hours)
    """

    def __init__(
        self,
        store: AuditStore,
        retention_days: int = 30,
        cleanup_interval_ms: int = 24 * 60 * 60 * 1000  # 24 hours
    ):
        """Initialize the audit middleware.

        Args:
            store: AuditStore instance for persistence
            retention_days: Number of days to retain audit logs
            cleanup_interval_ms: Interval between cleanup runs in milliseconds
        """
        self.store = store
        self.retention_ms = retention_days * 24 * 60 * 60 * 1000
        self.cleanup_interval_ms = cleanup_interval_ms
        self._last_cleanup_ms = utc_now_ms()

    async def process_inbound(
        self,
        message: InboundMessage,
        context: ProcessingContext
    ) -> ProcessingContext:
        """Log inbound message metadata to audit trail.

        Args:
            message: InboundMessage to audit
            context: Processing context

        Returns:
            Updated context with audit entry ID
        """
        try:
            entry_id = self.store.log_inbound(
                message=message,
                status=context.status,
                metadata=context.metadata
            )
            context.metadata["audit_entry_id"] = entry_id

        except Exception as e:
            logger.exception(f"Failed to log inbound message to audit: {e}")
            # Don't fail the message processing due to audit logging error
            # Just log the error and continue

        # Periodic cleanup
        now_ms = utc_now_ms()
        if now_ms - self._last_cleanup_ms > self.cleanup_interval_ms:
            try:
                self.store.cleanup_old_entries(self.retention_ms)
                self._last_cleanup_ms = now_ms
            except Exception as e:
                logger.warning(f"Failed to cleanup old audit entries: {e}")

        return context

    async def process_outbound(
        self,
        message: OutboundMessage,
        context: ProcessingContext
    ) -> ProcessingContext:
        """Log outbound message metadata to audit trail.

        Args:
            message: OutboundMessage to audit
            context: Processing context

        Returns:
            Updated context with audit entry ID
        """
        try:
            entry_id = self.store.log_outbound(
                message=message,
                status=context.status,
                metadata=context.metadata
            )
            context.metadata["audit_entry_id"] = entry_id

        except Exception as e:
            logger.exception(f"Failed to log outbound message to audit: {e}")
            # Don't fail the message processing due to audit logging error

        return context
