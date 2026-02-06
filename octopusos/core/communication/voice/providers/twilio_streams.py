"""Twilio Media Streams transport provider implementation.

This module implements the transport layer for Twilio Media Streams,
handling μ-law ↔ PCM audio transcoding and stream lifecycle management.

Twilio Media Streams provides bi-directional audio streaming over WebSocket
using μ-law encoding at 8kHz sample rate. This provider transcodes between
μ-law and PCM s16le for compatibility with internal audio processing.

References:
- https://www.twilio.com/docs/voice/media-streams
- μ-law encoding: ITU-T G.711

Usage Example:
    >>> provider = TwilioStreamsTransportProvider()
    >>> metadata = await provider.connect({
    ...     "call_sid": "CA1234567890abcdef",
    ...     "stream_sid": "MZ9876543210fedcba",
    ... })
    >>> # Send PCM audio (will be transcoded to μ-law)
    >>> await provider.send_audio_chunk(pcm_audio_bytes)
    >>> # Receive μ-law audio (will be transcoded to PCM)
    >>> pcm_data = await provider.receive_audio_chunk()
    >>> await provider.disconnect()
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, Optional
from datetime import datetime

import numpy as np

from agentos.core.time import utc_now
from agentos.core.communication.voice.providers.base import IVoiceTransportProvider

logger = logging.getLogger(__name__)


# μ-law encoding/decoding lookup tables (ITU-T G.711)
# These are precomputed for performance
_MULAW_BIAS = 33
_MULAW_MAX = 0x1FFF

# μ-law compression lookup table (PCM to μ-law)
_MULAW_ENCODE_TABLE = None
# μ-law expansion lookup table (μ-law to PCM)
_MULAW_DECODE_TABLE = None


def _init_mulaw_tables():
    """Initialize μ-law encoding/decoding lookup tables.

    This function creates precomputed lookup tables for fast μ-law
    encoding and decoding, following ITU-T G.711 standard.
    """
    global _MULAW_ENCODE_TABLE, _MULAW_DECODE_TABLE

    if _MULAW_ENCODE_TABLE is not None:
        return

    # Create encoding table (PCM s16 → μ-law)
    _MULAW_ENCODE_TABLE = np.zeros(65536, dtype=np.uint8)
    for i in range(65536):
        # Convert unsigned 16-bit to signed 16-bit
        pcm = i if i < 32768 else i - 65536

        # Apply μ-law compression
        sign = 0 if pcm >= 0 else 0x80
        if pcm < 0:
            pcm = -pcm

        pcm = pcm + _MULAW_BIAS
        if pcm > _MULAW_MAX:
            pcm = _MULAW_MAX

        # Find exponent
        exponent = 7
        for exp_mask in [0x4000, 0x2000, 0x1000, 0x0800, 0x0400, 0x0200, 0x0100]:
            if pcm & exp_mask:
                exponent = exp_mask.bit_length() - 9
                break
        else:
            exponent = 0

        mantissa = (pcm >> (exponent + 3)) & 0x0F
        mulaw = ~(sign | (exponent << 4) | mantissa) & 0xFF
        _MULAW_ENCODE_TABLE[i] = mulaw

    # Create decoding table (μ-law → PCM s16)
    _MULAW_DECODE_TABLE = np.zeros(256, dtype=np.int16)
    for i in range(256):
        mulaw = ~i & 0xFF
        sign = -1 if mulaw & 0x80 else 1
        exponent = (mulaw >> 4) & 0x07
        mantissa = mulaw & 0x0F

        sample = ((mantissa << 3) + _MULAW_BIAS) << exponent
        sample -= _MULAW_BIAS

        _MULAW_DECODE_TABLE[i] = sign * sample


# Initialize tables on module load
_init_mulaw_tables()


class TwilioStreamsTransportProvider(IVoiceTransportProvider):
    """Twilio Media Streams transport provider.

    Handles bi-directional audio streaming with Twilio Media Streams,
    including μ-law ↔ PCM transcoding and Twilio-specific event handling.

    Audio Specifications:
    - Twilio format: μ-law (G.711), 8kHz, mono
    - Internal format: PCM s16le, 16kHz, mono
    - Payload encoding: base64 (for JSON transport)

    Twilio Events:
    - "start": Stream started (provides call_sid, stream_sid)
    - "media": Audio payload (base64-encoded μ-law)
    - "stop": Stream stopped
    - "mark": Mark event (for synchronization)

    Attributes:
        active_streams: Dictionary of active stream metadata by call_sid
        current_call_sid: Currently active call SID
        connected: Connection status flag
        stats: Transcoding and transmission statistics
    """

    # Twilio Media Streams audio format
    TWILIO_SAMPLE_RATE = 8000  # Hz
    TWILIO_CHANNELS = 1  # mono
    TWILIO_ENCODING = "ulaw"  # μ-law (G.711)

    # Internal audio format
    INTERNAL_SAMPLE_RATE = 16000  # Hz
    INTERNAL_CHANNELS = 1  # mono
    INTERNAL_ENCODING = "pcm_s16le"  # PCM signed 16-bit little-endian

    def __init__(self):
        """Initialize Twilio Media Streams transport provider."""
        self.active_streams: Dict[str, Dict[str, Any]] = {}
        self.current_call_sid: Optional[str] = None
        self.connected: bool = False

        # Statistics tracking
        self.stats = {
            "bytes_sent": 0,
            "bytes_received": 0,
            "chunks_sent": 0,
            "chunks_received": 0,
            "transcode_errors": 0,
            "marks_sent": 0,
        }

        logger.info("TwilioStreamsTransportProvider initialized")

    async def connect(self, connection_params: Dict[str, Any]) -> Dict[str, Any]:
        """Connect to Twilio Media Stream.

        Establishes connection and registers stream metadata.

        Args:
            connection_params: Connection parameters
                Required:
                - call_sid: Twilio Call SID (e.g., "CA1234...")
                - stream_sid: Twilio Stream SID (e.g., "MZ5678...")
                Optional:
                - from_number: Caller phone number
                - to_number: Called phone number
                - call_status: Call status (e.g., "in-progress")

        Returns:
            Connection metadata dictionary

        Raises:
            ValueError: If required parameters are missing
            ConnectionError: If already connected to a different call

        Example:
            >>> metadata = await provider.connect({
            ...     "call_sid": "CA1234567890abcdef",
            ...     "stream_sid": "MZ9876543210fedcba",
            ...     "from_number": "+14155551234",
            ...     "to_number": "+14155559876",
            ... })
        """
        # Validate required parameters
        call_sid = connection_params.get("call_sid")
        stream_sid = connection_params.get("stream_sid")

        if not call_sid:
            raise ValueError("call_sid is required in connection_params")
        if not stream_sid:
            raise ValueError("stream_sid is required in connection_params")

        # Validate SID format
        if not call_sid.startswith("CA"):
            raise ValueError(f"Invalid call_sid format: {call_sid} (should start with CA)")
        if not stream_sid.startswith("MZ"):
            raise ValueError(f"Invalid stream_sid format: {stream_sid} (should start with MZ)")

        # Check if already connected to a different call
        if self.connected and self.current_call_sid != call_sid:
            raise ConnectionError(
                f"Already connected to call {self.current_call_sid}, "
                f"cannot connect to {call_sid}"
            )

        # Create stream metadata
        stream_metadata = {
            "call_sid": call_sid,
            "stream_sid": stream_sid,
            "from_number": connection_params.get("from_number"),
            "to_number": connection_params.get("to_number"),
            "call_status": connection_params.get("call_status", "unknown"),
            "start_time": utc_now(),
            "connected": True,
        }

        # Register stream
        self.active_streams[call_sid] = stream_metadata
        self.current_call_sid = call_sid
        self.connected = True

        logger.info(
            f"Connected to Twilio stream: call_sid={call_sid}, "
            f"stream_sid={stream_sid}, from={stream_metadata['from_number']}, "
            f"to={stream_metadata['to_number']}"
        )

        return stream_metadata

    async def disconnect(self) -> None:
        """Disconnect from Twilio Media Stream.

        Gracefully closes the stream connection and cleans up resources.
        Idempotent (safe to call multiple times).
        """
        if not self.connected:
            logger.debug("disconnect() called but not connected")
            return

        call_sid = self.current_call_sid

        # Mark stream as disconnected
        if call_sid and call_sid in self.active_streams:
            self.active_streams[call_sid]["connected"] = False
            self.active_streams[call_sid]["end_time"] = utc_now()

        # Reset connection state
        self.connected = False
        self.current_call_sid = None

        logger.info(
            f"Disconnected from Twilio stream: call_sid={call_sid}, "
            f"stats={self.stats}"
        )

    async def send_audio_chunk(self, pcm_data: bytes) -> None:
        """Send PCM audio chunk to Twilio (transcoded to μ-law).

        Transcodes PCM s16le audio to μ-law and sends it to the
        Twilio Media Stream. Audio is base64-encoded for JSON transport.

        Args:
            pcm_data: Raw PCM s16le audio data (mono, 16kHz recommended)

        Raises:
            RuntimeError: If not connected
            ValueError: If audio data is invalid or empty

        Note:
            If input is 16kHz and Twilio expects 8kHz, downsampling
            is performed automatically via audioop.ratecv().
        """
        if not self.connected:
            raise RuntimeError("Cannot send audio: not connected to Twilio stream")

        if not pcm_data:
            raise ValueError("pcm_data cannot be empty")

        try:
            # Transcode PCM to μ-law
            mulaw_data = self._transcode_pcm_to_mulaw(pcm_data)

            # Encode as base64 for JSON transport
            mulaw_base64 = base64.b64encode(mulaw_data).decode("utf-8")

            # Update statistics
            self.stats["bytes_sent"] += len(mulaw_data)
            self.stats["chunks_sent"] += 1

            # In production, this would send to WebSocket:
            # await websocket.send_json({
            #     "event": "media",
            #     "streamSid": self.active_streams[self.current_call_sid]["stream_sid"],
            #     "media": {"payload": mulaw_base64}
            # })

            logger.debug(
                f"Sent audio chunk: {len(pcm_data)} bytes PCM → "
                f"{len(mulaw_data)} bytes μ-law (base64: {len(mulaw_base64)} chars)"
            )

        except Exception as e:
            self.stats["transcode_errors"] += 1
            logger.error(f"Failed to send audio chunk: {e}")
            raise

    async def receive_audio_chunk(self) -> Optional[bytes]:
        """Receive μ-law audio from Twilio (transcoded to PCM).

        Receives μ-law audio from Twilio Media Stream and transcodes
        it to PCM s16le format for internal processing.

        Returns:
            PCM s16le audio data (mono, 16kHz), or None if no data available

        Raises:
            RuntimeError: If not connected

        Note:
            In a real implementation, this would read from a WebSocket
            queue. This MVP returns None (no data) for demonstration.
        """
        if not self.connected:
            raise RuntimeError("Cannot receive audio: not connected to Twilio stream")

        # In production, this would receive from WebSocket:
        # message = await websocket.receive_json()
        # if message["event"] == "media":
        #     mulaw_base64 = message["media"]["payload"]
        #     mulaw_data = base64.b64decode(mulaw_base64)
        #     pcm_data = self._transcode_mulaw_to_pcm(mulaw_data)
        #     self.stats["bytes_received"] += len(mulaw_data)
        #     self.stats["chunks_received"] += 1
        #     return pcm_data

        # MVP: Return None (no data available)
        return None

    async def send_control(self, command: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Send control command to Twilio Media Stream.

        Supported commands:
        - "mark": Send mark event for synchronization (requires "name" param)
        - "clear": Clear audio buffer (Twilio-specific)

        Args:
            command: Control command name
            params: Optional command parameters

        Raises:
            RuntimeError: If not connected
            ValueError: If command is not supported or params are invalid

        Example:
            >>> await provider.send_control("mark", {"name": "segment_end"})
        """
        if not self.connected:
            raise RuntimeError("Cannot send control: not connected to Twilio stream")

        if command == "mark":
            # Twilio mark event for synchronization
            if not params or "name" not in params:
                raise ValueError("mark command requires 'name' parameter")

            mark_name = params["name"]
            self.stats["marks_sent"] += 1

            # In production, send to WebSocket:
            # await websocket.send_json({
            #     "event": "mark",
            #     "streamSid": self.active_streams[self.current_call_sid]["stream_sid"],
            #     "mark": {"name": mark_name}
            # })

            logger.debug(f"Sent mark event: {mark_name}")

        elif command == "clear":
            # Twilio-specific: clear audio buffer
            # In production, send to WebSocket:
            # await websocket.send_json({
            #     "event": "clear",
            #     "streamSid": self.active_streams[self.current_call_sid]["stream_sid"]
            # })

            logger.debug("Sent clear command")

        else:
            raise ValueError(f"Unsupported control command: {command}")

    def get_transport_metadata(self) -> Dict[str, Any]:
        """Get current transport metadata.

        Returns runtime metadata about the Twilio stream connection,
        including call/stream IDs, phone numbers, and statistics.

        Returns:
            Dictionary with transport metadata

        Example:
            {
                "call_sid": "CA1234...",
                "stream_sid": "MZ5678...",
                "from_number": "+1234567890",
                "to_number": "+0987654321",
                "call_status": "in-progress",
                "connected": True,
                "bytes_sent": 12345,
                "bytes_received": 54321,
                "chunks_sent": 100,
                "chunks_received": 95,
            }
        """
        if not self.current_call_sid or self.current_call_sid not in self.active_streams:
            return {
                "connected": False,
                "error": "No active stream",
            }

        stream_metadata = self.active_streams[self.current_call_sid].copy()
        stream_metadata.update({
            "bytes_sent": self.stats["bytes_sent"],
            "bytes_received": self.stats["bytes_received"],
            "chunks_sent": self.stats["chunks_sent"],
            "chunks_received": self.stats["chunks_received"],
            "transcode_errors": self.stats["transcode_errors"],
            "marks_sent": self.stats["marks_sent"],
        })

        # Convert datetime to ISO format for JSON serialization
        if "start_time" in stream_metadata and isinstance(stream_metadata["start_time"], datetime):
            stream_metadata["start_time"] = stream_metadata["start_time"].isoformat()
        if "end_time" in stream_metadata and isinstance(stream_metadata["end_time"], datetime):
            stream_metadata["end_time"] = stream_metadata["end_time"].isoformat()

        return stream_metadata

    def is_connected(self) -> bool:
        """Check if transport is currently connected.

        Returns:
            True if connected to a Twilio Media Stream
        """
        return self.connected

    # Private transcoding methods

    def _transcode_mulaw_to_pcm(self, mulaw_data: bytes) -> bytes:
        """Transcode μ-law audio to PCM s16le.

        Converts Twilio's μ-law audio (8kHz, mono) to PCM s16le format.
        If internal sample rate is higher (16kHz), upsampling is performed.

        Args:
            mulaw_data: μ-law encoded audio data

        Returns:
            PCM s16le audio data (16kHz, mono)

        Raises:
            ValueError: If mulaw_data is empty or invalid
        """
        if not mulaw_data:
            raise ValueError("mulaw_data cannot be empty")

        try:
            # Convert bytes to numpy array
            mulaw_array = np.frombuffer(mulaw_data, dtype=np.uint8)

            # Decode μ-law to PCM s16 using lookup table
            pcm_8khz = _MULAW_DECODE_TABLE[mulaw_array]

            # Upsample from 8kHz to 16kHz if needed (simple linear interpolation)
            if self.INTERNAL_SAMPLE_RATE != self.TWILIO_SAMPLE_RATE:
                # Linear interpolation for 2x upsampling
                pcm_16khz = np.repeat(pcm_8khz, 2)
                return pcm_16khz.tobytes()

            return pcm_8khz.tobytes()

        except Exception as e:
            raise ValueError(f"Invalid μ-law data: {e}")

    def _transcode_pcm_to_mulaw(self, pcm_data: bytes) -> bytes:
        """Transcode PCM s16le audio to μ-law.

        Converts internal PCM s16le audio (16kHz, mono) to μ-law format
        for Twilio Media Streams. If sample rate is higher than 8kHz,
        downsampling is performed.

        Args:
            pcm_data: PCM s16le audio data (16kHz, mono)

        Returns:
            μ-law encoded audio data (8kHz, mono)

        Raises:
            ValueError: If pcm_data is empty or invalid
        """
        if not pcm_data:
            raise ValueError("pcm_data cannot be empty")

        try:
            # Convert bytes to numpy array
            pcm_array = np.frombuffer(pcm_data, dtype=np.int16)

            # Downsample from 16kHz to 8kHz if needed (simple decimation)
            if self.INTERNAL_SAMPLE_RATE != self.TWILIO_SAMPLE_RATE:
                # Take every other sample for 2x downsampling
                pcm_8khz = pcm_array[::2]
            else:
                pcm_8khz = pcm_array

            # Convert to unsigned 16-bit for lookup table
            # Add 32768 to convert from signed to unsigned range
            pcm_unsigned = (pcm_8khz.astype(np.int32) + 32768).astype(np.uint16)

            # Encode PCM to μ-law using lookup table
            mulaw_array = _MULAW_ENCODE_TABLE[pcm_unsigned]

            return mulaw_array.tobytes()

        except Exception as e:
            raise ValueError(f"Invalid PCM data: {e}")

    # Twilio event handling methods

    def handle_twilio_event(self, event: Dict[str, Any]) -> None:
        """Handle Twilio Media Streams event.

        Processes Twilio-specific events such as start, media, stop, mark.
        This is a utility method for integration with WebSocket handlers.

        Args:
            event: Twilio event dictionary

        Supported events:
            - start: Stream started
            - media: Audio payload (base64-encoded μ-law)
            - stop: Stream stopped
            - mark: Mark event

        Example:
            >>> event = {
            ...     "event": "start",
            ...     "start": {
            ...         "callSid": "CA1234...",
            ...         "streamSid": "MZ5678...",
            ...     }
            ... }
            >>> provider.handle_twilio_event(event)
        """
        event_type = event.get("event")

        if event_type == "start":
            # Stream start event
            start_data = event.get("start", {})
            logger.info(
                f"Twilio stream started: call_sid={start_data.get('callSid')}, "
                f"stream_sid={start_data.get('streamSid')}"
            )

        elif event_type == "media":
            # Audio payload event
            media_data = event.get("media", {})
            payload = media_data.get("payload")
            if payload:
                logger.debug(f"Received Twilio media payload: {len(payload)} chars (base64)")

        elif event_type == "stop":
            # Stream stop event
            stop_data = event.get("stop", {})
            logger.info(
                f"Twilio stream stopped: call_sid={stop_data.get('callSid')}, "
                f"stream_sid={stop_data.get('streamSid')}"
            )

        elif event_type == "mark":
            # Mark event (synchronization point)
            mark_data = event.get("mark", {})
            logger.debug(f"Received Twilio mark: {mark_data.get('name')}")

        else:
            logger.warning(f"Unknown Twilio event type: {event_type}")
