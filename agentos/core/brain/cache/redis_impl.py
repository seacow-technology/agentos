"""
Redis-based Brain Cache Implementation

Provides cross-process, persistent cache using Redis.
"""

import json
import logging
from typing import Optional, Dict, Any

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from .interface import IBrainCache

logger = logging.getLogger(__name__)


class RedisBrainCache(IBrainCache):
    """Redis-based brain cache for cross-process subgraph caching."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        Initialize Redis cache.

        Args:
            redis_url: Redis connection URL

        Raises:
            ImportError: If redis package is not installed
            redis.RedisError: If connection fails
        """
        if not REDIS_AVAILABLE:
            raise ImportError("redis package not installed. Install with: pip install redis")

        self.redis_url = redis_url
        self.client = redis.from_url(redis_url, decode_responses=True)
        self.hits = 0
        self.misses = 0

        # Test connection
        self.client.ping()
        logger.info(f"RedisBrainCache initialized: {redis_url}")

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached subgraph from Redis.

        Args:
            key: Cache key

        Returns:
            Cached data or None if not found
        """
        try:
            cache_key = f"brain:subgraph:{key}"
            cached = self.client.get(cache_key)

            if cached:
                self.hits += 1
                logger.debug(f"Cache hit: {key}")
                return json.loads(cached)
            else:
                self.misses += 1
                logger.debug(f"Cache miss: {key}")
                return None

        except redis.RedisError as e:
            logger.error(f"Redis get failed: {e}")
            self.misses += 1
            return None

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int = 3600):
        """
        Cache subgraph in Redis with TTL.

        Args:
            key: Cache key
            value: Subgraph data to cache
            ttl_seconds: Time-to-live in seconds
        """
        try:
            cache_key = f"brain:subgraph:{key}"
            self.client.setex(
                cache_key,
                ttl_seconds,
                json.dumps(value)
            )
            logger.debug(f"Cached: {key} (TTL: {ttl_seconds}s)")

        except redis.RedisError as e:
            logger.error(f"Redis set failed: {e}")

    def invalidate(self, key: str):
        """
        Invalidate cache entry in Redis.

        Args:
            key: Cache key to invalidate
        """
        try:
            cache_key = f"brain:subgraph:{key}"
            self.client.delete(cache_key)
            logger.debug(f"Invalidated: {key}")

        except redis.RedisError as e:
            logger.error(f"Redis delete failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with hits, misses, hit_rate
        """
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0

        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 4),
            "backend": "redis",
            "url": self.redis_url
        }
