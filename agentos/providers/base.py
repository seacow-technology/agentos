"""
Base classes for Provider abstraction

v0.3.2 Closeout: Added reason_code and hint for status explanation
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime, timezone


class ProviderType(str, Enum):
    """Provider type"""
    LOCAL = "local"
    CLOUD = "cloud"


class ProviderState(str, Enum):
    """Provider connection state"""
    DISCONNECTED = "DISCONNECTED"
    READY = "READY"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


@dataclass
class ProviderStatus:
    """
    Provider status snapshot

    v0.3.2 Closeout: Added reason_code and hint for standardized status explanation
    """
    id: str
    type: ProviderType
    state: ProviderState
    endpoint: Optional[str] = None
    latency_ms: Optional[float] = None
    last_ok_at: Optional[str] = None
    last_error: Optional[str] = None
    reason_code: Optional[str] = None  # Standard reason code (from ReasonCode enum)
    hint: Optional[str] = None  # User-facing hint for resolution


@dataclass
class ModelInfo:
    """Model information"""
    id: str
    label: str
    context_window: Optional[int] = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class Provider(ABC):
    """Abstract base class for all providers"""

    def __init__(
        self,
        provider_id: str,
        provider_type: ProviderType,
        instance_id: str = "default",
    ):
        self.provider_id = provider_id  # Provider type (e.g., "ollama", "llamacpp")
        self.instance_id = instance_id  # Instance identifier (e.g., "default", "glm47flash-q8")
        self.id = f"{provider_id}:{instance_id}" if instance_id != "default" else provider_id
        self.type = provider_type
        self._last_status: Optional[ProviderStatus] = None
        self._last_check: Optional[datetime] = None

    @abstractmethod
    async def probe(self) -> ProviderStatus:
        """
        Probe provider health and return status

        This should be fast (< 1.5s) and non-blocking.
        Returns current connection state.
        """
        pass

    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        """
        List available models from this provider

        Returns empty list if provider is not available.
        """
        pass

    def get_cached_status(self) -> Optional[ProviderStatus]:
        """Get last cached status (if available)"""
        return self._last_status

    def _cache_status(self, status: ProviderStatus):
        """
        Cache status result and emit event if state changed

        Sprint B Task #4: Emit provider.status_changed event
        """
        # Check if state actually changed
        state_changed = (
            self._last_status is None
            or self._last_status.state != status.state
        )

        self._last_status = status
        self._last_check = datetime.now(timezone.utc)

        # Emit event if state changed
        if state_changed:
            try:
                from agentos.core.events import Event, get_event_bus

                event = Event.provider_status_changed(
                    provider_id=self.id,
                    state=status.state.value,
                    details={
                        "endpoint": status.endpoint,
                        "latency_ms": status.latency_ms,
                        "last_error": status.last_error,
                    },
                )

                get_event_bus().emit(event)
            except Exception as e:
                # Don't let event emission crash provider logic
                import logging
                logging.getLogger(__name__).warning(f"Failed to emit provider event: {e}")

    @staticmethod
    def now_iso() -> str:
        """Get current time in ISO format"""
        return datetime.now(timezone.utc).isoformat()
