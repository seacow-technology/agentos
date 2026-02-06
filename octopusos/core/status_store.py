"""
Status Store - Unified status cache for all components

Single source of truth for:
- Provider status
- Context status
- Runtime status

v0.3.2 Closeout #1: Centralized status management with TTL
"""

import asyncio
import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from agentos.providers.base import ProviderStatus

logger = logging.getLogger(__name__)


@dataclass
class CachedStatus:
    """Status entry with cache metadata"""
    data: Any
    cached_at: float  # Unix timestamp
    ttl_ms: int  # Cache TTL in milliseconds


class StatusStore:
    """
    Centralized status cache

    Provides unified caching for all status queries with configurable TTL.
    Prevents redundant probes and provides consistent status across UI.

    Usage:
        store = StatusStore.get_instance()
        status = await store.get_provider_status("ollama", ttl_ms=5000)
    """

    _instance: Optional["StatusStore"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._provider_cache: Dict[str, CachedStatus] = {}
        self._context_cache: Dict[str, CachedStatus] = {}
        self._runtime_cache: Dict[str, CachedStatus] = {}

        # Default TTLs (can be overridden per call)
        self.default_provider_ttl_ms = 5000  # 5 seconds
        self.default_context_ttl_ms = 10000  # 10 seconds
        self.default_runtime_ttl_ms = 30000  # 30 seconds

    @classmethod
    def get_instance(cls) -> "StatusStore":
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _is_cache_valid(self, cached: Optional[CachedStatus]) -> bool:
        """Check if cached entry is still valid"""
        if cached is None:
            return False

        now = time.time()
        age_ms = (now - cached.cached_at) * 1000

        return age_ms < cached.ttl_ms

    def _cache_entry(self, data: Any, ttl_ms: int) -> CachedStatus:
        """Create cache entry"""
        return CachedStatus(
            data=data,
            cached_at=time.time(),
            ttl_ms=ttl_ms,
        )

    def get_cache_age_ms(self, cached: Optional[CachedStatus]) -> Optional[int]:
        """Get cache age in milliseconds"""
        if cached is None:
            return None

        now = time.time()
        age_ms = (now - cached.cached_at) * 1000

        return int(age_ms)

    # Provider Status Methods

    async def get_provider_status(
        self,
        provider_id: str,
        ttl_ms: Optional[int] = None,
        force_refresh: bool = False,
    ) -> tuple[Optional[ProviderStatus], int]:
        """
        Get provider status with caching

        Args:
            provider_id: Provider ID
            ttl_ms: Cache TTL in milliseconds (default: 5000)
            force_refresh: If True, bypass cache and probe

        Returns:
            Tuple of (status, cache_ttl_ms)
        """
        ttl = ttl_ms or self.default_provider_ttl_ms

        # Check cache first
        if not force_refresh:
            cached = self._provider_cache.get(provider_id)
            if self._is_cache_valid(cached):
                return cached.data, ttl

        # Cache miss or expired - probe provider
        from agentos.providers.registry import ProviderRegistry

        registry = ProviderRegistry.get_instance()
        provider = registry.get(provider_id)

        if not provider:
            return None, ttl

        status = await provider.probe()

        # Cache the result
        self._provider_cache[provider_id] = self._cache_entry(status, ttl)

        return status, ttl

    async def get_all_provider_status(
        self,
        ttl_ms: Optional[int] = None,
        force_refresh: bool = False,
    ) -> tuple[List[ProviderStatus], int]:
        """
        Get status for all providers

        Args:
            ttl_ms: Cache TTL in milliseconds
            force_refresh: If True, bypass cache and probe all

        Returns:
            Tuple of (status_list, cache_ttl_ms)
        """
        from agentos.providers.registry import ProviderRegistry

        ttl = ttl_ms or self.default_provider_ttl_ms
        registry = ProviderRegistry.get_instance()

        # Get status for each provider
        tasks = []
        providers = registry.list_all()

        for provider in providers:
            tasks.append(
                self.get_provider_status(provider.id, ttl_ms=ttl, force_refresh=force_refresh)
            )

        results = await asyncio.gather(*tasks)

        # Extract status objects (ignore ttl from individual calls)
        status_list = [status for status, _ in results if status is not None]

        return status_list, ttl

    def invalidate_provider(self, provider_id: str):
        """清除单个 provider 的缓存"""
        if provider_id in self._provider_cache:
            del self._provider_cache[provider_id]
            logger.debug(f"Invalidated cache for provider: {provider_id}")

    def invalidate_all_providers(self):
        """清除所有 provider 缓存"""
        count = len(self._provider_cache)
        self._provider_cache.clear()
        logger.debug(f"Invalidated all provider caches ({count} entries)")

    # Context Status Methods

    def cache_context_status(self, session_id: str, status: Any, ttl_ms: Optional[int] = None):
        """Cache context status for a session"""
        ttl = ttl_ms or self.default_context_ttl_ms
        self._context_cache[session_id] = self._cache_entry(status, ttl)

    def get_cached_context_status(self, session_id: str) -> Optional[Any]:
        """Get cached context status"""
        cached = self._context_cache.get(session_id)
        if self._is_cache_valid(cached):
            return cached.data
        return None

    def invalidate_context(self, session_id: str):
        """Invalidate cached context status"""
        self._context_cache.pop(session_id, None)

    # Runtime Status Methods

    def cache_runtime_status(self, key: str, status: Any, ttl_ms: Optional[int] = None):
        """Cache runtime status"""
        ttl = ttl_ms or self.default_runtime_ttl_ms
        self._runtime_cache[key] = self._cache_entry(status, ttl)

    def get_cached_runtime_status(self, key: str) -> Optional[Any]:
        """Get cached runtime status"""
        cached = self._runtime_cache.get(key)
        if self._is_cache_valid(cached):
            return cached.data
        return None

    def invalidate_runtime(self, key: str):
        """Invalidate cached runtime status"""
        self._runtime_cache.pop(key, None)

    # Global Operations

    def clear_all(self):
        """Clear all caches"""
        self._provider_cache.clear()
        self._context_cache.clear()
        self._runtime_cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        now = time.time()

        provider_valid = sum(
            1 for c in self._provider_cache.values()
            if (now - c.cached_at) * 1000 < c.ttl_ms
        )
        context_valid = sum(
            1 for c in self._context_cache.values()
            if (now - c.cached_at) * 1000 < c.ttl_ms
        )
        runtime_valid = sum(
            1 for c in self._runtime_cache.values()
            if (now - c.cached_at) * 1000 < c.ttl_ms
        )

        return {
            "providers": {
                "total": len(self._provider_cache),
                "valid": provider_valid,
                "expired": len(self._provider_cache) - provider_valid,
            },
            "context": {
                "total": len(self._context_cache),
                "valid": context_valid,
                "expired": len(self._context_cache) - context_valid,
            },
            "runtime": {
                "total": len(self._runtime_cache),
                "valid": runtime_valid,
                "expired": len(self._runtime_cache) - runtime_valid,
            },
        }
