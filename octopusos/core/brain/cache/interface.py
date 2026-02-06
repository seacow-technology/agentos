"""
Brain Cache Interface

Defines the contract for Brain subgraph cache implementations.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class IBrainCache(ABC):
    """Brain subgraph cache interface."""

    @abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached subgraph.

        Args:
            key: Cache key

        Returns:
            Cached data or None if not found/expired
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int = 3600):
        """
        Cache subgraph with TTL.

        Args:
            key: Cache key
            value: Subgraph data to cache
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
        """
        pass

    @abstractmethod
    def invalidate(self, key: str):
        """
        Invalidate cache entry.

        Args:
            key: Cache key to invalidate
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with hits, misses, hit_rate
        """
        pass
