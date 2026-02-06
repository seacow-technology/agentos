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
    """
    Provider connection state

    Task #17: P0.4 - Enhanced with additional states for accurate status detection
    """
    UNKNOWN = "UNKNOWN"          # Initial state, not yet checked
    STOPPED = "STOPPED"          # Confirmed not running
    STARTING = "STARTING"        # Starting up (transitional state)
    RUNNING = "RUNNING"          # Confirmed running (PID + health check passed)
    DEGRADED = "DEGRADED"        # Partially available (PID exists but API not responding)
    ERROR = "ERROR"              # Startup failed or abnormal exit
    # Legacy states mapped to new ones:
    DISCONNECTED = "STOPPED"     # Alias for backward compatibility
    READY = "RUNNING"            # Alias for backward compatibility


@dataclass
class ProviderStatus:
    """
    Provider status snapshot

    v0.3.2 Closeout: Added reason_code and hint for standardized status explanation
    Task #17: P0.4 - Enhanced with health check details
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
    # Task #17: Health check details
    pid: Optional[int] = None  # Process ID (if managed locally)
    pid_exists: Optional[bool] = None  # Whether PID is alive
    port_listening: Optional[bool] = None  # Whether port is accessible
    api_responding: Optional[bool] = None  # Whether API endpoint responds


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

        Task #17: Enhanced to include detailed health check information
        """
        pass

    async def health_check_with_pid(self, pid: int) -> dict:
        """
        Multi-layer health check when PID is available.

        Task #17: P0.4 - Health check implementation

        Checks:
        1. psutil.pid_exists(pid) - Process exists
        2. Port listening check (optional) - socket connection test
        3. HTTP health endpoint (optional) - call /health or /api/tags

        Args:
            pid: Process ID to check

        Returns:
            dict: {
                "pid_exists": bool,
                "port_listening": bool,
                "api_responding": bool,
                "status": "RUNNING" | "DEGRADED" | "STOPPED"
            }
        """
        import psutil
        import socket

        result = {
            "pid_exists": False,
            "port_listening": False,
            "api_responding": False,
            "status": "STOPPED"
        }

        # Layer 1: Check if PID exists
        try:
            result["pid_exists"] = psutil.pid_exists(pid)
        except Exception:
            result["pid_exists"] = False

        if not result["pid_exists"]:
            result["status"] = "STOPPED"
            return result

        # Layer 2: Check port listening (if endpoint is available)
        if hasattr(self, 'endpoint') and self.endpoint:
            try:
                # Extract host and port from endpoint
                import re
                from urllib.parse import urlparse
                parsed = urlparse(self.endpoint)
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port

                if port:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1.0)
                    result["port_listening"] = sock.connect_ex((host, port)) == 0
                    sock.close()
            except Exception:
                result["port_listening"] = False

        # Layer 3: Check API responding
        try:
            import httpx
            async with httpx.AsyncClient(timeout=1.0) as client:
                # Try common health endpoints
                endpoints_to_try = []
                if hasattr(self, 'endpoint') and self.endpoint:
                    endpoints_to_try = [
                        f"{self.endpoint}/health",
                        f"{self.endpoint}/api/tags",
                        f"{self.endpoint}/v1/models",
                    ]

                for endpoint in endpoints_to_try:
                    try:
                        response = await client.get(endpoint)
                        if response.status_code == 200:
                            result["api_responding"] = True
                            break
                    except Exception:
                        continue
        except Exception:
            result["api_responding"] = False

        # Determine status
        if result["api_responding"]:
            result["status"] = "RUNNING"
        elif result["pid_exists"] and result["port_listening"]:
            result["status"] = "DEGRADED"  # Process exists, port open, but API not responding
        elif result["pid_exists"]:
            result["status"] = "DEGRADED"  # Process exists but not ready
        else:
            result["status"] = "STOPPED"

        return result

    async def health_check_no_pid(self) -> dict:
        """
        Health check when PID is not available (e.g., externally started provider).

        Task #17: P0.4 - Health check for external providers

        Checks:
        1. Port probing - socket connection
        2. API endpoint probing - HTTP request

        Returns:
            dict: {
                "port_listening": bool,
                "api_responding": bool,
                "status": "RUNNING" | "STOPPED" | "UNKNOWN"
            }
        """
        import socket

        result = {
            "port_listening": False,
            "api_responding": False,
            "status": "UNKNOWN"
        }

        if not hasattr(self, 'endpoint') or not self.endpoint:
            result["status"] = "UNKNOWN"
            return result

        # Layer 1: Check port listening
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.endpoint)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port

            if port:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                result["port_listening"] = sock.connect_ex((host, port)) == 0
                sock.close()
        except Exception:
            result["port_listening"] = False

        # Layer 2: Check API responding
        try:
            import httpx
            async with httpx.AsyncClient(timeout=1.0) as client:
                # Try common health endpoints
                endpoints_to_try = [
                    f"{self.endpoint}/health",
                    f"{self.endpoint}/api/tags",
                    f"{self.endpoint}/v1/models",
                ]

                for endpoint in endpoints_to_try:
                    try:
                        response = await client.get(endpoint)
                        if response.status_code == 200:
                            result["api_responding"] = True
                            break
                    except Exception:
                        continue
        except Exception:
            result["api_responding"] = False

        # Determine status
        if result["api_responding"]:
            result["status"] = "RUNNING"
        elif result["port_listening"]:
            result["status"] = "DEGRADED"  # Port open but API not responding
        else:
            result["status"] = "STOPPED"

        return result

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
