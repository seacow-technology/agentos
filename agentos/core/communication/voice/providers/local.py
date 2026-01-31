"""Local WebSocket voice provider.

This provider implements voice communication over local WebSocket
connections, suitable for browser-based voice interfaces and
development/testing environments.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from agentos.core.communication.voice.providers.base import IVoiceProvider

logger = logging.getLogger(__name__)


class LocalProvider(IVoiceProvider):
    """Local WebSocket-based voice provider.

    The LocalProvider handles voice sessions over WebSocket connections,
    typically used for:
    - Browser-based voice interfaces (WebRTC + WebSocket)
    - Development and testing environments
    - Internal agent-to-agent voice communication

    Transport: WebSocket
    Protocol: Custom binary audio frames
    Authentication: Session tokens
    """

    def __init__(self):
        """Initialize local voice provider."""
        self.transport = "websocket"
        self.protocol = "custom_binary"
        self.supports_recording = True
        self.max_duration_seconds = 3600  # 1 hour max session

    def get_session_metadata(self) -> Dict[str, Any]:
        """Get provider-specific session metadata.

        Returns:
            Dictionary with provider metadata
        """
        return {
            "transport": self.transport,
            "protocol": self.protocol,
            "supports_recording": self.supports_recording,
            "max_duration_seconds": self.max_duration_seconds,
            "connection_type": "local",
            "requires_internet": False,
        }

    def validate_config(self) -> tuple[bool, str]:
        """Validate provider configuration.

        Local provider has no external dependencies, so validation
        always succeeds.

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, "Local provider configuration valid"

    def on_session_created(self, session_id: str, metadata: Dict[str, Any]) -> None:
        """Hook called when a session is created.

        Args:
            session_id: The newly created session ID
            metadata: Session metadata
        """
        logger.info(
            f"Local voice session created: {session_id} "
            f"(metadata: {metadata})"
        )

    def on_session_stopped(self, session_id: str) -> None:
        """Hook called when a session is stopped.

        Args:
            session_id: The stopped session ID
        """
        logger.info(f"Local voice session stopped: {session_id}")
