"""
Event Bus - Central event broadcasting system

Sprint B Task #4: Event bus implementation

Architecture:
- Singleton pattern (get_event_bus())
- Subscriber pattern (callback-based)
- Async event delivery
- Drop-oldest policy for queue overflow
"""

import asyncio
import logging
from typing import Callable, List, Optional, Coroutine, Any
from datetime import datetime

from agentos.core.events.types import Event


logger = logging.getLogger(__name__)


class EventBus:
    """
    Central event bus for AgentOS

    Zero coupling: Core emits events, WebUI/loggers subscribe.
    """

    _instance: Optional["EventBus"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._subscribers: List[Callable[[Event], None]] = []
        self._async_subscribers: List[Callable[[Event], Coroutine[Any, Any, None]]] = []
        self._max_queue_size = 1000  # Per-subscriber queue limit

    @classmethod
    async def get_instance(cls) -> "EventBus":
        """Get singleton instance (thread-safe)"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    logger.info("EventBus initialized")
        return cls._instance

    def subscribe(self, callback: Callable[[Event], None]):
        """
        Subscribe to all events (sync callback)

        Callback will be invoked on every event emission.
        """
        if callback not in self._subscribers:
            self._subscribers.append(callback)
            logger.info(f"Subscriber registered: {callback.__name__}")

    def subscribe_async(self, callback: Callable[[Event], Coroutine[Any, Any, None]]):
        """
        Subscribe to all events (async callback)

        Callback should be an async function.
        """
        if callback not in self._async_subscribers:
            self._async_subscribers.append(callback)
            logger.info(f"Async subscriber registered: {callback.__name__}")

    def unsubscribe(self, callback: Callable):
        """Unsubscribe from events"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
            logger.info(f"Subscriber unregistered: {callback.__name__}")

        if callback in self._async_subscribers:
            self._async_subscribers.remove(callback)
            logger.info(f"Async subscriber unregistered: {callback.__name__}")

    def emit(self, event: Event):
        """
        Emit event to all subscribers (sync)

        This is a fire-and-forget call. Subscribers are notified
        but Core doesn't wait for them.
        """
        logger.debug(f"Event emitted: {event.type.value} (entity: {event.entity.id if event.entity else 'N/A'})")

        # Notify sync subscribers
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Subscriber error ({callback.__name__}): {e}", exc_info=True)

        # Schedule async subscribers (don't block)
        for callback in self._async_subscribers:
            try:
                asyncio.create_task(self._safe_async_call(callback, event))
            except Exception as e:
                logger.error(f"Async subscriber error ({callback.__name__}): {e}", exc_info=True)

    async def emit_async(self, event: Event):
        """
        Emit event to all subscribers (async)

        Waits for async subscribers to complete.
        """
        logger.debug(f"Event emitted (async): {event.type.value}")

        # Notify sync subscribers
        for callback in self._subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Subscriber error ({callback.__name__}): {e}", exc_info=True)

        # Notify async subscribers (await)
        tasks = [self._safe_async_call(callback, event) for callback in self._async_subscribers]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_async_call(self, callback: Callable, event: Event):
        """Safely call async callback with error handling"""
        try:
            await callback(event)
        except Exception as e:
            logger.error(f"Async callback error ({callback.__name__}): {e}", exc_info=True)

    def subscriber_count(self) -> int:
        """Get total subscriber count (for monitoring)"""
        return len(self._subscribers) + len(self._async_subscribers)


# Singleton accessor (convenience function)
_global_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """
    Get global EventBus instance (sync accessor)

    Note: This is a sync wrapper around async get_instance().
    Use this in sync contexts where you can't await.
    """
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
        logger.info("EventBus created (sync accessor)")
    return _global_bus


async def get_event_bus_async() -> EventBus:
    """Get global EventBus instance (async accessor)"""
    return await EventBus.get_instance()
