"""Twilio Voice Integration API - Inbound Call Webhook and Media Streams WebSocket.

This module provides Twilio-specific voice integration endpoints:
- POST /api/voice/twilio/inbound - Inbound call webhook (returns TwiML)
- WebSocket /api/voice/twilio/stream/{session_id} - Media Streams audio transport

Part of VoiceOS Task #13 implementation.

References:
- Twilio Media Streams: https://www.twilio.com/docs/voice/media-streams
- TwiML: https://www.twilio.com/docs/voice/twiml
"""

import logging
import uuid
import base64
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import Response

from agentos.core.time import utc_now
from agentos.core.communication.voice.models import (
    VoiceSession,
    VoiceProvider,
    STTProvider,
    TransportType,
    VoiceSessionState,
)
from agentos.core.communication.voice.stt.whisper_local import WhisperLocalSTT
from agentos.webui.api.contracts import success, error, ReasonCode
from agentos.webui.api.time_format import iso_z

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================
# Session Management
# ============================================

# In-memory session store (MVP implementation)
# Production: Should use Redis or database with TTL
_twilio_sessions: Dict[str, VoiceSession] = {}


def get_twilio_session(session_id: str) -> Optional[VoiceSession]:
    """Get Twilio voice session by ID."""
    return _twilio_sessions.get(session_id)


def create_twilio_session(
    call_sid: str,
    from_number: str,
    to_number: str,
    project_id: str = "default",
) -> VoiceSession:
    """Create new Twilio voice session.

    Args:
        call_sid: Twilio call SID
        from_number: Caller phone number
        to_number: Recipient phone number
        project_id: Project ID for context and billing

    Returns:
        Created VoiceSession object
    """
    session_id = f"twilio-{call_sid}"

    session = VoiceSession(
        session_id=session_id,
        project_id=project_id,
        provider=VoiceProvider.TWILIO,
        stt_provider=STTProvider.WHISPER,
        state=VoiceSessionState.CREATED,
        transport=TransportType.TWILIO_STREAM,
        transport_metadata={
            "call_sid": call_sid,
            "from_number": from_number,
            "to_number": to_number,
        },
    )

    _twilio_sessions[session_id] = session

    logger.info(
        f"Created Twilio voice session: {session_id} "
        f"(call_sid={call_sid}, from={from_number}, to={to_number})"
    )

    # Audit log (via logging for MVP)
    # TODO: Add proper audit event type to agentos.core.events.types for voice events
    logger.info(
        f"AUDIT: voice.twilio.session.created "
        f"session_id={session_id} call_sid={call_sid} "
        f"from={from_number} to={to_number} project={project_id}"
    )

    return session


# ============================================
# Audio Transcoding
# ============================================


def transcode_mulaw_to_pcm(mulaw_bytes: bytes) -> bytes:
    """Transcode μ-law audio to PCM 16-bit (linear).

    Twilio Media Streams sends audio in μ-law (G.711) format.
    Whisper expects PCM 16-bit linear audio.

    Args:
        mulaw_bytes: Raw μ-law audio bytes

    Returns:
        PCM 16-bit audio bytes

    Reference:
        - G.711 μ-law: https://en.wikipedia.org/wiki/G.711
        - ITU-T Recommendation G.711

    Note:
        Python 3.13 removed audioop module. This implementation uses
        numpy for μ-law to linear PCM conversion.
    """
    import numpy as np

    # μ-law decompression table (ITU-T G.711)
    # Formula: sign * (2^(magnitude + 1) - 1 + bias) * step
    # Where bias = 33 (offset for μ-law encoding)

    # Convert bytes to numpy array
    mulaw_array = np.frombuffer(mulaw_bytes, dtype=np.uint8)

    # μ-law decompression
    # Extract sign bit (bit 7)
    sign = (mulaw_array & 0x80) >> 7

    # Extract magnitude (bits 4-6) and mantissa (bits 0-3)
    magnitude = (mulaw_array & 0x70) >> 4
    mantissa = mulaw_array & 0x0F

    # Decode μ-law: linear = (mantissa * 2 + 33) * 2^magnitude - 33
    linear = ((mantissa * 2 + 33) * (2 ** magnitude) - 33).astype(np.int16)

    # Apply sign (invert if sign bit is 0)
    linear = np.where(sign == 0, -linear, linear)

    # Scale to 16-bit range (μ-law uses 14-bit internal representation)
    # Scale factor: 32768 / 8159 ≈ 4.015
    linear = (linear * 4).astype(np.int16)

    # Convert to bytes
    pcm_bytes = linear.tobytes()

    return pcm_bytes


# ============================================
# Assistant Response (MVP Placeholder)
# ============================================


async def get_assistant_response(transcript: str, session_id: str) -> str:
    """Get assistant response for transcribed text.

    MVP Implementation: Simple echo response.
    Production: Integrate with ChatService/LLM engine.

    Args:
        transcript: Transcribed user speech
        session_id: Voice session ID

    Returns:
        Assistant response text

    TODO:
        - Integrate with agentos.core.chat.service.ChatService
        - Pass session context and project_id
        - Handle streaming responses
        - Implement conversation memory
    """
    # MVP: Echo response
    logger.info(f"[MVP] Assistant responding to: '{transcript}' (session: {session_id})")

    # Simulate processing delay
    await asyncio.sleep(0.1)

    return f"You said: {transcript}"


async def send_twilio_say(
    websocket: WebSocket,
    text: str,
    session: VoiceSession,
) -> None:
    """Send text response as TTS audio via Twilio <Say>.

    MVP Implementation: Send text back to client for TTS.
    Production: Use Twilio <Say> via REST API or stream TTS audio.

    Args:
        websocket: WebSocket connection to Twilio Media Streams
        text: Text to speak
        session: Voice session

    TODO:
        - Use Twilio REST API to update call with <Say> TwiML
        - Or implement real-time TTS streaming via Media Streams
        - Support voice customization (voice_id, language, speed)
    """
    # MVP: Send as text event (client can handle TTS)
    await websocket.send_json({
        "type": "voice.assistant.text",
        "text": text,
        "session_id": session.session_id,
        "timestamp": iso_z(utc_now()),
    })

    logger.info(f"Sent assistant text to Twilio session: {session.session_id}")


# ============================================
# REST Endpoint: Inbound Call Webhook
# ============================================


@router.post("/api/voice/twilio/inbound", tags=["voice", "twilio"])
async def twilio_inbound_call(request: Request):
    """Handle inbound Twilio voice call.

    This endpoint is called by Twilio when an inbound call arrives.
    It returns TwiML instructions to establish a Media Stream connection.

    Twilio Request Parameters (form-encoded):
        - CallSid: Unique call identifier
        - From: Caller phone number (E.164 format)
        - To: Recipient phone number (E.164 format)
        - CallStatus: Call status (ringing, in-progress, etc.)

    Returns:
        TwiML XML response with <Stream> instruction

    Example TwiML Response:
        ```xml
        <?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say>Connecting to agent.</Say>
            <Start>
                <Stream url="wss://example.com/api/voice/twilio/stream/twilio-CA123" />
            </Start>
        </Response>
        ```

    Twilio Configuration:
        1. Set Voice Webhook URL: https://your-domain.com/api/voice/twilio/inbound
        2. Set HTTP Method: POST
        3. Ensure WebSocket is accessible (wss:// protocol)

    Reference:
        - Twilio <Stream>: https://www.twilio.com/docs/voice/twiml/stream
    """
    try:
        # Parse Twilio form data
        form_data = await request.form()

        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From")
        to_number = form_data.get("To")
        call_status = form_data.get("CallStatus", "unknown")

        logger.info(
            f"Twilio inbound call: call_sid={call_sid}, "
            f"from={from_number}, to={to_number}, status={call_status}"
        )

        # Validate required parameters
        if not call_sid:
            raise HTTPException(status_code=400, detail="Missing CallSid parameter")
        if not from_number:
            raise HTTPException(status_code=400, detail="Missing From parameter")
        if not to_number:
            raise HTTPException(status_code=400, detail="Missing To parameter")

        # Create voice session
        session = create_twilio_session(
            call_sid=call_sid,
            from_number=from_number,
            to_number=to_number,
            project_id="default",  # TODO: Derive from phone number mapping
        )

        # Generate WebSocket URL
        # Use request host header to construct full URL
        host = request.headers.get("host", "localhost:8000")
        stream_url = f"wss://{host}/api/voice/twilio/stream/{session.session_id}"

        # Generate TwiML response
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Connecting to agent.</Say>
    <Start>
        <Stream url="{stream_url}" />
    </Start>
</Response>"""

        logger.info(f"Generated TwiML with stream URL: {stream_url}")

        # Return TwiML (XML response)
        return Response(content=twiml, media_type="application/xml")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling Twilio inbound call: {e}", exc_info=True)

        # Return error TwiML
        error_twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Sorry, we encountered an error. Please try again later.</Say>
    <Hangup />
</Response>"""

        return Response(content=error_twiml, media_type="application/xml")


# ============================================
# WebSocket Endpoint: Media Streams
# ============================================


@router.websocket("/api/voice/twilio/stream/{session_id}")
async def twilio_stream_websocket(websocket: WebSocket, session_id: str):
    """Handle Twilio Media Streams WebSocket connection.

    This endpoint receives real-time audio from Twilio Media Streams,
    transcribes it using Whisper STT, and sends assistant responses.

    Twilio Media Streams Protocol:
        - Event: "start" - Stream initialization
        - Event: "media" - Audio data (μ-law, 8kHz, base64-encoded)
        - Event: "stop" - Stream termination

    Example "media" Event:
        ```json
        {
            "event": "media",
            "sequenceNumber": "4",
            "media": {
                "track": "inbound",
                "chunk": "4",
                "timestamp": "5000",
                "payload": "base64-encoded-mulaw-audio"
            },
            "streamSid": "MZ..."
        }
        ```

    Reference:
        - Media Streams Protocol: https://www.twilio.com/docs/voice/media-streams#message-types
    """
    await websocket.accept()
    logger.info(f"Twilio Media Streams WebSocket connected: {session_id}")

    # Get session
    session = get_twilio_session(session_id)
    if not session:
        await websocket.send_json({
            "type": "error",
            "error": f"Session not found: {session_id}",
        })
        await websocket.close()
        logger.warning(f"Twilio stream connection rejected: session not found ({session_id})")
        return

    # Update session state
    session.state = VoiceSessionState.ACTIVE
    session.last_activity_at = utc_now()

    # Initialize STT service
    stt_service = WhisperLocalSTT(model_name="base", device="cpu")

    # Audio buffer for accumulating chunks
    audio_buffer = bytearray()
    stream_sid = None

    # Audit log (via logging for MVP)
    logger.info(
        f"AUDIT: voice.twilio.stream.connected "
        f"session_id={session_id} call_sid={session.transport_metadata.get('call_sid')}"
    )

    try:
        async for message in websocket.iter_json():
            event_type = message.get("event")

            if event_type == "start":
                # Stream started
                start_data = message.get("start", {})
                stream_sid = start_data.get("streamSid")
                call_sid = start_data.get("callSid")

                logger.info(
                    f"Twilio Media Stream started: stream_sid={stream_sid}, "
                    f"call_sid={call_sid}"
                )

                # Update session metadata
                session.transport_metadata["stream_sid"] = stream_sid

                # Audit log (via logging for MVP)
                logger.info(
                    f"AUDIT: voice.twilio.stream.started "
                    f"session_id={session_id} stream_sid={stream_sid} call_sid={call_sid}"
                )

            elif event_type == "media":
                # Audio data received
                media_data = message.get("media", {})
                payload_b64 = media_data.get("payload", "")
                chunk_num = media_data.get("chunk")
                timestamp = media_data.get("timestamp")

                # Decode μ-law audio
                mulaw_audio = base64.b64decode(payload_b64)

                # Transcode μ-law → PCM 16-bit
                try:
                    pcm_audio = transcode_mulaw_to_pcm(mulaw_audio)
                except Exception as e:
                    logger.error(f"Audio transcoding error: {e}", exc_info=True)
                    continue

                # Accumulate audio in buffer
                audio_buffer.extend(pcm_audio)

                # Update activity timestamp
                session.last_activity_at = utc_now()

                logger.debug(
                    f"Received audio chunk #{chunk_num}: "
                    f"{len(mulaw_audio)} bytes μ-law → {len(pcm_audio)} bytes PCM "
                    f"(buffer: {len(audio_buffer)} bytes)"
                )

                # Process when buffer reaches threshold (3 seconds at 8kHz mono 16-bit)
                # Twilio streams at 8kHz, so 3 seconds = 8000 * 2 * 3 = 48000 bytes
                BUFFER_THRESHOLD = 48000

                if len(audio_buffer) >= BUFFER_THRESHOLD:
                    # Transcribe accumulated audio
                    try:
                        logger.info(f"Transcribing {len(audio_buffer)} bytes of audio...")

                        transcript = await stt_service.transcribe_audio(
                            bytes(audio_buffer),
                            sample_rate=8000,  # Twilio Media Streams uses 8kHz
                        )

                        if transcript and transcript.strip():
                            logger.info(f"Transcript: '{transcript}'")

                            # Send STT result
                            await websocket.send_json({
                                "type": "voice.stt.final",
                                "text": transcript,
                                "session_id": session_id,
                                "timestamp": iso_z(utc_now()),
                            })

                            # Get assistant response
                            assistant_text = await get_assistant_response(
                                transcript,
                                session_id,
                            )

                            # Send assistant response
                            await send_twilio_say(websocket, assistant_text, session)

                            # Audit log (via logging for MVP)
                            logger.info(
                                f"AUDIT: voice.twilio.transcript "
                                f"session_id={session_id} stream_sid={stream_sid} "
                                f"transcript='{transcript}' response='{assistant_text}'"
                            )
                        else:
                            logger.debug("Transcription returned empty (silence detected)")

                    except Exception as e:
                        logger.error(f"STT processing error: {e}", exc_info=True)
                        await websocket.send_json({
                            "type": "error",
                            "error": f"STT processing failed: {str(e)}",
                        })

                    # Clear buffer
                    audio_buffer.clear()

            elif event_type == "stop":
                # Stream stopped
                stop_data = message.get("stop", {})
                logger.info(
                    f"Twilio Media Stream stopped: stream_sid={stream_sid}, "
                    f"reason={stop_data}"
                )

                # Process remaining audio in buffer
                if len(audio_buffer) > 0:
                    try:
                        logger.info(f"Processing final {len(audio_buffer)} bytes...")

                        transcript = await stt_service.transcribe_audio(
                            bytes(audio_buffer),
                            sample_rate=8000,
                        )

                        if transcript and transcript.strip():
                            logger.info(f"Final transcript: '{transcript}'")

                            await websocket.send_json({
                                "type": "voice.stt.final",
                                "text": transcript,
                                "session_id": session_id,
                                "timestamp": iso_z(utc_now()),
                            })

                            assistant_text = await get_assistant_response(
                                transcript,
                                session_id,
                            )

                            await send_twilio_say(websocket, assistant_text, session)

                    except Exception as e:
                        logger.error(f"Final STT processing error: {e}", exc_info=True)

                # Update session state
                session.state = VoiceSessionState.STOPPED

                # Audit log (via logging for MVP)
                logger.info(
                    f"AUDIT: voice.twilio.stream.stopped "
                    f"session_id={session_id} stream_sid={stream_sid} reason={stop_data}"
                )

                break

            else:
                logger.warning(f"Unknown Twilio event type: {event_type}")

    except WebSocketDisconnect:
        logger.info(f"Twilio Media Streams WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(
            f"Twilio Media Streams error (session: {session_id}): {e}",
            exc_info=True,
        )

        # Audit log (via logging for MVP)
        logger.error(
            f"AUDIT: voice.twilio.stream.error "
            f"session_id={session_id} stream_sid={stream_sid} error={str(e)}"
        )

        try:
            await websocket.send_json({
                "type": "error",
                "error": str(e),
            })
        except Exception:
            pass  # Connection may already be closed
    finally:
        # Update session state
        if session:
            session.state = VoiceSessionState.STOPPED

        # Close WebSocket
        try:
            await websocket.close()
        except Exception:
            pass

        logger.info(f"Twilio Media Streams session ended: {session_id}")
