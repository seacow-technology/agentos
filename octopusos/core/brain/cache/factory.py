"""
Brain Cache Factory

Automatically selects Redis or SQLite cache based on availability.
"""

import os
import logging
from pathlib import Path

from .interface import IBrainCache
from .redis_impl import RedisBrainCache, REDIS_AVAILABLE
from .sqlite_impl import SQLiteBrainCache

logger = logging.getLogger(__name__)


def get_brain_cache() -> IBrainCache:
    """
    Get brain cache instance with automatic fallback.

    Priority:
    1. Redis (if available and REDIS_URL is set)
    2. SQLite (fallback)

    Returns:
        IBrainCache instance
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Try Redis first if redis package is available
    if REDIS_AVAILABLE:
        try:
            cache = RedisBrainCache(redis_url)
            cache.client.ping()  # Test connection
            logger.info(f"Using Redis brain cache: {redis_url}")
            return cache
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}), falling back to SQLite cache")
    else:
        logger.info("Redis package not installed, using SQLite cache")

    # Fallback to SQLite
    db_path = Path.home() / ".agentos/store/agentos/cache.sqlite"
    cache = SQLiteBrainCache(db_path)
    logger.info(f"Using SQLite brain cache: {db_path}")
    return cache
