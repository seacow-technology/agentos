"""Base interface for Text-to-Speech (TTS) providers.

This module defines the abstract interface that all TTS providers must implement,
ensuring consistent behavior across different TTS engines.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, List, Optional


class ITTSProvider(ABC):
    """Abstract interface for TTS providers.

    All TTS providers must implement this interface to ensure consistent
    behavior for streaming synthesis, cancellation, and voice management.
    """

    @abstractmethod
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
            voice_id: Voice identifier (provider-specific)
            speed: Playback speed multiplier (0.25 - 4.0)
            **kwargs: Additional provider-specific parameters

        Yields:
            Audio chunks (PCM s16le, mono, 16kHz recommended)

        Example:
            >>> async for chunk in provider.synthesize("Hello world", "alloy"):
            ...     await send_audio(chunk)
        """
        pass

    @abstractmethod
    async def cancel(self, request_id: str) -> bool:
        """Cancel an ongoing synthesis request.

        Used for barge-in scenarios where TTS must be stopped immediately.

        Args:
            request_id: Request identifier returned by synthesize()

        Returns:
            True if successfully cancelled, False if request not found
        """
        pass

    @abstractmethod
    def get_voices(self) -> List[Dict[str, str]]:
        """Get list of available voices.

        Returns:
            List of voice dictionaries with 'id', 'name', 'language' keys

        Example:
            >>> voices = provider.get_voices()
            >>> print(voices[0])
            {'id': 'alloy', 'name': 'Alloy', 'language': 'en'}
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name for logging and metrics.

        Returns:
            Provider name (e.g., "openai", "elevenlabs")
        """
        pass
