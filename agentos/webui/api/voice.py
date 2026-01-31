"""Voice REST + WebSocket API - Voice conversation endpoints.

This module provides REST and WebSocket API endpoints for voice-based interactions:
- Session management (create, query, stop)
- WebSocket audio streaming
- Speech-to-Text (STT) integration
- Text-to-Speech (TTS) integration with streaming
- Barge-In detection and handling

Implementation:
- Local STT using Whisper (or mock)
- TTS using OpenAI or Mock provider
- Barge-in detection during TTS playback
- WebSocket-based audio streaming

Part of VoiceOS implementation
"""

import logging
import uuid
import base64
import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel, Field

from agentos.core.time import utc_now
from agentos.webui.api.contracts import (
    success,
    error,
    not_found_error,
    validation_error,
    ReasonCode,
)
from agentos.webui.api.time_format import iso_z
from agentos.core.communication.voice.environment_check import check_voice_environment
from agentos.core.communication.voice.tts.base import ITTSProvider
from agentos.core.communication.voice.tts.openai_provider import OpenAITTSProvider
from agentos.core.communication.voice.tts.mock_provider import MockTTSProvider
from agentos.core.communication.voice.barge_in import (
    BargeInDetector,
    BargeInHandler,
    BargeInConfig,
    create_default_barge_in_config,
)
from agentos.core.audit import log_audit_event

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================
# Voice Session Limits (Resource Protection)
# ============================================

# Maximum audio buffer size per session (10 MB)
MAX_AUDIO_BUFFER_BYTES = 10 * 1024 * 1024

# Session idle timeout in seconds (60 seconds)
SESSION_IDLE_TIMEOUT_SECONDS = 60

# ============================================
# Voice Session State
# ============================================


class SessionState(str, Enum):
    """Voice session state enumeration"""
    ACTIVE = "ACTIVE"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class AudioFormat(BaseModel):
    """Audio format specification"""
    codec: str = Field(default="pcm_s16le", description="Audio codec (e.g., pcm_s16le, opus)")
    sample_rate: int = Field(default=16000, description="Sample rate in Hz")
    channels: int = Field(default=1, description="Number of audio channels (1=mono, 2=stereo)")


class VoiceSession:
    """Voice session data model"""

    def __init__(
        self,
        session_id: str,
        project_id: Optional[str],
        provider: str,
        stt_provider: str,
    ):
        self.session_id = session_id
        self.project_id = project_id
        self.provider = provider
        self.stt_provider = stt_provider
        self.state = SessionState.ACTIVE
        self.created_at = utc_now()
        self.last_activity_at = utc_now()
        self.stopped_at: Optional[datetime] = None
        self.websocket: Optional[WebSocket] = None
        self.audio_buffer: List[bytes] = []
        self.total_bytes_received: int = 0

    def to_dict(self, include_ws_url: bool = False) -> Dict[str, Any]:
        """Convert session to dictionary representation"""
        data = {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "provider": self.provider,
            "stt_provider": self.stt_provider,
            "state": self.state.value,
            "created_at": iso_z(self.created_at),
        }

        if self.stopped_at:
            data["stopped_at"] = iso_z(self.stopped_at)

        if include_ws_url:
            # Use relative URL (frontend will construct full URL)
            data["ws_url"] = f"/api/voice/sessions/{self.session_id}/events"

        return data


# ============================================
# In-Memory Session Store (MVP)
# ============================================

_sessions: Dict[str, VoiceSession] = {}


def get_session(session_id: str) -> Optional[VoiceSession]:
    """Get voice session by ID"""
    return _sessions.get(session_id)


def create_session(
    project_id: Optional[str],
    provider: str,
    stt_provider: str,
) -> VoiceSession:
    """Create new voice session"""
    session_id = f"voice-{uuid.uuid4().hex[:12]}"
    session = VoiceSession(
        session_id=session_id,
        project_id=project_id,
        provider=provider,
        stt_provider=stt_provider,
    )
    _sessions[session_id] = session
    logger.info(f"Created voice session: {session_id} (project: {project_id}, STT: {stt_provider})")
    return session


def stop_session(session_id: str) -> Optional[VoiceSession]:
    """Stop voice session"""
    session = _sessions.get(session_id)
    if session:
        session.state = SessionState.STOPPED
        session.stopped_at = utc_now()
        if session.websocket:
            # WebSocket will be closed by the endpoint
            session.websocket = None
        logger.info(f"Stopped voice session: {session_id}")
    return session


def list_sessions() -> List[VoiceSession]:
    """List all voice sessions"""
    return list(_sessions.values())


# ============================================
# Request/Response Models
# ============================================


class CreateSessionRequest(BaseModel):
    """Request model for creating voice session"""
    project_id: Optional[str] = Field(None, description="Project ID for context")
    provider: str = Field(default="local", description="Voice provider (local, openai, etc.)")
    stt_provider: str = Field(default="whisper_local", description="STT provider (whisper_local, openai, etc.)")


class SessionResponse(BaseModel):
    """Response model for session information"""
    session_id: str
    project_id: Optional[str] = None
    provider: str
    stt_provider: str
    state: str
    created_at: str
    stopped_at: Optional[str] = None
    ws_url: Optional[str] = None


class AudioChunkEvent(BaseModel):
    """WebSocket event: Audio chunk from client"""
    type: str = Field(default="voice.audio.chunk")
    session_id: str
    seq: int = Field(description="Sequence number for ordering")
    format: AudioFormat
    payload_b64: str = Field(description="Base64-encoded audio data")
    t_ms: int = Field(description="Client timestamp in milliseconds")


class AudioEndEvent(BaseModel):
    """WebSocket event: Audio stream ended"""
    type: str = Field(default="voice.audio.end")
    session_id: str
    t_ms: int = Field(description="Client timestamp in milliseconds")


# ============================================
# STT Service (MVP Mock)
# ============================================


class STTService:
    """Speech-to-Text service (MVP implementation)

    MVP: Returns mock transcription for testing.
    TODO: Integrate with real Whisper model or OpenAI API.
    """

    def __init__(self):
        self.enabled = True

    async def transcribe(self, audio_data: bytes, format: AudioFormat) -> str:
        """Transcribe audio to text

        Args:
            audio_data: Raw audio bytes
            format: Audio format specification

        Returns:
            Transcribed text
        """
        # MVP: Return mock transcription
        # TODO: Integrate with Whisper or OpenAI Whisper API
        duration_estimate = len(audio_data) / (format.sample_rate * format.channels * 2)  # 16-bit PCM
        logger.info(
            f"[MVP STT] Transcribing {len(audio_data)} bytes "
            f"({duration_estimate:.2f}s, {format.codec}, {format.sample_rate}Hz)"
        )

        # Simulate processing delay
        await asyncio.sleep(0.1)

        # Return mock transcription
        return f"[Mock transcription of {duration_estimate:.1f}s audio]"

    async def transcribe_partial(self, audio_data: bytes, format: AudioFormat) -> str:
        """Get partial transcription (for real-time feedback)

        Args:
            audio_data: Raw audio bytes
            format: Audio format specification

        Returns:
            Partial transcription
        """
        # MVP: Return mock partial transcription
        return f"[Partial...]"


# Global STT service instance
_stt_service = STTService()


# ============================================
# TTS Service (v0.2)
# ============================================


def get_tts_provider() -> ITTSProvider:
    """Get TTS provider based on environment configuration.

    Returns:
        TTS provider instance (OpenAI or Mock)
    """
    # Check if OpenAI API key is available
    openai_api_key = os.environ.get("OPENAI_API_KEY")

    if openai_api_key:
        logger.info("Using OpenAI TTS provider")
        return OpenAITTSProvider(api_key=openai_api_key, model="tts-1")
    else:
        logger.info("Using Mock TTS provider (no OPENAI_API_KEY found)")
        return MockTTSProvider(generate_tone=False)


# ============================================
# Chat Engine Integration (Simplified v0.2)
# ============================================


async def get_assistant_response(transcript: str, session_id: str) -> str:
    """Get assistant response from chat engine.

    Simplified implementation for v0.2 - returns echo response.
    TODO: Integrate with real chat engine in future versions.

    Args:
        transcript: User's transcribed speech
        session_id: Voice session ID

    Returns:
        Assistant's text response
    """
    # MVP: Simple echo response
    # In production, this would call the actual chat engine:
    # - Load session context
    # - Call LLM with conversation history
    # - Apply guardrails and policies
    # - Return assistant response

    logger.info(f"[Chat Engine] Processing transcript (session={session_id}, length={len(transcript)})")

    # Echo response for MVP
    response = f"You said: {transcript}"

    logger.info(f"[Chat Engine] Generated response: {response}")
    return response


# ============================================
# REST Endpoints
# ============================================


@router.post("/api/voice/sessions", tags=["voice"])
async def create_voice_session(request: CreateSessionRequest) -> Dict[str, Any]:
    """Create a new voice session.

    Args:
        request: Session creation parameters

    Returns:
        Session information including WebSocket URL

    Example request:
    ```json
    {
      "project_id": "proj-abc123",
      "provider": "local",
      "stt_provider": "whisper_local"
    }
    ```

    Example response:
    ```json
    {
      "ok": true,
      "data": {
        "session_id": "voice-a1b2c3d4e5f6",
        "project_id": "proj-abc123",
        "provider": "local",
        "stt_provider": "whisper_local",
        "state": "ACTIVE",
        "created_at": "2026-02-01T12:34:56.789012Z",
        "ws_url": "/api/voice/sessions/voice-a1b2c3d4e5f6/events"
      }
    }
    ```
    """
    try:
        # Environment check (only for local providers that need Whisper)
        if request.stt_provider == "whisper_local":
            is_ready, reason_code, message = check_voice_environment()
            if not is_ready:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "ok": False,
                        "reason_code": reason_code,
                        "message": message,
                        "hint": "Voice capability is not available in this environment. See docs/voice/MVP.md",
                    }
                )

        # Validate provider
        if request.provider not in ["local", "openai", "azure"]:
            raise validation_error(
                f"Invalid provider: {request.provider}",
                hint="Valid providers: local, openai, azure"
            )

        # Validate STT provider
        if request.stt_provider not in ["whisper_local", "openai", "azure", "mock"]:
            raise validation_error(
                f"Invalid STT provider: {request.stt_provider}",
                hint="Valid STT providers: whisper_local, openai, azure, mock"
            )

        # Create session
        session = create_session(
            project_id=request.project_id,
            provider=request.provider,
            stt_provider=request.stt_provider,
        )

        return success(session.to_dict(include_ws_url=True))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create voice session: {str(e)}", exc_info=True)
        raise error(
            "Failed to create voice session",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.get("/api/voice/sessions/{session_id}", tags=["voice"])
async def get_voice_session(session_id: str) -> Dict[str, Any]:
    """Get voice session information.

    Args:
        session_id: Voice session ID

    Returns:
        Session information

    Example response:
    ```json
    {
      "ok": true,
      "data": {
        "session_id": "voice-a1b2c3d4e5f6",
        "project_id": "proj-abc123",
        "provider": "local",
        "stt_provider": "whisper_local",
        "state": "ACTIVE",
        "created_at": "2026-02-01T12:34:56.789012Z"
      }
    }
    ```
    """
    try:
        session = get_session(session_id)

        if not session:
            raise not_found_error("Voice session", session_id)

        return success(session.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get voice session {session_id}: {str(e)}", exc_info=True)
        raise error(
            f"Failed to retrieve voice session {session_id}",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.post("/api/voice/sessions/{session_id}/stop", tags=["voice"])
async def stop_voice_session(session_id: str) -> Dict[str, Any]:
    """Stop a voice session.

    Args:
        session_id: Voice session ID

    Returns:
        Updated session information

    Example response:
    ```json
    {
      "ok": true,
      "data": {
        "session_id": "voice-a1b2c3d4e5f6",
        "state": "STOPPED",
        "stopped_at": "2026-02-01T12:35:00.123456Z"
      }
    }
    ```
    """
    try:
        session = get_session(session_id)

        if not session:
            raise not_found_error("Voice session", session_id)

        if session.state == SessionState.STOPPED:
            raise error(
                "Session already stopped",
                reason_code=ReasonCode.BAD_STATE,
                hint="Session is already in STOPPED state",
                http_status=409
            )

        # Stop session
        stop_session(session_id)

        return success(session.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop voice session {session_id}: {str(e)}", exc_info=True)
        raise error(
            f"Failed to stop voice session {session_id}",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


@router.get("/api/voice/sessions", tags=["voice"])
async def list_voice_sessions(
    state: Optional[str] = Query(None, description="Filter by state (ACTIVE, STOPPED)"),
    limit: int = Query(100, description="Maximum number of results", ge=1, le=1000),
) -> Dict[str, Any]:
    """List all voice sessions (for debugging).

    Args:
        state: Filter by session state
        limit: Maximum number of results

    Returns:
        List of voice sessions

    Example response:
    ```json
    {
      "ok": true,
      "data": {
        "sessions": [...],
        "total": 5,
        "filters_applied": {
          "state": "ACTIVE",
          "limit": 100
        }
      }
    }
    ```
    """
    try:
        # Get all sessions
        all_sessions = list_sessions()

        # Filter by state if specified
        if state:
            try:
                state_enum = SessionState(state.upper())
                filtered_sessions = [s for s in all_sessions if s.state == state_enum]
            except ValueError:
                raise validation_error(
                    f"Invalid state: {state}",
                    hint=f"Valid states: {', '.join([s.value for s in SessionState])}"
                )
        else:
            filtered_sessions = all_sessions

        # Apply limit
        sessions = filtered_sessions[:limit]

        # Convert to response format
        sessions_data = [s.to_dict() for s in sessions]

        return success({
            "sessions": sessions_data,
            "total": len(sessions),
            "filters_applied": {
                "state": state,
                "limit": limit,
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list voice sessions: {str(e)}", exc_info=True)
        raise error(
            "Failed to list voice sessions",
            reason_code=ReasonCode.INTERNAL_ERROR,
            hint="Check server logs for details",
            http_status=500
        )


# ============================================
# WebSocket Endpoint
# ============================================


@router.websocket("/api/voice/sessions/{session_id}/events")
async def voice_session_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for voice session events.

    Protocol (v0.2):
    1. Client connects
    2. Server sends: {"type": "voice.session.ready", "session_id": "..."}
    3. Client sends audio chunks: {"type": "voice.audio.chunk", ...}
    4. Server sends STT results: {"type": "voice.stt.final", "text": "..."}
    5. Server sends assistant response: {"type": "assistant.text", "text": "..."}
    6. Server streams TTS: {"type": "tts.start/chunk/end", ...}
    7. Barge-in: Server detects speech during TTS, sends control.stop_playback
    8. Client sends end signal: {"type": "voice.audio.end"}

    Client Events:
    - voice.audio.chunk: Audio data chunk
    - voice.audio.end: End of audio stream

    Server Events:
    - voice.session.ready: Session ready for audio
    - voice.stt.partial: Partial transcription
    - voice.stt.final: Final transcription
    - assistant.text: Assistant text response
    - tts.start: TTS synthesis started
    - tts.chunk: TTS audio chunk (base64)
    - tts.end: TTS synthesis completed
    - barge_in.detected: User speech detected during TTS
    - control.stop_playback: Stop audio playback (barge-in)
    - voice.error: Error message
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for session: {session_id}")

    # Initialize TTS provider and Barge-In components
    tts_provider = get_tts_provider()
    barge_in_config = create_default_barge_in_config()
    barge_in_detector = BargeInDetector(barge_in_config)
    barge_in_handler = BargeInHandler()
    current_tts_request_id: Optional[str] = None
    tts_task: Optional[asyncio.Task] = None

    try:
        # Validate session
        session = get_session(session_id)
        if not session:
            await websocket.send_json({
                "type": "voice.error",
                "error": "Session not found",
                "session_id": session_id,
            })
            await websocket.close()
            return

        if session.state != SessionState.ACTIVE:
            await websocket.send_json({
                "type": "voice.error",
                "error": f"Session not active (state: {session.state.value})",
                "session_id": session_id,
            })
            await websocket.close()
            return

        # Attach WebSocket to session
        session.websocket = websocket

        # Send ready event
        await websocket.send_json({
            "type": "voice.session.ready",
            "session_id": session_id,
            "timestamp": iso_z(utc_now()),
        })
        logger.info(f"Sent voice.session.ready for session: {session_id}")

        # Resource protection: Start idle timeout monitor
        async def check_idle_timeout():
            """Background task to check for session idle timeout."""
            while session.state == SessionState.ACTIVE:
                await asyncio.sleep(10)  # Check every 10 seconds

                if session.state != SessionState.ACTIVE:
                    break

                idle_seconds = (utc_now() - session.last_activity_at).total_seconds()
                if idle_seconds > SESSION_IDLE_TIMEOUT_SECONDS:
                    logger.warning(
                        f"Session {session_id} idle timeout "
                        f"({idle_seconds:.1f}s > {SESSION_IDLE_TIMEOUT_SECONDS}s)"
                    )
                    try:
                        await websocket.send_json({
                            "type": "voice.error",
                            "error": f"Session idle timeout ({SESSION_IDLE_TIMEOUT_SECONDS}s)",
                            "reason_code": "IDLE_TIMEOUT",
                            "timestamp": iso_z(utc_now()),
                        })
                    except:
                        pass  # WebSocket may already be closed

                    session.state = SessionState.ERROR
                    session.stopped_at = utc_now()
                    logger.info(f"Session {session_id} stopped due to idle timeout")
                    break

        # Start idle timeout monitor in background
        timeout_task = asyncio.create_task(check_idle_timeout())

        # Process incoming events
        accumulated_audio = bytearray()
        audio_format = None

        while True:
            # Receive event from client
            data = await websocket.receive_json()
            event_type = data.get("type")

            if event_type == "voice.audio.chunk":
                # Process audio chunk
                try:
                    seq = data.get("seq", 0)
                    format_data = data.get("format", {})
                    payload_b64 = data.get("payload_b64", "")

                    # Decode audio data
                    audio_data = base64.b64decode(payload_b64)

                    # Resource protection: Check buffer size limit
                    if len(accumulated_audio) + len(audio_data) > MAX_AUDIO_BUFFER_BYTES:
                        logger.warning(
                            f"Session {session_id} exceeded buffer limit "
                            f"({len(accumulated_audio) + len(audio_data)} > {MAX_AUDIO_BUFFER_BYTES})"
                        )
                        await websocket.send_json({
                            "type": "voice.error",
                            "error": f"Audio buffer limit exceeded ({MAX_AUDIO_BUFFER_BYTES} bytes)",
                            "reason_code": "BUFFER_LIMIT_EXCEEDED",
                            "timestamp": iso_z(utc_now()),
                        })
                        # Stop session and close connection
                        session.state = SessionState.ERROR
                        session.stopped_at = utc_now()
                        logger.info(f"Session {session_id} stopped due to buffer limit")
                        break

                    # Store format
                    if not audio_format:
                        audio_format = AudioFormat(**format_data)
                        logger.info(
                            f"Audio format: {audio_format.codec}, "
                            f"{audio_format.sample_rate}Hz, "
                            f"{audio_format.channels}ch"
                        )

                    # Accumulate audio
                    accumulated_audio.extend(audio_data)

                    # Update session activity tracking
                    session.last_activity_at = utc_now()
                    session.total_bytes_received += len(audio_data)

                    logger.debug(
                        f"Received audio chunk #{seq}: {len(audio_data)} bytes "
                        f"(total: {len(accumulated_audio)} bytes)"
                    )

                    # Barge-in detection (if TTS is playing)
                    if barge_in_detector.is_playing_tts:
                        try:
                            should_barge_in = barge_in_detector.detect(
                                audio_data,
                                sample_rate=audio_format.sample_rate if audio_format else 16000
                            )

                            if should_barge_in:
                                # Send barge-in detected event
                                await websocket.send_json({
                                    "type": "barge_in.detected",
                                    "timestamp": iso_z(utc_now()),
                                })

                                # Log audit event
                                log_audit_event(
                                    event_type="BARGE_IN_DETECTED",
                                    metadata={
                                        "session_id": session_id,
                                        "tts_request_id": current_tts_request_id,
                                    }
                                )

                                # Execute barge-in: cancel TTS
                                if current_tts_request_id:
                                    logger.info(f"Executing barge-in (tts_request={current_tts_request_id})")

                                    # Cancel TTS provider
                                    cancelled = await tts_provider.cancel(current_tts_request_id)
                                    if cancelled:
                                        logger.info(f"TTS cancelled: {current_tts_request_id}")

                                    # Cancel TTS streaming task
                                    if tts_task and not tts_task.done():
                                        tts_task.cancel()
                                        try:
                                            await tts_task
                                        except asyncio.CancelledError:
                                            logger.info("TTS streaming task cancelled")

                                    # Send stop playback control
                                    await websocket.send_json({
                                        "type": "control.stop_playback",
                                        "reason": "barge_in",
                                        "tts_request_id": current_tts_request_id,
                                        "timestamp": iso_z(utc_now()),
                                    })

                                    # Log audit event
                                    log_audit_event(
                                        event_type="BARGE_IN_EXECUTED",
                                        metadata={
                                            "session_id": session_id,
                                            "tts_request_id": current_tts_request_id,
                                            "barge_in_count": barge_in_handler.barge_in_count,
                                        }
                                    )

                                    barge_in_handler.barge_in_count += 1

                                    # Stop detector
                                    barge_in_detector.stop_tts_playback()
                                    current_tts_request_id = None

                        except Exception as e:
                            logger.error(f"Barge-in detection error: {e}", exc_info=True)

                    # Send partial transcription (optional)
                    # Uncomment if you want real-time partial results:
                    # if len(accumulated_audio) > 16000 * 2:  # 1 second of audio
                    #     partial_text = await _stt_service.transcribe_partial(
                    #         bytes(accumulated_audio),
                    #         audio_format
                    #     )
                    #     await websocket.send_json({
                    #         "type": "voice.stt.partial",
                    #         "text": partial_text,
                    #         "timestamp": iso_z(utc_now()),
                    #     })

                except Exception as e:
                    logger.error(f"Error processing audio chunk: {str(e)}", exc_info=True)
                    await websocket.send_json({
                        "type": "voice.error",
                        "error": f"Failed to process audio chunk: {str(e)}",
                        "timestamp": iso_z(utc_now()),
                    })

            elif event_type == "voice.audio.end":
                # Process accumulated audio
                t_end_received = utc_now()
                logger.info(
                    f"Audio stream ended, processing {len(accumulated_audio)} bytes"
                )

                if len(accumulated_audio) > 0 and audio_format:
                    try:
                        # Transcribe audio
                        t_stt_start = utc_now()
                        transcription = await _stt_service.transcribe(
                            bytes(accumulated_audio),
                            audio_format
                        )
                        t_stt_done = utc_now()
                        stt_latency_ms = int((t_stt_done - t_stt_start).total_seconds() * 1000)

                        # Send final transcription
                        await websocket.send_json({
                            "type": "voice.stt.final",
                            "text": transcription,
                            "timestamp": iso_z(utc_now()),
                        })
                        t_final_sent = utc_now()
                        logger.info(f"Sent transcription: {transcription}")

                        # Get assistant response from chat engine
                        t_chat_start = utc_now()
                        assistant_response = await get_assistant_response(transcription, session_id)
                        t_chat_done = utc_now()
                        chat_latency_ms = int((t_chat_done - t_chat_start).total_seconds() * 1000)

                        # Send assistant text response
                        await websocket.send_json({
                            "type": "assistant.text",
                            "text": assistant_response,
                            "timestamp": iso_z(utc_now()),
                        })
                        logger.info(f"Sent assistant response: {assistant_response}")

                        # Stream TTS audio
                        try:
                            tts_request_id = f"tts-{uuid.uuid4().hex[:12]}"
                            current_tts_request_id = tts_request_id
                            voice_id = "alloy"  # Default voice (could be from session config)
                            speed = 1.0

                            # Send TTS start event
                            await websocket.send_json({
                                "type": "tts.start",
                                "request_id": tts_request_id,
                                "voice_id": voice_id,
                                "speed": speed,
                                "timestamp": iso_z(utc_now()),
                            })

                            # Log audit event
                            log_audit_event(
                                event_type="TTS_START",
                                metadata={
                                    "session_id": session_id,
                                    "tts_request_id": tts_request_id,
                                    "voice_id": voice_id,
                                    "speed": speed,
                                    "text_length": len(assistant_response),
                                }
                            )

                            logger.info(f"Starting TTS synthesis (request={tts_request_id}, voice={voice_id})")

                            # Start barge-in detector
                            barge_in_detector.start_tts_playback()

                            # Stream TTS chunks
                            t_tts_start = utc_now()
                            chunk_count = 0

                            async def stream_tts():
                                """Background task to stream TTS chunks."""
                                nonlocal chunk_count
                                try:
                                    async for audio_chunk in tts_provider.synthesize(
                                        text=assistant_response,
                                        voice_id=voice_id,
                                        speed=speed,
                                    ):
                                        # Encode to base64
                                        payload_b64 = base64.b64encode(audio_chunk).decode("utf-8")

                                        # Send TTS chunk event
                                        await websocket.send_json({
                                            "type": "tts.chunk",
                                            "request_id": tts_request_id,
                                            "payload_b64": payload_b64,
                                            "format": {
                                                "codec": "pcm_s16le",  # ITTSProvider contract: PCM s16le
                                                "sample_rate": 16000,
                                                "channels": 1,
                                            },
                                            "timestamp": iso_z(utc_now()),
                                        })

                                        chunk_count += 1
                                        logger.debug(f"Sent TTS chunk #{chunk_count} ({len(audio_chunk)} bytes)")

                                except asyncio.CancelledError:
                                    logger.info(f"TTS streaming cancelled (request={tts_request_id})")
                                    raise
                                except Exception as e:
                                    logger.error(f"TTS streaming error: {e}", exc_info=True)
                                    await websocket.send_json({
                                        "type": "voice.error",
                                        "error": f"TTS streaming failed: {str(e)}",
                                        "timestamp": iso_z(utc_now()),
                                    })

                            # Start TTS streaming in background
                            tts_task = asyncio.create_task(stream_tts())

                            # Wait for TTS to complete
                            try:
                                await tts_task
                            except asyncio.CancelledError:
                                logger.info(f"TTS task was cancelled (barge-in)")
                            finally:
                                # Stop barge-in detector
                                barge_in_detector.stop_tts_playback()

                                t_tts_done = utc_now()
                                tts_duration_ms = int((t_tts_done - t_tts_start).total_seconds() * 1000)

                                # Send TTS end event (if not cancelled)
                                if not tts_task.cancelled():
                                    await websocket.send_json({
                                        "type": "tts.end",
                                        "request_id": tts_request_id,
                                        "total_chunks": chunk_count,
                                        "duration_ms": tts_duration_ms,
                                        "timestamp": iso_z(utc_now()),
                                    })

                                    # Log audit event
                                    log_audit_event(
                                        event_type="TTS_END",
                                        metadata={
                                            "session_id": session_id,
                                            "tts_request_id": tts_request_id,
                                            "duration_ms": tts_duration_ms,
                                            "chunk_count": chunk_count,
                                        }
                                    )

                                    logger.info(
                                        f"TTS synthesis completed (request={tts_request_id}, "
                                        f"chunks={chunk_count}, duration={tts_duration_ms}ms)"
                                    )

                                current_tts_request_id = None
                                tts_task = None

                        except Exception as e:
                            logger.error(f"TTS synthesis error: {e}", exc_info=True)
                            await websocket.send_json({
                                "type": "voice.error",
                                "error": f"TTS synthesis failed: {str(e)}",
                                "timestamp": iso_z(utc_now()),
                            })
                            barge_in_detector.stop_tts_playback()

                        # Performance metric log (grepable)
                        e2e_latency_ms = int((utc_now() - t_end_received).total_seconds() * 1000)
                        logger.info(
                            f"VOICE_METRIC session_id={session_id} "
                            f"bytes={len(accumulated_audio)} "
                            f"stt_ms={stt_latency_ms} "
                            f"chat_ms={chat_latency_ms} "
                            f"e2e_ms={e2e_latency_ms} "
                            f"provider=local "
                            f"stt_provider=whisper_local"
                        )

                    except Exception as e:
                        logger.error(f"Error processing audio: {str(e)}", exc_info=True)
                        await websocket.send_json({
                            "type": "voice.error",
                            "error": f"Failed to process audio: {str(e)}",
                            "timestamp": iso_z(utc_now()),
                        })

                # Reset buffer
                accumulated_audio.clear()
                audio_format = None

            else:
                logger.warning(f"Unknown event type: {event_type}")
                await websocket.send_json({
                    "type": "voice.error",
                    "error": f"Unknown event type: {event_type}",
                    "timestamp": iso_z(utc_now()),
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {str(e)}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "voice.error",
                "error": str(e),
                "timestamp": iso_z(utc_now()),
            })
        except Exception:
            pass  # Connection already closed
    finally:
        # Cancel idle timeout monitor
        if 'timeout_task' in locals():
            timeout_task.cancel()
            try:
                await timeout_task
            except asyncio.CancelledError:
                pass

        # Cleanup
        session = get_session(session_id)
        if session:
            session.websocket = None
        logger.info(f"WebSocket closed for session: {session_id}")
