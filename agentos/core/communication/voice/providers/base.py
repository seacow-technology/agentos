"""Base interface for voice providers.

This module defines the abstract interface that all voice providers
must implement, ensuring consistent behavior across different backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class IVoiceProvider(ABC):
    """Abstract base class for voice communication providers.

    Voice providers handle the low-level transport and connectivity
    for voice sessions. Different providers may use WebSockets,
    SIP, PSTN, or other protocols.

    Implementations must provide:
    - Session metadata (transport type, capabilities)
    - Configuration validation
    - Optional connection management hooks
    """

    @abstractmethod
    def get_session_metadata(self) -> Dict[str, Any]:
        """Get provider-specific session metadata.

        This metadata describes the provider's capabilities,
        transport mechanism, and configuration.

        Returns:
            Dictionary with provider metadata

        Example:
            {
                "transport": "websocket",
                "protocol": "webrtc",
                "supports_recording": True,
                "max_duration_seconds": 3600,
            }
        """
        pass

    @abstractmethod
    def validate_config(self) -> tuple[bool, str]:
        """Validate provider configuration.

        Checks that all required configuration parameters are
        present and valid before allowing session creation.

        Returns:
            Tuple of (is_valid, error_message)

        Example:
            >>> provider.validate_config()
            (True, "Configuration valid")
        """
        pass

    def on_session_created(self, session_id: str, metadata: Dict[str, Any]) -> None:
        """Hook called when a session is created.

        Optional hook for providers to perform initialization
        tasks when a new session is created.

        Args:
            session_id: The newly created session ID
            metadata: Session metadata
        """
        pass

    def on_session_stopped(self, session_id: str) -> None:
        """Hook called when a session is stopped.

        Optional hook for providers to perform cleanup tasks
        when a session is stopped.

        Args:
            session_id: The stopped session ID
        """
        pass


class IVoiceTransportProvider(ABC):
    """Abstract base class for voice transport layer providers.

    Transport providers handle the physical layer of voice communication,
    including audio encoding/decoding, stream management, and protocol-specific
    event handling. This is a lower-level interface than IVoiceProvider.

    Transport providers are responsible for:
    - Connecting to external voice streams (Twilio, WebRTC, etc.)
    - Audio transcoding (μ-law, PCM, Opus, etc.)
    - Sending and receiving audio chunks
    - Handling transport-specific control messages
    - Session lifecycle management (connect, disconnect)

    Example implementations:
    - TwilioStreamsTransportProvider: Twilio Media Streams (μ-law ↔ PCM)
    - WebRTCTransportProvider: WebRTC (Opus ↔ PCM)
    - SIPTransportProvider: SIP/RTP (G.711 ↔ PCM)
    """

    @abstractmethod
    async def connect(self, connection_params: Dict[str, Any]) -> Dict[str, Any]:
        """Connect to the external voice stream.

        Establishes connection to the transport layer and returns
        connection metadata (stream IDs, capabilities, etc.).

        Args:
            connection_params: Provider-specific connection parameters
                For Twilio: {"call_sid": "CA...", "stream_sid": "MZ..."}
                For WebRTC: {"ice_servers": [...], "session_id": "..."}

        Returns:
            Connection metadata dictionary with transport-specific info

        Raises:
            ConnectionError: If connection fails
            ValueError: If connection_params are invalid
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the voice stream.

        Gracefully closes the connection and releases resources.
        Should be idempotent (safe to call multiple times).
        """
        pass

    @abstractmethod
    async def send_audio_chunk(self, pcm_data: bytes) -> None:
        """Send PCM audio chunk to the external stream.

        Transcodes PCM audio to the transport's native format
        (e.g., μ-law for Twilio) and sends it to the stream.

        Args:
            pcm_data: Raw PCM s16le audio data (mono, 16kHz recommended)

        Raises:
            RuntimeError: If not connected
            ValueError: If audio data is invalid
        """
        pass

    @abstractmethod
    async def receive_audio_chunk(self) -> Optional[bytes]:
        """Receive audio chunk from the external stream.

        Receives audio from the transport layer and transcodes it
        to PCM s16le format for internal processing.

        Returns:
            PCM s16le audio data (mono, 16kHz), or None if no data available

        Raises:
            RuntimeError: If not connected
        """
        pass

    @abstractmethod
    async def send_control(self, command: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Send control command to the transport layer.

        Commands vary by transport type. Common commands:
        - "pause": Pause audio transmission
        - "resume": Resume audio transmission
        - "clear": Clear audio buffer
        - "mark": Send mark event (Twilio)

        Args:
            command: Control command name
            params: Optional command parameters

        Raises:
            RuntimeError: If not connected
            ValueError: If command is not supported
        """
        pass

    @abstractmethod
    def get_transport_metadata(self) -> Dict[str, Any]:
        """Get current transport metadata.

        Returns runtime metadata about the transport connection,
        including stream IDs, connection status, and statistics.

        Returns:
            Dictionary with transport metadata

        Example (Twilio):
            {
                "call_sid": "CA1234...",
                "stream_sid": "MZ5678...",
                "from_number": "+1234567890",
                "to_number": "+0987654321",
                "call_status": "in-progress",
                "connected": True,
                "bytes_sent": 12345,
                "bytes_received": 54321,
            }
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if transport is currently connected.

        Returns:
            True if connected and ready for audio transmission
        """
        pass
