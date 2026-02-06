"""Rate limiting middleware for message processing.

This module provides rate limiting to prevent abuse and protect the system
from message flooding. Rate limits are applied per channel+user combination.

Design Principles:
- Sliding window: Accurate rate limiting using sliding window
- Per-user limits: Each user has independent rate limits
- SQLite storage: Persistent tracking across restarts
- Configurable: Flexible rate limit configuration per channel
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Dict, Optional

from agentos.communicationos.message_bus import (
    Middleware,
    ProcessingContext,
    ProcessingStatus,
)
from agentos.communicationos.models import InboundMessage, OutboundMessage
from agentos.core.storage.paths import ensure_db_exists
from agentos.core.time import utc_now_ms

logger = logging.getLogger(__name__)


class RateLimitStore:
    """SQLite-based storage for rate limiting state.

    This store tracks message counts per user per channel using a sliding
    window approach for accurate rate limiting.

    Schema:
        CREATE TABLE rate_limit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            user_key TEXT NOT NULL,
            timestamp_ms INTEGER NOT NULL
        )
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the rate limit store.

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
        logger.info(f"RateLimitStore initialized: {self.db_path}")

    def _init_schema(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL,
                    user_key TEXT NOT NULL,
                    timestamp_ms INTEGER NOT NULL
                )
            """)
            # Index for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rate_limit_channel_user_time
                ON rate_limit_events(channel_id, user_key, timestamp_ms)
            """)
            conn.commit()

    def check_rate_limit(
        self,
        channel_id: str,
        user_key: str,
        window_ms: int,
        max_requests: int
    ) -> tuple[bool, int]:
        """Check if user has exceeded rate limit and record event.

        Uses a sliding window approach: counts events in the last window_ms
        milliseconds and compares to max_requests.

        Args:
            channel_id: Channel identifier
            user_key: User identifier
            window_ms: Time window in milliseconds
            max_requests: Maximum requests allowed in window

        Returns:
            Tuple of (is_allowed, current_count)
            - is_allowed: True if request is within rate limit
            - current_count: Number of requests in current window
        """
        now_ms = utc_now_ms()
        window_start_ms = now_ms - window_ms

        with sqlite3.connect(self.db_path) as conn:
            # Count requests in the current window
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM rate_limit_events
                WHERE channel_id = ?
                  AND user_key = ?
                  AND timestamp_ms > ?
                """,
                (channel_id, user_key, window_start_ms)
            )
            count = cursor.fetchone()[0]

            # Check if under limit
            if count < max_requests:
                # Record this event
                conn.execute(
                    """
                    INSERT INTO rate_limit_events
                    (channel_id, user_key, timestamp_ms)
                    VALUES (?, ?, ?)
                    """,
                    (channel_id, user_key, now_ms)
                )
                conn.commit()
                return True, count + 1
            else:
                # Over limit, don't record
                logger.warning(
                    f"Rate limit exceeded for {channel_id}:{user_key} "
                    f"({count}/{max_requests} in {window_ms}ms)"
                )
                return False, count

    def cleanup_old_events(self, retention_ms: int) -> int:
        """Remove events older than retention period.

        Args:
            retention_ms: Retention period in milliseconds

        Returns:
            Number of events deleted
        """
        cutoff_ms = utc_now_ms() - retention_ms

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM rate_limit_events WHERE timestamp_ms < ?",
                (cutoff_ms,)
            )
            deleted = cursor.rowcount
            conn.commit()

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old rate limit events")

        return deleted

    def get_stats(self, channel_id: Optional[str] = None) -> Dict:
        """Get rate limiting statistics.

        Args:
            channel_id: Optional channel filter

        Returns:
            Dictionary with statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            if channel_id:
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_events,
                        COUNT(DISTINCT user_key) as unique_users
                    FROM rate_limit_events
                    WHERE channel_id = ?
                    """,
                    (channel_id,)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_events,
                        COUNT(DISTINCT channel_id || ':' || user_key) as unique_users
                    FROM rate_limit_events
                    """
                )

            row = cursor.fetchone()

        return {
            "total_events": row[0] or 0,
            "unique_users": row[1] or 0,
        }


class RateLimitMiddleware(Middleware):
    """Middleware for rate limiting message processing.

    This middleware enforces rate limits on inbound messages to prevent
    abuse and protect system resources. Limits are applied per channel+user.

    Configuration:
        - window_ms: Time window for rate limiting (default: 60 seconds)
        - max_requests: Maximum requests per window (default: 20)
        - cleanup_interval_ms: How often to cleanup old events (default: 10 minutes)
    """

    def __init__(
        self,
        store: RateLimitStore,
        window_ms: int = 60 * 1000,  # 60 seconds
        max_requests: int = 20,
        cleanup_interval_ms: int = 10 * 60 * 1000  # 10 minutes
    ):
        """Initialize the rate limiting middleware.

        Args:
            store: RateLimitStore instance for persistence
            window_ms: Time window in milliseconds
            max_requests: Maximum requests allowed per window
            cleanup_interval_ms: Interval between cleanup runs in milliseconds
        """
        self.store = store
        self.window_ms = window_ms
        self.max_requests = max_requests
        self.cleanup_interval_ms = cleanup_interval_ms
        self._last_cleanup_ms = utc_now_ms()

        # Retention is 10x the window to keep historical data
        self.retention_ms = window_ms * 10

    async def process_inbound(
        self,
        message: InboundMessage,
        context: ProcessingContext
    ) -> ProcessingContext:
        """Check rate limit for inbound messages.

        Args:
            message: InboundMessage to check
            context: Processing context

        Returns:
            Updated context with REJECT status if rate limit exceeded
        """
        # Check rate limit
        is_allowed, count = self.store.check_rate_limit(
            channel_id=message.channel_id,
            user_key=message.user_key,
            window_ms=self.window_ms,
            max_requests=self.max_requests
        )

        if not is_allowed:
            context.status = ProcessingStatus.REJECT
            context.metadata["rate_limit_exceeded"] = True
            context.metadata["rate_limit_count"] = count
            context.metadata["rate_limit_max"] = self.max_requests
            context.metadata["rate_limit_window_ms"] = self.window_ms

            logger.warning(
                f"Rate limit exceeded for message: {message.message_id} "
                f"from {message.channel_id}:{message.user_key} "
                f"({count}/{self.max_requests} in {self.window_ms}ms window)"
            )
        else:
            context.metadata["rate_limit_checked"] = True
            context.metadata["rate_limit_count"] = count

            logger.debug(
                f"Rate limit check passed for {message.channel_id}:{message.user_key} "
                f"({count}/{self.max_requests})"
            )

        # Periodic cleanup
        now_ms = utc_now_ms()
        if now_ms - self._last_cleanup_ms > self.cleanup_interval_ms:
            try:
                self.store.cleanup_old_events(self.retention_ms)
                self._last_cleanup_ms = now_ms
            except Exception as e:
                logger.warning(f"Failed to cleanup old rate limit events: {e}")

        return context

    async def process_outbound(
        self,
        message: OutboundMessage,
        context: ProcessingContext
    ) -> ProcessingContext:
        """Process outbound message (no rate limiting).

        Outbound messages are not rate limited as they are system-initiated.

        Args:
            message: OutboundMessage to process
            context: Processing context

        Returns:
            Unchanged context
        """
        # No rate limiting for outbound messages
        return context
