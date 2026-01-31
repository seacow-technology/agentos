"""
Voice Activity Detection (VAD) using webrtcvad.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


class VADDetector:
    """
    Voice Activity Detection using webrtcvad.

    Features:
    - Detects speech vs non-speech in audio frames
    - Configurable aggressiveness level (0-3)
    - Silence end detection for sentence boundary detection
    """

    def __init__(self, aggressiveness: int = 2):
        """
        Initialize VADDetector.

        Args:
            aggressiveness: VAD aggressiveness level (0-3).
                0: Least aggressive (more speech detected)
                3: Most aggressive (less speech detected)
                Default: 2 (balanced)

        Raises:
            ValueError: If aggressiveness is not in range [0, 3].
            RuntimeError: If webrtcvad is not installed.
        """
        if not 0 <= aggressiveness <= 3:
            raise ValueError(f"Aggressiveness must be in range [0, 3], got {aggressiveness}")

        try:
            import webrtcvad
        except ImportError as e:
            raise RuntimeError(
                "webrtcvad is not installed. Install it with: pip install webrtcvad>=2.0.10"
            ) from e

        self.aggressiveness = aggressiveness
        self._vad = webrtcvad.Vad(aggressiveness)

        logger.info(f"VADDetector initialized with aggressiveness={aggressiveness}")

    def is_speech(self, audio_chunk: bytes, sample_rate: int = 16000) -> bool:
        """
        Detect if audio chunk contains speech.

        Args:
            audio_chunk: Raw audio data in PCM int16 format.
                Must be 10, 20, or 30 ms of audio.
            sample_rate: Audio sample rate in Hz (must be 8000, 16000, or 32000).
                Default: 16000.

        Returns:
            True if speech is detected, False otherwise.

        Raises:
            ValueError: If sample_rate is not supported or chunk size is invalid.
            RuntimeError: If VAD detection fails.
        """
        if sample_rate not in (8000, 16000, 32000):
            raise ValueError(
                f"Sample rate must be 8000, 16000, or 32000 Hz, got {sample_rate}"
            )

        # Calculate expected frame lengths (in bytes) for 10, 20, 30 ms
        # Each sample is 2 bytes (int16)
        valid_lengths = [
            int(sample_rate * duration_ms / 1000) * 2
            for duration_ms in (10, 20, 30)
        ]

        if len(audio_chunk) not in valid_lengths:
            raise ValueError(
                f"Audio chunk must be 10, 20, or 30 ms ({valid_lengths} bytes "
                f"for {sample_rate} Hz), got {len(audio_chunk)} bytes"
            )

        try:
            return self._vad.is_speech(audio_chunk, sample_rate)
        except Exception as e:
            logger.error(f"VAD detection failed: {e}")
            raise RuntimeError(f"VAD detection failed: {e}") from e

    def detect_silence_end(
        self,
        audio_buffer: List[bytes],
        sample_rate: int = 16000,
        threshold_ms: int = 500,
    ) -> bool:
        """
        Detect if silence has ended (sentence boundary detection).

        This method checks if the last N frames in the buffer are all non-speech.
        If yes, it indicates that the speaker has stopped talking.

        Args:
            audio_buffer: List of audio frames (each 10, 20, or 30 ms).
            sample_rate: Audio sample rate in Hz (default: 16000).
            threshold_ms: Duration of consecutive silence required (in ms).
                Default: 500 ms.

        Returns:
            True if silence end is detected (consecutive non-speech frames >= threshold),
            False otherwise.

        Raises:
            ValueError: If audio_buffer is empty or sample_rate is invalid.
        """
        if not audio_buffer:
            raise ValueError("Audio buffer is empty")

        if sample_rate not in (8000, 16000, 32000):
            raise ValueError(
                f"Sample rate must be 8000, 16000, or 32000 Hz, got {sample_rate}"
            )

        # Calculate frame duration from first frame
        # Assume all frames have the same duration
        frame_bytes = len(audio_buffer[0])
        samples_per_frame = frame_bytes // 2  # 2 bytes per sample (int16)
        frame_duration_ms = (samples_per_frame / sample_rate) * 1000

        # Calculate number of frames needed for threshold
        frames_needed = int(threshold_ms / frame_duration_ms)

        if len(audio_buffer) < frames_needed:
            # Not enough frames to determine silence
            return False

        # Check last N frames
        last_frames = audio_buffer[-frames_needed:]

        try:
            # All frames must be non-speech
            for frame in last_frames:
                if self.is_speech(frame, sample_rate):
                    return False

            logger.debug(
                f"Silence end detected: {frames_needed} consecutive non-speech frames "
                f"({threshold_ms} ms)"
            )
            return True

        except Exception as e:
            logger.error(f"Silence detection failed: {e}")
            # If detection fails, assume no silence end
            return False
