"""Rate limiting for communication operations.

This module implements rate limiting to prevent abuse and ensure
fair usage of external communication resources.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from agentos.core.time import utc_now


logger = logging.getLogger(__name__)


@dataclass
class RateLimitRecord:
    """Record of rate limit usage.

    Attributes:
        key: Rate limit key (e.g., connector type)
        timestamps: List of request timestamps
        limit: Maximum requests allowed in window
        window_seconds: Time window in seconds
    """

    key: str
    timestamps: List[float] = field(default_factory=list)
    limit: int = 60
    window_seconds: int = 60


class RateLimiter:
    """Rate limiter for communication operations.

    Implements a sliding window rate limiter to control
    request frequency per connector or operation.
    """

    def __init__(self):
        """Initialize rate limiter."""
        self.records: Dict[str, RateLimitRecord] = {}
        self.global_limit = 100  # Global limit per minute
        self.global_timestamps: List[float] = []

    def check_limit(
        self,
        key: str,
        limit: int = 60,
        window_seconds: int = 60,
    ) -> Tuple[bool, str]:
        """Check if request is within rate limit.

        Args:
            key: Rate limit key (e.g., connector type)
            limit: Maximum requests in window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, reason)
        """
        now = time.time()

        # Check global limit first
        is_allowed, reason = self._check_global_limit(now)
        if not is_allowed:
            return False, reason

        # Get or create record for key
        if key not in self.records:
            self.records[key] = RateLimitRecord(
                key=key,
                limit=limit,
                window_seconds=window_seconds,
            )

        record = self.records[key]

        # Remove old timestamps outside the window
        cutoff = now - window_seconds
        record.timestamps = [ts for ts in record.timestamps if ts > cutoff]

        # Check if limit is exceeded
        if len(record.timestamps) >= limit:
            oldest = min(record.timestamps)
            wait_time = int(window_seconds - (now - oldest))
            return False, f"Rate limit exceeded. Try again in {wait_time} seconds."

        # Add current timestamp
        record.timestamps.append(now)
        self.global_timestamps.append(now)

        logger.debug(f"Rate limit check passed: {key} ({len(record.timestamps)}/{limit})")
        return True, "OK"

    def _check_global_limit(self, now: float) -> Tuple[bool, str]:
        """Check global rate limit.

        Args:
            now: Current timestamp

        Returns:
            Tuple of (is_allowed, reason)
        """
        # Remove old timestamps
        cutoff = now - 60  # 1 minute window
        self.global_timestamps = [ts for ts in self.global_timestamps if ts > cutoff]

        if len(self.global_timestamps) >= self.global_limit:
            oldest = min(self.global_timestamps)
            wait_time = int(60 - (now - oldest))
            return False, f"Global rate limit exceeded. Try again in {wait_time} seconds."

        return True, "OK"

    def get_usage(self, key: str) -> Dict[str, any]:
        """Get current usage for a key.

        Args:
            key: Rate limit key

        Returns:
            Dictionary with usage information
        """
        if key not in self.records:
            return {
                "key": key,
                "current": 0,
                "limit": 0,
                "window_seconds": 60,
                "percentage": 0.0,
            }

        record = self.records[key]
        now = time.time()
        cutoff = now - record.window_seconds
        current = len([ts for ts in record.timestamps if ts > cutoff])

        return {
            "key": key,
            "current": current,
            "limit": record.limit,
            "window_seconds": record.window_seconds,
            "percentage": (current / record.limit * 100) if record.limit > 0 else 0.0,
        }

    def get_all_usage(self) -> Dict[str, Dict[str, any]]:
        """Get usage for all keys.

        Returns:
            Dictionary mapping keys to usage information
        """
        return {key: self.get_usage(key) for key in self.records.keys()}

    def reset(self, key: Optional[str] = None) -> None:
        """Reset rate limit records.

        Args:
            key: Specific key to reset, or None to reset all
        """
        if key:
            if key in self.records:
                self.records[key].timestamps.clear()
                logger.info(f"Reset rate limit for: {key}")
        else:
            self.records.clear()
            self.global_timestamps.clear()
            logger.info("Reset all rate limits")

    def set_limit(self, key: str, limit: int, window_seconds: int = 60) -> None:
        """Set rate limit for a key.

        Args:
            key: Rate limit key
            limit: Maximum requests in window
            window_seconds: Time window in seconds
        """
        if key not in self.records:
            self.records[key] = RateLimitRecord(key=key)

        self.records[key].limit = limit
        self.records[key].window_seconds = window_seconds
        logger.info(f"Set rate limit for {key}: {limit} requests per {window_seconds}s")

    def get_remaining(self, key: str) -> int:
        """Get remaining requests for a key.

        Args:
            key: Rate limit key

        Returns:
            Number of remaining requests
        """
        usage = self.get_usage(key)
        return max(0, usage["limit"] - usage["current"])

    def get_reset_time(self, key: str) -> Optional[datetime]:
        """Get time when rate limit will reset.

        Args:
            key: Rate limit key

        Returns:
            Reset time as datetime, or None if key not found
        """
        if key not in self.records:
            return None

        record = self.records[key]
        if not record.timestamps:
            return utc_now()

        oldest = min(record.timestamps)
        reset_timestamp = oldest + record.window_seconds
        return datetime.fromtimestamp(reset_timestamp, tz=timezone.utc)
