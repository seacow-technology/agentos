"""
Base interface for Speech-to-Text providers.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator


class ISTTProvider(ABC):
    """
    Abstract base class for Speech-to-Text providers.

    All STT implementations must inherit from this class and implement
    the transcribe_audio and transcribe_stream methods.
    """

    @abstractmethod
    async def transcribe_audio(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw audio data in PCM format (int16).
            sample_rate: Audio sample rate in Hz (default: 16000).

        Returns:
            Transcribed text as a string.

        Raises:
            ValueError: If audio format is invalid.
            RuntimeError: If transcription fails.
        """
        pass

    @abstractmethod
    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[str]:
        """
        Transcribe streaming audio to text in real-time.

        Args:
            audio_stream: Async iterator yielding audio chunks.

        Yields:
            Transcribed text segments as they become available.

        Raises:
            ValueError: If audio format is invalid.
            RuntimeError: If transcription fails.
        """
        pass
