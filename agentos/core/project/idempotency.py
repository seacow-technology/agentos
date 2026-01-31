"""Idempotency Key Management for Project Operations

Provides idempotency key handling to ensure duplicate requests
don't create duplicate resources (M-03 fix).

Design:
- In-memory cache with TTL (24 hours)
- Thread-safe operations
- Automatic cleanup of expired entries
"""

import logging
import threading
import time
from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


@dataclass
class IdempotencyRecord:
    """Record of an idempotent operation"""
    key: str
    response: Any
    created_at: float
    ttl_seconds: int = 86400  # 24 hours default

    def is_expired(self) -> bool:
        """Check if record has expired"""
        return time.time() - self.created_at > self.ttl_seconds


class IdempotencyStore:
    """Thread-safe idempotency key store

    Stores operation results keyed by idempotency key to prevent
    duplicate operations from duplicate requests.

    Features:
    - Thread-safe operations
    - Automatic TTL-based expiration
    - Memory-based (not persisted)
    """

    def __init__(self, default_ttl: int = 86400):
        """Initialize idempotency store

        Args:
            default_ttl: Default TTL for records in seconds (24 hours)
        """
        self._store: Dict[str, IdempotencyRecord] = {}
        self._lock = threading.RLock()
        self._default_ttl = default_ttl
        logger.info(f"IdempotencyStore initialized with TTL={default_ttl}s")

    def get(self, key: str) -> Optional[Any]:
        """Get cached response for idempotency key

        Args:
            key: Idempotency key

        Returns:
            Cached response if exists and not expired, None otherwise
        """
        with self._lock:
            record = self._store.get(key)

            if record is None:
                return None

            # Check expiration
            if record.is_expired():
                logger.debug(f"Idempotency key expired: {key}")
                del self._store[key]
                return None

            logger.info(f"Idempotency key hit: {key}")
            return record.response

    def set(self, key: str, response: Any, ttl: Optional[int] = None) -> None:
        """Store response for idempotency key

        Args:
            key: Idempotency key
            response: Response to cache
            ttl: Optional TTL override in seconds
        """
        with self._lock:
            record = IdempotencyRecord(
                key=key,
                response=response,
                created_at=time.time(),
                ttl_seconds=ttl or self._default_ttl
            )
            self._store[key] = record
            logger.debug(f"Cached idempotency key: {key}, TTL={record.ttl_seconds}s")

    def exists(self, key: str) -> bool:
        """Check if idempotency key exists and is valid

        Args:
            key: Idempotency key

        Returns:
            True if key exists and not expired
        """
        return self.get(key) is not None

    def invalidate(self, key: str) -> bool:
        """Invalidate an idempotency key

        Args:
            key: Idempotency key to invalidate

        Returns:
            True if key was found and removed
        """
        with self._lock:
            if key in self._store:
                del self._store[key]
                logger.debug(f"Invalidated idempotency key: {key}")
                return True
            return False

    def cleanup_expired(self) -> int:
        """Remove all expired records

        Returns:
            Number of records removed
        """
        with self._lock:
            expired_keys = [
                key for key, record in self._store.items()
                if record.is_expired()
            ]

            for key in expired_keys:
                del self._store[key]

            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired idempotency records")

            return len(expired_keys)

    def size(self) -> int:
        """Get current store size

        Returns:
            Number of active records
        """
        with self._lock:
            return len(self._store)

    def clear(self) -> None:
        """Clear all records (for testing)"""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            logger.warning(f"Cleared all {count} idempotency records")


# Global singleton instance
_global_store: Optional[IdempotencyStore] = None
_global_store_lock = threading.Lock()


def get_idempotency_store() -> IdempotencyStore:
    """Get global idempotency store singleton

    Returns:
        Global IdempotencyStore instance
    """
    global _global_store

    if _global_store is None:
        with _global_store_lock:
            if _global_store is None:
                _global_store = IdempotencyStore()

    return _global_store


def reset_idempotency_store() -> None:
    """Reset global store (for testing)"""
    global _global_store
    with _global_store_lock:
        if _global_store:
            _global_store.clear()
        _global_store = None
