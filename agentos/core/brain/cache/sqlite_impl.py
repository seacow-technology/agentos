"""
SQLite-based Brain Cache Implementation

Fallback cache implementation using SQLite with TTL support.
"""

import json
import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from .interface import IBrainCache

logger = logging.getLogger(__name__)


def utc_now_ms() -> int:
    """Get current UTC timestamp in milliseconds."""
    from datetime import datetime, timezone
    return int(datetime.now(timezone.utc).timestamp() * 1000)


class SQLiteBrainCache(IBrainCache):
    """SQLite-based brain cache with TTL support."""

    def __init__(self, db_path: Path):
        """
        Initialize SQLite cache.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.hits = 0
        self.misses = 0

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize schema
        self._init_schema()
        logger.info(f"SQLiteBrainCache initialized: {db_path}")

    def _init_schema(self):
        """Initialize cache table schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS brain_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at INTEGER NOT NULL
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_brain_cache_expires
                ON brain_cache(expires_at)
            """)

            conn.commit()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached subgraph from SQLite.

        Args:
            key: Cache key

        Returns:
            Cached data or None if not found/expired
        """
        now_ms = utc_now_ms()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value FROM brain_cache WHERE key = ? AND expires_at > ?",
                (key, now_ms)
            )
            row = cursor.fetchone()

            if row:
                self.hits += 1
                logger.debug(f"Cache hit: {key}")
                return json.loads(row[0])
            else:
                self.misses += 1
                logger.debug(f"Cache miss: {key}")
                return None

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int = 3600):
        """
        Cache subgraph in SQLite with TTL.

        Args:
            key: Cache key
            value: Subgraph data to cache
            ttl_seconds: Time-to-live in seconds
        """
        now_ms = utc_now_ms()
        expires_at = now_ms + (ttl_seconds * 1000)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO brain_cache (key, value, expires_at) VALUES (?, ?, ?)",
                (key, json.dumps(value), expires_at)
            )
            conn.commit()

        logger.debug(f"Cached: {key} (TTL: {ttl_seconds}s)")

    def invalidate(self, key: str):
        """
        Invalidate cache entry in SQLite.

        Args:
            key: Cache key to invalidate
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM brain_cache WHERE key = ?", (key,))
            conn.commit()

        logger.debug(f"Invalidated: {key}")

    def cleanup_expired(self):
        """Remove expired cache entries."""
        now_ms = utc_now_ms()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM brain_cache WHERE expires_at <= ?", (now_ms,))
            deleted = cursor.rowcount
            conn.commit()

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired cache entries")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with hits, misses, hit_rate
        """
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0

        # Get cache entry count
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM brain_cache")
            entry_count = cursor.fetchone()[0]

        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 4),
            "backend": "sqlite",
            "db_path": str(self.db_path),
            "entry_count": entry_count
        }
