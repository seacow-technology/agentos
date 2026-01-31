"""Data models for voice communication system.

This module defines the core data structures for voice sessions and events,
supporting real-time voice interactions with external agents and users.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from agentos.core.time import utc_now


class VoiceSessionState(str, Enum):
    """State of a voice session.

    Lifecycle: CREATED -> ACTIVE -> STOPPING -> STOPPED
    """

    CREATED = "created"      # Session created but not yet active
    ACTIVE = "active"        # Session is actively processing voice data
    STOPPING = "stopping"    # Session is being gracefully stopped
    STOPPED = "stopped"      # Session has been stopped


class VoiceProvider(str, Enum):
    """Voice provider types.

    Determines the underlying transport and connectivity mechanism.
    """

    LOCAL = "local"          # Local WebSocket-based voice transport
    TWILIO = "twilio"        # Twilio voice API (PSTN/SIP)


class STTProvider(str, Enum):
    """Speech-to-text provider types.

    Determines which STT engine is used for audio transcription.
    """

    WHISPER = "whisper_local"  # OpenAI Whisper (local via faster-whisper)
    GOOGLE = "google"          # Google Cloud Speech-to-Text
    AZURE = "azure"            # Azure Speech Services
    AWS = "aws"                # Amazon Transcribe


class TTSProvider(str, Enum):
    """Text-to-speech provider types.

    Determines which TTS engine is used for audio synthesis.
    """

    OPENAI = "openai"          # OpenAI TTS (tts-1 model)
    ELEVENLABS = "elevenlabs"  # ElevenLabs TTS
    LOCAL = "local"            # Local TTS engine (e.g., piper)
    MOCK = "mock"              # Mock TTS for testing


class TransportType(str, Enum):
    """Voice transport layer types.

    Separates the physical transport mechanism from the voice processing logic.
    """

    WEBSOCKET = "websocket"            # Local WebUI WebSocket transport
    TWILIO_STREAM = "twilio_stream"    # Twilio Media Streams WebSocket
    SIDECAR_GRPC = "sidecar_grpc"      # Internal gRPC to Sidecar worker


class RuntimeMode(str, Enum):
    """Voice runtime execution mode.

    Determines whether voice processing runs in-process or in a separate sidecar.
    """

    EMBEDDED = "embedded"  # In-process (Python 3.14) - requires compatible libraries
    SIDECAR = "sidecar"    # Separate process (Python 3.13) - for Whisper compatibility


class VoiceEventType(str, Enum):
    """Types of voice events.

    Events track the lifecycle and data flow of voice sessions.
    """

    # Session lifecycle
    SESSION_STARTED = "session_started"
    SESSION_STOPPED = "session_stopped"
    ERROR = "error"

    # Audio input (STT)
    AUDIO_RECEIVED = "audio_received"
    TRANSCRIPT_READY = "transcript_ready"
    STT_PARTIAL = "stt_partial"        # Partial STT result (real-time preview)
    STT_FINAL = "stt_final"            # Final STT result (confirmed transcript)

    # Audio output (TTS) - v0.2
    ASSISTANT_TEXT = "assistant.text"  # Assistant response text (before TTS)
    TTS_START = "tts.start"            # TTS synthesis started
    TTS_CHUNK = "tts.chunk"            # TTS audio chunk ready for playback
    TTS_END = "tts.end"                # TTS synthesis completed

    # Barge-in control - v0.2
    BARGE_IN_DETECTED = "barge_in.detected"      # User speech detected during TTS
    BARGE_IN_EXECUTED = "barge_in.executed"      # TTS playback cancelled
    CONTROL_STOP_PLAYBACK = "control.stop_playback"  # Control signal to stop audio


@dataclass
class VoiceSession:
    """Represents an active voice communication session.

    Voice sessions manage real-time bidirectional audio communication
    between agents and external parties (users, other agents, PSTN callers).

    Attributes (v0.1 - Base):
        session_id: Unique session identifier
        project_id: Associated project ID for context and billing
        provider: Voice provider type (LOCAL, TWILIO)
        stt_provider: Speech-to-text provider for transcription
        state: Current session state
        created_at: Session creation timestamp (UTC)
        last_activity_at: Last activity timestamp (UTC)
        risk_tier: Risk assessment level (LOW, MEDIUM, HIGH)
        policy_verdict: Policy evaluation verdict status
        audit_trace_id: Audit trace ID for evidence chain
        metadata: Additional session metadata (caller_id, user_id, etc.)

    Attributes (v0.2 - Transport):
        transport: Transport layer type (WEBSOCKET, TWILIO_STREAM, SIDECAR_GRPC)
        transport_metadata: Transport-specific metadata (call_sid, stream_sid, etc.)

    Attributes (v0.2 - TTS):
        tts_provider: Text-to-speech provider (OPENAI, ELEVENLABS, etc.)
        tts_voice_id: Voice ID for TTS (e.g., "alloy", "echo", "fable")
        tts_speed: TTS playback speed multiplier (0.25 - 4.0)

    Attributes (v0.2 - Barge-In):
        barge_in_enabled: Whether user can interrupt TTS playback
        barge_in_config: Barge-in configuration (thresholds, detection mode)

    Attributes (v0.2 - Runtime):
        runtime_mode: Execution mode (EMBEDDED, SIDECAR)
        sidecar_worker_id: Worker ID if using SIDECAR mode
    """

    # v0.1 - Base fields
    session_id: str
    project_id: str
    provider: VoiceProvider
    stt_provider: STTProvider
    state: VoiceSessionState = VoiceSessionState.CREATED
    created_at: datetime = field(default_factory=utc_now)
    last_activity_at: datetime = field(default_factory=utc_now)
    risk_tier: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    policy_verdict: str = "APPROVED"
    audit_trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # v0.2 - Transport fields
    transport: TransportType = TransportType.WEBSOCKET
    transport_metadata: Dict[str, Any] = field(default_factory=dict)

    # v0.2 - TTS fields
    tts_provider: Optional[TTSProvider] = None
    tts_voice_id: Optional[str] = None
    tts_speed: float = 1.0

    # v0.2 - Barge-in fields
    barge_in_enabled: bool = False
    barge_in_config: Dict[str, Any] = field(default_factory=dict)

    # v0.2 - Runtime fields
    runtime_mode: RuntimeMode = RuntimeMode.EMBEDDED
    sidecar_worker_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary representation.

        Returns:
            Dictionary with all session fields (v0.1 + v0.2)
        """
        return {
            # v0.1 fields
            "session_id": self.session_id,
            "project_id": self.project_id,
            "provider": self.provider.value,
            "stt_provider": self.stt_provider.value,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "last_activity_at": self.last_activity_at.isoformat(),
            "risk_tier": self.risk_tier,
            "policy_verdict": self.policy_verdict,
            "audit_trace_id": self.audit_trace_id,
            "metadata": self.metadata,
            # v0.2 fields
            "transport": self.transport.value,
            "transport_metadata": self.transport_metadata,
            "tts_provider": self.tts_provider.value if self.tts_provider else None,
            "tts_voice_id": self.tts_voice_id,
            "tts_speed": self.tts_speed,
            "barge_in_enabled": self.barge_in_enabled,
            "barge_in_config": self.barge_in_config,
            "runtime_mode": self.runtime_mode.value,
            "sidecar_worker_id": self.sidecar_worker_id,
        }


@dataclass
class VoiceEvent:
    """Represents a voice event within a session.

    Voice events track significant occurrences during a voice session,
    including audio data reception, transcription results, and errors.

    Attributes:
        event_id: Unique event identifier
        session_id: Associated session ID
        event_type: Type of event
        payload: Event-specific data payload
        timestamp_ms: Event timestamp in epoch milliseconds
        metadata: Additional event metadata
    """

    event_id: str
    session_id: str
    event_type: VoiceEventType
    payload: Dict[str, Any]
    timestamp_ms: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary representation.

        Returns:
            Dictionary with all event fields
        """
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "event_type": self.event_type.value,
            "payload": self.payload,
            "timestamp_ms": self.timestamp_ms,
            "metadata": self.metadata,
        }
