"""OpenAI TTS Provider - Streaming text-to-speech using OpenAI API.

This provider uses OpenAI's TTS API (tts-1, tts-1-hd models) to synthesize
speech with natural-sounding voices.

Supported voices: alloy, echo, fable, onyx, nova, shimmer

Features:
- Streaming synthesis (low latency)
- Multiple voices
- Speed control (0.25 - 4.0x)
- Cancellation support (barge-in)
"""

import asyncio
import logging
import uuid
from typing import AsyncIterator, Dict, List, Optional

from openai import AsyncOpenAI

from .base import ITTSProvider

logger = logging.getLogger(__name__)


class OpenAITTSProvider(ITTSProvider):
    """OpenAI TTS provider implementation."""

    # Available voices (as of 2025-01)
    VOICES = [
        {"id": "alloy", "name": "Alloy", "language": "en", "description": "Neutral, balanced"},
        {"id": "echo", "name": "Echo", "language": "en", "description": "Male, clear"},
        {"id": "fable", "name": "Fable", "language": "en", "description": "British, expressive"},
        {"id": "onyx", "name": "Onyx", "language": "en", "description": "Male, deep"},
        {"id": "nova", "name": "Nova", "language": "en", "description": "Female, friendly"},
        {"id": "shimmer", "name": "Shimmer", "language": "en", "description": "Female, warm"},
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "tts-1",
        chunk_size: int = 4096
    ):
        """Initialize OpenAI TTS provider.

        Args:
            api_key: OpenAI API key (uses OPENAI_API_KEY env var if not provided)
            model: TTS model ("tts-1" or "tts-1-hd")
            chunk_size: Audio chunk size in bytes
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.chunk_size = chunk_size
        self.active_requests: Dict[str, bool] = {}  # request_id -> cancelled flag

        logger.info(f"OpenAITTSProvider initialized (model={model}, chunk_size={chunk_size})")

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        **kwargs
    ) -> AsyncIterator[bytes]:
        """Synthesize text to audio chunks (streaming).

        Args:
            text: Text to synthesize
            voice_id: Voice ID (alloy, echo, fable, onyx, nova, shimmer)
            speed: Playback speed (0.25 - 4.0)
            **kwargs: Additional parameters (model, response_format)

        Yields:
            Audio chunks (opus or pcm_s16le depending on response_format)
        """
        request_id = str(uuid.uuid4())
        self.active_requests[request_id] = False  # Not cancelled yet

        # Validate voice
        if voice_id not in [v["id"] for v in self.VOICES]:
            logger.warning(f"Invalid voice_id '{voice_id}', defaulting to 'alloy'")
            voice_id = "alloy"

        # Clamp speed
        speed = max(0.25, min(4.0, speed))

        # Override model if specified
        model = kwargs.get("model", self.model)
        response_format = kwargs.get("response_format", "opus")

        logger.info(f"Starting TTS synthesis (request_id={request_id}, text_length={len(text)}, "
                   f"voice={voice_id}, speed={speed}, model={model})")

        try:
            # Call OpenAI TTS API
            response = await self.client.audio.speech.create(
                model=model,
                voice=voice_id,
                input=text,
                speed=speed,
                response_format=response_format
            )
            try:
                from octopusos.core.llm.usage_events import LLMUsageEvent, record_llm_usage_event_best_effort
                record_llm_usage_event_best_effort(
                    LLMUsageEvent(
                        provider="openai",
                        model=model,
                        operation="voice.tts.synthesize_stream",
                        confidence="LOW",
                        metadata={
                            "chars": len(text),
                            "voice": voice_id,
                            "speed": speed,
                            "response_format": response_format,
                        },
                    )
                )
            except Exception:
                pass

            # Stream audio chunks
            chunk_count = 0
            async for chunk in response.iter_bytes(chunk_size=self.chunk_size):
                # Check if cancelled
                if self.active_requests.get(request_id, False):
                    logger.info(f"TTS synthesis cancelled (request_id={request_id})")
                    break

                yield chunk
                chunk_count += 1

            logger.info(f"TTS synthesis completed (request_id={request_id}, chunks={chunk_count})")

        except Exception as e:
            logger.error(f"TTS synthesis failed (request_id={request_id}): {e}", exc_info=True)
            raise
        finally:
            # Cleanup
            self.active_requests.pop(request_id, None)

    async def cancel(self, request_id: str) -> bool:
        """Cancel an ongoing synthesis request.

        Args:
            request_id: Request identifier

        Returns:
            True if successfully cancelled, False if request not found
        """
        if request_id in self.active_requests:
            self.active_requests[request_id] = True
            logger.info(f"Marked TTS request for cancellation: {request_id}")
            return True

        logger.warning(f"TTS request not found for cancellation: {request_id}")
        return False

    def get_voices(self) -> List[Dict[str, str]]:
        """Get list of available voices.

        Returns:
            List of voice dictionaries
        """
        return self.VOICES.copy()

    def get_provider_name(self) -> str:
        """Get provider name.

        Returns:
            Provider name
        """
        return "openai"


# Helper function for transcoding (if needed)
async def transcode_opus_to_pcm(opus_data: bytes) -> bytes:
    """Transcode Opus audio to PCM s16le.

    Args:
        opus_data: Opus-encoded audio

    Returns:
        PCM s16le audio (16kHz, mono)

    Note:
        Requires ffmpeg. This is a placeholder - actual implementation
        would use subprocess or a library like pydub.
    """
    # TODO: Implement if needed (opus → pcm transcoding)
    # For now, assume clients can handle opus directly
    return opus_data
