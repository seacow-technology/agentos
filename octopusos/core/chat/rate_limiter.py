"""AutoComm rate limiting and deduplication"""

from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import hashlib

# Configuration
MAX_REQUESTS_PER_MINUTE = 5
DEDUP_WINDOW_SECONDS = 300  # 5 minutes


class RateLimiter:
    """Session-level rate limiter"""

    def __init__(self, max_requests: int = MAX_REQUESTS_PER_MINUTE):
        self.max_requests = max_requests
        self.request_log = defaultdict(deque)  # session_id -> [timestamp, ...]

    def check_rate_limit(self, session_id: str) -> Tuple[bool, int]:
        """
        Check if rate limit has been exceeded

        Returns:
            (allowed: bool, remaining: int)
        """
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)

        # Clean up expired records
        log = self.request_log[session_id]
        while log and log[0] < cutoff:
            log.popleft()

        # Check rate limit
        current_count = len(log)
        allowed = current_count < self.max_requests

        if allowed:
            log.append(now)
            remaining = self.max_requests - current_count - 1
        else:
            remaining = 0

        return allowed, remaining


class DedupChecker:
    """Query deduplication checker"""

    def __init__(self, window_seconds: int = DEDUP_WINDOW_SECONDS):
        self.window_seconds = window_seconds
        self.cache = {}  # (session_id, query_hash) -> (timestamp, result)

    def _hash_query(self, query: str) -> str:
        """Generate hash for query"""
        return hashlib.sha256(query.encode()).hexdigest()[:16]

    def check_duplicate(
        self,
        session_id: str,
        query: str
    ) -> Tuple[bool, Optional[dict]]:
        """
        Check if this is a duplicate query

        Returns:
            (is_duplicate: bool, cached_result: Optional[dict])
        """
        query_hash = self._hash_query(query)
        key = (session_id, query_hash)

        if key not in self.cache:
            return False, None

        timestamp, result = self.cache[key]
        age = (datetime.now() - timestamp).total_seconds()

        if age > self.window_seconds:
            # Expired, clean cache
            del self.cache[key]
            return False, None

        return True, result

    def store_result(self, session_id: str, query: str, result: dict):
        """Store execution result"""
        query_hash = self._hash_query(query)
        key = (session_id, query_hash)
        self.cache[key] = (datetime.now(), result)


# Global instances
rate_limiter = RateLimiter()
dedup_checker = DedupChecker()


def reset_rate_limiter():
    """Reset rate limiter state (for testing)"""
    global rate_limiter
    rate_limiter = RateLimiter()


def reset_dedup_checker():
    """Reset deduplication checker state (for testing)"""
    global dedup_checker
    dedup_checker = DedupChecker()
