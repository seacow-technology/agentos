"""Mock TTS Provider - Testing implementation.

This provider generates silence or beeps for testing TTS functionality
without requiring external API calls.
"""

import asyncio
import logging
import struct
from typing import AsyncIterator, Dict, List

from .base import ITTSProvider

logger = logging.getLogger(__name__)


class MockTTSProvider(ITTSProvider):
    """Mock TTS provider for testing."""

    VOICES = [
        {"id": "test-voice-1", "name": "Test Voice 1", "language": "en"},
        {"id": "test-voice-2", "name": "Test Voice 2", "language": "en"},
    ]

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_duration_ms: int = 100,
        generate_tone: bool = False
    ):
        """Initialize mock TTS provider.

        Args:
            sample_rate: Audio sample rate (Hz)
            chunk_duration_ms: Duration of each audio chunk (ms)
            generate_tone: Whether to generate a tone (True) or silence (False)
        """
        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        self.generate_tone = generate_tone
        self.active_requests = {}

        logger.info(f"MockTTSProvider initialized (generate_tone={generate_tone})")

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        **kwargs
    ) -> AsyncIterator[bytes]:
        """Generate mock audio chunks.

        Args:
            text: Text to "synthesize" (used to calculate duration)
            voice_id: Voice ID (ignored)
            speed: Speed multiplier (affects duration)
            **kwargs: Additional parameters (ignored)

        Yields:
            Audio chunks (PCM s16le, mono)
        """
        import uuid
        request_id = str(uuid.uuid4())
        self.active_requests[request_id] = False

        # Calculate number of chunks based on text length
        # Assume ~150 words per minute, adjust by speed
        words = len(text.split())
        duration_seconds = (words / 150) * 60 / speed
        num_chunks = int((duration_seconds * 1000) / self.chunk_duration_ms)

        logger.info(f"Generating mock TTS (text_length={len(text)}, words={words}, "
                   f"duration={duration_seconds:.1f}s, chunks={num_chunks})")

        # Generate chunks
        samples_per_chunk = int((self.sample_rate * self.chunk_duration_ms) / 1000)

        for i in range(num_chunks):
            # Check cancellation
            if self.active_requests.get(request_id, False):
                logger.info(f"Mock TTS cancelled (request_id={request_id})")
                break

            # Generate audio data
            if self.generate_tone:
                # Generate a simple 440Hz tone (A4 note)
                chunk = self._generate_tone_chunk(samples_per_chunk, 440.0)
            else:
                # Generate silence
                chunk = self._generate_silence_chunk(samples_per_chunk)

            yield chunk

            # Simulate processing delay
            await asyncio.sleep(self.chunk_duration_ms / 1000)

        logger.info(f"Mock TTS completed (request_id={request_id})")
        self.active_requests.pop(request_id, None)

    def _generate_silence_chunk(self, num_samples: int) -> bytes:
        """Generate silence audio chunk.

        Args:
            num_samples: Number of samples

        Returns:
            PCM s16le audio (all zeros)
        """
        return bytes(num_samples * 2)  # 2 bytes per sample (s16le)

    def _generate_tone_chunk(self, num_samples: int, frequency: float) -> bytes:
        """Generate tone audio chunk.

        Args:
            num_samples: Number of samples
            frequency: Tone frequency (Hz)

        Returns:
            PCM s16le audio (sine wave)
        """
        import math

        chunk = bytearray()
        amplitude = 10000  # Max amplitude for s16le is 32767

        for i in range(num_samples):
            # Generate sine wave
            t = i / self.sample_rate
            sample = int(amplitude * math.sin(2 * math.pi * frequency * t))

            # Convert to s16le (little-endian signed 16-bit)
            chunk.extend(struct.pack("<h", sample))

        return bytes(chunk)

    async def cancel(self, request_id: str) -> bool:
        """Cancel mock synthesis.

        Args:
            request_id: Request identifier

        Returns:
            True if cancelled, False if not found
        """
        if request_id in self.active_requests:
            self.active_requests[request_id] = True
            return True
        return False

    def get_voices(self) -> List[Dict[str, str]]:
        """Get mock voices.

        Returns:
            List of mock voice dictionaries
        """
        return self.VOICES.copy()

    def get_provider_name(self) -> str:
        """Get provider name.

        Returns:
            Provider name
        """
        return "mock"
