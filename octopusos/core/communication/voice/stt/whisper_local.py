"""
Local Whisper STT implementation using faster-whisper.
"""

import asyncio
import logging
from typing import AsyncIterator, Optional

import numpy as np

from agentos.core.communication.voice.stt.base import ISTTProvider

logger = logging.getLogger(__name__)


class WhisperLocalSTT(ISTTProvider):
    """
    Local Whisper Speech-to-Text implementation using faster-whisper.

    Features:
    - Lazy model initialization (loads on first use to avoid startup delay)
    - Multiple model sizes: tiny, base, small, medium, large
    - Device selection: cpu, cuda, auto
    - Automatic language detection or explicit language setting
    - Error handling for model loading and transcription failures
    """

    def __init__(
        self,
        model_name: str = "base",
        device: str = "cpu",
        language: Optional[str] = None,
    ):
        """
        Initialize WhisperLocalSTT.

        Args:
            model_name: Model size (tiny/base/small/medium/large). Default: "base".
            device: Device to run inference on (cpu/cuda/auto). Default: "cpu".
            language: Target language code (e.g., "en", "zh"). None for auto-detection.
        """
        self.model_name = model_name
        self.device = device
        self.language = language
        self._model = None  # Lazy initialization
        self._model_loading = False
        self._model_load_lock = asyncio.Lock()

        logger.info(
            f"WhisperLocalSTT initialized with model={model_name}, "
            f"device={device}, language={language or 'auto'}"
        )

    async def _load_model(self):
        """
        Lazy load the Whisper model.

        This method is called on first transcription to avoid startup delays.
        Uses a lock to prevent concurrent loading attempts.
        """
        if self._model is not None:
            return

        async with self._model_load_lock:
            # Double-check after acquiring lock
            if self._model is not None:
                return

            if self._model_loading:
                # Another task is loading, wait for it
                while self._model_loading:
                    await asyncio.sleep(0.1)
                return

            self._model_loading = True

            try:
                logger.info(f"Loading Whisper model '{self.model_name}' on device '{self.device}'...")

                # Import here to avoid import errors if faster-whisper is not installed
                try:
                    from faster_whisper import WhisperModel
                except ImportError as e:
                    raise RuntimeError(
                        "faster-whisper is not installed. "
                        "Install it with: pip install faster-whisper>=1.0.0"
                    ) from e

                # Run model loading in thread pool to avoid blocking
                loop = asyncio.get_running_loop()
                self._model = await loop.run_in_executor(
                    None,
                    lambda: WhisperModel(
                        self.model_name,
                        device=self.device,
                        compute_type="int8" if self.device == "cpu" else "float16",
                    ),
                )

                logger.info(f"Whisper model '{self.model_name}' loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                raise RuntimeError(f"Failed to load Whisper model '{self.model_name}': {e}") from e
            finally:
                self._model_loading = False

    def _bytes_to_numpy(self, audio_bytes: bytes, sample_rate: int = 16000) -> np.ndarray:
        """
        Convert audio bytes (int16 PCM) to numpy float32 array normalized to [-1, 1].

        Args:
            audio_bytes: Raw audio data in PCM int16 format.
            sample_rate: Audio sample rate in Hz.

        Returns:
            Numpy array of float32 samples normalized to [-1, 1].

        Raises:
            ValueError: If audio format is invalid.
        """
        try:
            # Convert bytes to int16 numpy array
            audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)

            # Convert to float32 and normalize to [-1, 1]
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            return audio_float32
        except Exception as e:
            raise ValueError(f"Failed to convert audio bytes to numpy array: {e}") from e

    async def transcribe_audio(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribe audio bytes to text using local Whisper model.

        Args:
            audio_bytes: Raw audio data in PCM int16 format.
            sample_rate: Audio sample rate in Hz (default: 16000).

        Returns:
            Transcribed text as a string.

        Raises:
            ValueError: If audio format is invalid.
            RuntimeError: If transcription fails or model loading fails.
        """
        if not audio_bytes:
            logger.warning("Empty audio bytes provided for transcription")
            return ""

        # Ensure model is loaded
        await self._load_model()

        try:
            # Convert audio bytes to numpy array
            audio_array = self._bytes_to_numpy(audio_bytes, sample_rate)

            # Run transcription in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            segments, info = await loop.run_in_executor(
                None,
                lambda: self._model.transcribe(
                    audio_array,
                    language=self.language,
                    beam_size=5,
                    vad_filter=True,  # Enable VAD filtering
                ),
            )

            # Extract text from segments
            text = " ".join([segment.text for segment in segments])
            text = text.strip()

            if text:
                logger.debug(
                    f"Transcription successful: '{text[:50]}...' "
                    f"(detected language: {info.language})"
                )
            else:
                logger.debug("Transcription returned empty text (possibly silence)")

            return text

        except ValueError as e:
            # Re-raise ValueError from audio conversion
            raise
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise RuntimeError(f"Transcription failed: {e}") from e

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[str]:
        """
        Transcribe streaming audio to text in real-time.

        Note: This is a simple implementation that buffers audio and transcribes
        when enough data is accumulated. For true real-time streaming,
        consider using a different model or service.

        Args:
            audio_stream: Async iterator yielding audio chunks.

        Yields:
            Transcribed text segments as they become available.

        Raises:
            ValueError: If audio format is invalid.
            RuntimeError: If transcription fails.
        """
        # Ensure model is loaded
        await self._load_model()

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
