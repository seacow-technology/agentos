"""LLM output cache for reducing token consumption.

This module provides LLMOutputCache for caching and reusing LLM outputs,
significantly reducing token consumption and latency for repeated requests.

Key Features:
- Cache LLM outputs by prompt + model hash
- Automatic cache hit detection
- Configurable cache expiration
- Token savings tracking
- Support for both plan and work_item outputs

Example:
    cache = LLMOutputCache()

    # Cache plan generation
    plan = cache.get_or_generate(
        operation_type="plan",
        prompt="Write a plan for task X",
        model="gpt-4",
        task_id="task-123",
        generate_fn=lambda: call_llm(prompt)
    )

    # Cache work item execution
    result = cache.get_or_generate(
        operation_type="work_item",
        prompt="Execute step 1",
        model="gpt-4",
        task_id="task-123",
        work_item_id="work-456",
        generate_fn=lambda: call_llm(prompt)
    )
"""

import logging
from typing import Any, Callable, Dict, Optional

from agentos.core.idempotency.store import IdempotencyStore

logger = logging.getLogger(__name__)


class LLMOutputCache:
    """Cache for LLM outputs to reduce token consumption.

    Uses IdempotencyStore under the hood with cache keys based on:
    - operation_type (plan, work_item, etc.)
    - prompt content
    - model name
    - task context

    This ensures that identical LLM requests return cached results,
    avoiding redundant API calls and token consumption.
    """

    def __init__(self, store: Optional[IdempotencyStore] = None):
        """Initialize LLM output cache.

        Args:
            store: Optional IdempotencyStore instance. If None, creates new one.
        """
        self.store = store or IdempotencyStore()
        self._cache_hits = 0
        self._cache_misses = 0

    def get_or_generate(
        self,
        operation_type: str,
        prompt: str,
        model: str,
        generate_fn: Callable[[], Dict[str, Any]],
        task_id: Optional[str] = None,
        work_item_id: Optional[str] = None,
        expires_in_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get cached LLM output or generate new one.

        Args:
            operation_type: Type of operation (plan, work_item, etc.)
            prompt: LLM prompt text
            model: Model name (gpt-4, claude-3, etc.)
            generate_fn: Function to call if cache miss (should return dict)
            task_id: Optional task ID for tracking
            work_item_id: Optional work item ID for tracking
            expires_in_seconds: Cache expiration (default: 7 days)

        Returns:
            LLM output dictionary (either cached or newly generated)

        Example:
            output = cache.get_or_generate(
                operation_type="plan",
                prompt="Write a plan for X",
                model="gpt-4",
                task_id="task-123",
                generate_fn=lambda: {"content": call_llm(prompt), "tokens": 150}
            )
        """
        # Build cache key
        cache_key = self._build_cache_key(
            operation_type, prompt, model, task_id, work_item_id
        )

        # Compute request hash
        request_data = {
            "operation_type": operation_type,
            "prompt": prompt,
            "model": model,
            "task_id": task_id,
            "work_item_id": work_item_id,
        }
        request_hash = IdempotencyStore.compute_hash(request_data)

        # Check cache or create entry
        expires_in = expires_in_seconds or (7 * 24 * 3600)  # Default 7 days
        is_cached, cached_result = self.store.check_or_create(
            key=cache_key,
            request_hash=request_hash,
            task_id=task_id,
            work_item_id=work_item_id,
            expires_in_seconds=expires_in
        )

        if is_cached:
            # Cache hit
            self._cache_hits += 1
            logger.info(
                f"LLM cache HIT: operation={operation_type}, "
                f"model={model}, task_id={task_id}"
            )
            return cached_result

        # Cache miss - generate new output
        self._cache_misses += 1
        logger.info(
            f"LLM cache MISS: operation={operation_type}, "
            f"model={model}, task_id={task_id}"
        )

        try:
            # Generate new output
            result = generate_fn()

            # Cache the result
            self.store.mark_succeeded(cache_key, result)

            return result

        except Exception as e:
            # Mark as failed
            self.store.mark_failed(cache_key, str(e))
            raise

    def invalidate(
        self,
        operation_type: str,
        prompt: str,
        model: str,
        task_id: Optional[str] = None,
        work_item_id: Optional[str] = None
    ) -> None:
        """Invalidate cached entry (mark as failed).

        Useful when you know the cached result is stale or incorrect.

        Args:
            operation_type: Type of operation
            prompt: LLM prompt text
            model: Model name
            task_id: Optional task ID
            work_item_id: Optional work item ID
        """
        cache_key = self._build_cache_key(
            operation_type, prompt, model, task_id, work_item_id
        )
        self.store.mark_failed(cache_key, "Manually invalidated")
        logger.info(f"Invalidated LLM cache entry: key={cache_key}")

    def _build_cache_key(
        self,
        operation_type: str,
        prompt: str,
        model: str,
        task_id: Optional[str],
        work_item_id: Optional[str]
    ) -> str:
        """Build cache key from parameters.

        Format: llm-cache:{operation_type}:{model}:{prompt_hash}[:task_id][:work_item_id]

        Args:
            operation_type: Type of operation
            prompt: LLM prompt
            model: Model name
            task_id: Optional task ID
            work_item_id: Optional work item ID

        Returns:
            Cache key string
        """
        # Hash prompt to keep key size reasonable
        prompt_hash = IdempotencyStore.compute_hash(prompt).split(":")[1][:16]

        # Build key components
        parts = [
            "llm-cache",
            operation_type,
            model,
            prompt_hash
        ]

        if task_id:
            parts.append(task_id)
        if work_item_id:
            parts.append(work_item_id)

        return ":".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with:
            - cache_hits: Number of cache hits
            - cache_misses: Number of cache misses
            - hit_rate: Cache hit rate (0-1)
            - total_requests: Total requests
            - store_stats: Statistics from underlying IdempotencyStore
        """
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0.0

        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate,
            "total_requests": total,
            "store_stats": self.store.get_stats(),
        }

    def reset_stats(self) -> None:
        """Reset cache statistics counters."""
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("Reset LLM cache statistics")
