"""Message deduplication middleware using SQLite storage.

This module provides deduplication for inbound messages based on message_id
to prevent duplicate processing when external channels retry or send duplicates.

Design Principles:
- Message ID based: Use message_id as unique key
- SQLite storage: Persistent deduplication across restarts
- Configurable TTL: Auto-cleanup of old entries
- Read-after-write: Atomic insert with conflict detection
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

from agentos.communicationos.message_bus import (
    Middleware,
    ProcessingContext,
    ProcessingStatus,
)
from agentos.communicationos.models import InboundMessage, OutboundMessage
from agentos.core.storage.paths import ensure_db_exists
from agentos.core.time import utc_now, utc_now_ms

logger = logging.getLogger(__name__)


class DedupeStore:
    """SQLite-based storage for message deduplication.

    This store tracks message IDs to detect and prevent duplicate processing.
    It automatically cleans up old entries based on TTL.

    Schema:
        CREATE TABLE message_dedupe (
            message_id TEXT PRIMARY KEY,
            channel_id TEXT NOT NULL,
            first_seen_ms INTEGER NOT NULL,
            last_seen_ms INTEGER NOT NULL,
            count INTEGER DEFAULT 1
        )
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the deduplication store.

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
        logger.info(f"DedupeStore initialized: {self.db_path}")

    def _init_schema(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS message_dedupe (
                    message_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    first_seen_ms INTEGER NOT NULL,
                    last_seen_ms INTEGER NOT NULL,
                    count INTEGER DEFAULT 1,
                    metadata TEXT,
                    PRIMARY KEY (message_id, channel_id)
                )
            """)
            # Index for cleanup queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_message_dedupe_last_seen
                ON message_dedupe(last_seen_ms)
            """)
            conn.commit()

    def is_duplicate(self, message_id: str, channel_id: str) -> bool:
        """Check if a message has been seen before.

        This method atomically checks and records the message. If the message
        is new, it's recorded and False is returned. If it's a duplicate, the
        count is incremented and True is returned.

        Args:
            message_id: Unique message identifier
            channel_id: Channel identifier

        Returns:
            True if message is a duplicate, False if new
        """
        now_ms = utc_now_ms()

        with sqlite3.connect(self.db_path) as conn:
            # Try to insert, if conflict then it's a duplicate
            try:
                conn.execute(
                    """
                    INSERT INTO message_dedupe
                    (message_id, channel_id, first_seen_ms, last_seen_ms, count)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (message_id, channel_id, now_ms, now_ms)
                )
                conn.commit()
                logger.debug(f"New message recorded: {message_id}")
                return False

            except sqlite3.IntegrityError:
                # Message already exists, update count and last_seen
                conn.execute(
                    """
                    UPDATE message_dedupe
                    SET last_seen_ms = ?, count = count + 1
                    WHERE message_id = ? AND channel_id = ?
                    """,
                    (now_ms, message_id, channel_id)
                )
                conn.commit()

                # Get the count for logging
                cursor = conn.execute(
                    "SELECT count FROM message_dedupe WHERE message_id = ? AND channel_id = ?",
                    (message_id, channel_id)
                )
                row = cursor.fetchone()
                count = row[0] if row else 0

                logger.info(
                    f"Duplicate message detected: {message_id} "
                    f"(seen {count} times)"
                )
                return True

    def cleanup_old_entries(self, ttl_ms: int) -> int:
        """Remove entries older than the specified TTL.

        Args:
            ttl_ms: Time-to-live in milliseconds

        Returns:
            Number of entries deleted
        """
        cutoff_ms = utc_now_ms() - ttl_ms

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM message_dedupe WHERE last_seen_ms < ?",
                (cutoff_ms,)
            )
            deleted = cursor.rowcount
            conn.commit()

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old dedupe entries")

        return deleted

    def get_stats(self) -> dict:
        """Get statistics about the deduplication store.

        Returns:
            Dictionary with stats: total_messages, duplicate_messages, etc.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_messages,
                    SUM(CASE WHEN count > 1 THEN 1 ELSE 0 END) as messages_with_duplicates,
                    SUM(count - 1) as total_duplicates_blocked
                FROM message_dedupe
            """)
            row = cursor.fetchone()

        return {
            "total_messages": row["total_messages"] or 0,
            "messages_with_duplicates": row["messages_with_duplicates"] or 0,
            "total_duplicates_blocked": row["total_duplicates_blocked"] or 0,
        }


class DedupeMiddleware(Middleware):
    """Middleware for message deduplication.

    This middleware prevents duplicate processing of inbound messages by
    checking message_id against a persistent store. Outbound messages are
    not deduplicated as they should always be sent.

    Configuration:
        - ttl_ms: Time-to-live for dedupe entries (default: 24 hours)
        - cleanup_interval: How often to run cleanup (default: 1 hour)
    """

    def __init__(
        self,
        store: DedupeStore,
        ttl_ms: int = 24 * 60 * 60 * 1000,  # 24 hours
        cleanup_interval_ms: int = 60 * 60 * 1000  # 1 hour
    ):
        """Initialize the deduplication middleware.

        Args:
            store: DedupeStore instance for persistence
            ttl_ms: Time-to-live for entries in milliseconds
            cleanup_interval_ms: Interval between cleanup runs in milliseconds
        """
        self.store = store
        self.ttl_ms = ttl_ms
        self.cleanup_interval_ms = cleanup_interval_ms
        self._last_cleanup_ms = utc_now_ms()

    async def process_inbound(
        self,
        message: InboundMessage,
        context: ProcessingContext
    ) -> ProcessingContext:
        """Check for duplicate inbound messages.

        Args:
            message: InboundMessage to check
            context: Processing context

        Returns:
            Updated context with REJECT status if duplicate
        """
        # Check if this message is a duplicate
        is_dup = self.store.is_duplicate(message.message_id, message.channel_id)

        if is_dup:
            context.status = ProcessingStatus.REJECT
            context.metadata["dedupe_reason"] = "duplicate_message_id"
            logger.info(
                f"Rejected duplicate message: {message.message_id} "
                f"from channel: {message.channel_id}"
            )
        else:
            context.metadata["dedupe_checked"] = True

        # Periodic cleanup
        now_ms = utc_now_ms()
        if now_ms - self._last_cleanup_ms > self.cleanup_interval_ms:
            try:
                self.store.cleanup_old_entries(self.ttl_ms)
                self._last_cleanup_ms = now_ms
            except Exception as e:
                logger.warning(f"Failed to cleanup old dedupe entries: {e}")

        return context

    async def process_outbound(
        self,
        message: OutboundMessage,
        context: ProcessingContext
    ) -> ProcessingContext:
        """Process outbound message (no deduplication).

        Outbound messages are not deduplicated as they should always be sent.

        Args:
            message: OutboundMessage to process
            context: Processing context

        Returns:
            Unchanged context
        """
        # No deduplication for outbound messages
        return context
