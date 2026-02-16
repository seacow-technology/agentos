"""
OpenAI Whisper API STT implementation.
"""

import asyncio
import logging
import os
from typing import AsyncIterator, Optional
import io

from octopusos.core.communication.voice.stt.base import ISTTProvider

logger = logging.getLogger(__name__)


class OpenAIWhisperProvider(ISTTProvider):
    """
    OpenAI Whisper API Speech-to-Text implementation.

    Features:
    - Cloud-based transcription using OpenAI's Whisper API
    - No local model loading required
    - Support for multiple languages
    - Automatic language detection
    - Error handling with proper error codes

    Configuration:
    - OPENAI_API_KEY: API key (required)
    - OPENAI_STT_MODEL: Model name (default: "whisper-1")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "whisper-1",
        language: Optional[str] = None,
    ):
        """
        Initialize OpenAI Whisper provider.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
            model: Model name (default: "whisper-1").
            language: Target language code (e.g., "en", "zh"). None for auto-detection.

        Raises:
            ValueError: If API key is not provided or empty.
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model = model
        self.language = language
        self._client = None

        logger.info(
            f"OpenAIWhisperProvider initialized with model={model}, "
            f"language={language or 'auto'}"
        )

    def _get_client(self):
        """Get or create OpenAI client (lazy initialization)."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as e:
                raise RuntimeError(
                    "openai package is not installed. "
                    "Install it with: pip install openai>=1.0.0"
                ) from e

            self._client = AsyncOpenAI(api_key=self.api_key)
            logger.debug("OpenAI client initialized")

        return self._client

    async def transcribe_audio(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribe audio bytes to text using OpenAI Whisper API.

        Args:
            audio_bytes: Raw audio data in PCM int16 format.
            sample_rate: Audio sample rate in Hz (default: 16000).

        Returns:
            Transcribed text as a string.

        Raises:
            ValueError: If audio format is invalid.
            RuntimeError: If transcription fails (API error, network error, etc.).
        """
        if not audio_bytes:
            logger.warning("Empty audio bytes provided for transcription")
            return ""

        try:
            # Convert PCM bytes to WAV format for API
            wav_bytes = self._pcm_to_wav(audio_bytes, sample_rate)

            # Create file-like object
            audio_file = io.BytesIO(wav_bytes)
            audio_file.name = "audio.wav"

            # Call OpenAI API
            client = self._get_client()
            logger.debug(f"Calling OpenAI Whisper API (model={self.model}, size={len(wav_bytes)} bytes)")

            transcription = await client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
                language=self.language,
                response_format="text",
            )

            text = transcription.strip() if isinstance(transcription, str) else ""
            try:
                from octopusos.core.llm.usage_events import LLMUsageEvent, record_llm_usage_event_best_effort
                record_llm_usage_event_best_effort(
                    LLMUsageEvent(
                        provider="openai",
                        model=self.model,
                        operation="voice.stt.transcribe",
                        confidence="LOW",
                        metadata={
                            "bytes": len(audio_bytes),
                            "sample_rate": sample_rate,
                            "language": self.language,
                        },
                    )
                )
            except Exception:
                pass

            if text:
                logger.debug(f"Transcription successful: '{text[:50]}...'")
            else:
                logger.debug("Transcription returned empty text (possibly silence)")

            return text

        except ValueError as e:
            # Re-raise ValueError from audio conversion
            raise
        except Exception as e:
            logger.error(f"OpenAI Whisper API transcription failed: {e}")
            # Return error with proper error code
            raise RuntimeError(f"STT_API_ERROR: OpenAI Whisper API failed: {e}") from e

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[str]:
        """
        Transcribe streaming audio to text.

        Note: OpenAI Whisper API doesn't support true streaming, so this
        implementation buffers audio chunks and transcribes when enough
        data is accumulated.

        Args:
            audio_stream: Async iterator yielding audio chunks.

        Yields:
            Transcribed text segments as they become available.

        Raises:
            ValueError: If audio format is invalid.
            RuntimeError: If transcription fails.
        """
        # Buffer for accumulating audio chunks
        buffer = bytearray()
        MIN_BUFFER_SIZE = 16000 * 2 * 3  # 3 seconds of 16kHz int16 audio

        try:
            async for chunk in audio_stream:
                buffer.extend(chunk)

                # When buffer is large enough, transcribe
                if len(buffer) >= MIN_BUFFER_SIZE:
                    audio_bytes = bytes(buffer)
                    buffer.clear()

                    text = await self.transcribe_audio(audio_bytes)
                    if text:
                        yield text

            # Transcribe remaining buffer
            if buffer:
                audio_bytes = bytes(buffer)
                text = await self.transcribe_audio(audio_bytes)
                if text:
                    yield text

        except Exception as e:
            logger.error(f"Stream transcription failed: {e}")
            raise RuntimeError(f"Stream transcription failed: {e}") from e

    def _pcm_to_wav(self, pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
        """
        Convert PCM int16 bytes to WAV format.

        Args:
            pcm_bytes: Raw PCM int16 audio data.
            sample_rate: Audio sample rate in Hz.

        Returns:
            WAV format bytes.

        Raises:
            ValueError: If conversion fails.
        """
        try:
            import struct

            # WAV header parameters
            num_channels = 1  # Mono
            sample_width = 2  # 16-bit = 2 bytes
            num_frames = len(pcm_bytes) // sample_width

            # Build WAV header
            wav_header = struct.pack(
                '<4sI4s4sIHHIIHH4sI',
                b'RIFF',
                36 + len(pcm_bytes),  # Chunk size
                b'WAVE',
                b'fmt ',
                16,  # Subchunk1 size (PCM)
                1,   # Audio format (PCM)
                num_channels,
                sample_rate,
                sample_rate * num_channels * sample_width,  # Byte rate
                num_channels * sample_width,  # Block align
                sample_width * 8,  # Bits per sample
                b'data',
                len(pcm_bytes),  # Subchunk2 size
            )

            return wav_header + pcm_bytes

        except Exception as e:
            raise ValueError(f"Failed to convert PCM to WAV: {e}") from e
