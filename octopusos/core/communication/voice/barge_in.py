"""Barge-In Detection and Execution for Voice Communication.

Barge-in allows users to interrupt TTS playback by speaking, creating
a more natural conversational experience.

Detection methods:
- RMS energy threshold (simple, low latency)
- VAD (Voice Activity Detection) using webrtcvad
- Hybrid (RMS + VAD)

Flow:
1. TTS starts playing
2. Continue listening to user microphone
3. If speech detected → Cancel TTS + Stop playback
4. Resume listening for user input
"""

import logging
import struct
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BargeInConfig:
    """Configuration for barge-in detection.

    Attributes:
        enabled: Whether barge-in is enabled
        vad_energy_threshold: RMS energy threshold (0.0 - 1.0)
        detection_mode: Detection mode ("rms", "vad", "rms_or_vad")
        cancel_delay_ms: Delay before cancelling TTS (ms)
        min_speech_duration_ms: Minimum speech duration to trigger barge-in
    """

    enabled: bool = True
    vad_energy_threshold: float = 0.03  # RMS threshold (empirically tuned)
    detection_mode: str = "rms_or_vad"  # "rms", "vad", "rms_or_vad"
    cancel_delay_ms: int = 100  # Delay before cancelling (avoid false positives)
    min_speech_duration_ms: int = 200  # Minimum speech duration


class BargeInDetector:
    """Detects user speech during TTS playback."""

    def __init__(self, config: BargeInConfig):
        """Initialize barge-in detector.

        Args:
            config: Barge-in configuration
        """
        self.config = config
        self.is_playing_tts = False
        self.consecutive_speech_frames = 0

        # Initialize VAD if needed
        self._vad = None
        if "vad" in config.detection_mode:
            try:
                import webrtcvad
                self._vad = webrtcvad.Vad(2)  # Aggressiveness 2 (0-3)
                logger.info("Initialized WebRTC VAD for barge-in detection")
            except ImportError:
                logger.warning("webrtcvad not available, falling back to RMS-only detection")
                self.config.detection_mode = "rms"

    def start_tts_playback(self):
        """Mark TTS playback as started."""
        self.is_playing_tts = True
        self.consecutive_speech_frames = 0
        logger.debug("Barge-in detector: TTS playback started")

    def stop_tts_playback(self):
        """Mark TTS playback as stopped."""
        self.is_playing_tts = False
        self.consecutive_speech_frames = 0
        logger.debug("Barge-in detector: TTS playback stopped")

    def detect(self, audio_chunk: bytes, sample_rate: int = 16000) -> bool:
        """Detect if audio chunk contains speech (during TTS playback).

        Args:
            audio_chunk: Raw audio data (PCM s16le)
            sample_rate: Audio sample rate (Hz)

        Returns:
            True if barge-in should be triggered, False otherwise
        """
        if not self.config.enabled or not self.is_playing_tts:
            return False

        # Detect speech using configured method
        is_speech = False

        if "rms" in self.config.detection_mode:
            is_speech = is_speech or self._detect_rms(audio_chunk)

        if "vad" in self.config.detection_mode and self._vad:
            is_speech = is_speech or self._detect_vad(audio_chunk, sample_rate)

        # Track consecutive speech frames
        if is_speech:
            self.consecutive_speech_frames += 1
        else:
            self.consecutive_speech_frames = 0

        # Calculate required frames for min speech duration
        # Assume 100ms chunks (typical)
        chunk_duration_ms = (len(audio_chunk) / 2) / sample_rate * 1000
        required_frames = max(1, int(self.config.min_speech_duration_ms / chunk_duration_ms))

        # Trigger barge-in if enough consecutive speech detected
        should_barge_in = self.consecutive_speech_frames >= required_frames

        if should_barge_in:
            logger.info(f"Barge-in triggered (consecutive_frames={self.consecutive_speech_frames})")

        return should_barge_in

    def _detect_rms(self, audio_chunk: bytes) -> bool:
        """Detect speech using RMS energy threshold.

        Args:
            audio_chunk: Raw audio data (PCM s16le)

        Returns:
            True if RMS exceeds threshold
        """
        try:
            # Convert bytes to numpy array (s16le)
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16)

            # Calculate RMS (root mean square)
            rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2)) / 32768.0

            # Check threshold
            is_speech = rms > self.config.vad_energy_threshold

            logger.debug(f"RMS detection: {rms:.4f} (threshold={self.config.vad_energy_threshold}, "
                        f"is_speech={is_speech})")

            return is_speech

        except Exception as e:
            logger.error(f"RMS detection error: {e}")
            return False

    def _detect_vad(self, audio_chunk: bytes, sample_rate: int) -> bool:
        """Detect speech using WebRTC VAD.

        Args:
            audio_chunk: Raw audio data (PCM s16le)
            sample_rate: Audio sample rate (must be 8000, 16000, 32000, or 48000)

        Returns:
            True if VAD detects speech
        """
        if not self._vad:
            return False

        try:
            # WebRTC VAD requires specific chunk sizes (10, 20, or 30 ms)
            # and sample rates (8000, 16000, 32000, 48000)

            # Validate sample rate
            if sample_rate not in (8000, 16000, 32000, 48000):
                logger.warning(f"Invalid sample rate for VAD: {sample_rate}")
                return False

            # Check chunk size (must be 10, 20, or 30 ms)
            chunk_duration_ms = (len(audio_chunk) / 2) / sample_rate * 1000
            if chunk_duration_ms not in (10, 20, 30):
                # Resample or skip VAD for this chunk
                logger.debug(f"Chunk duration {chunk_duration_ms}ms not compatible with VAD")
                return False

            # Run VAD
            is_speech = self._vad.is_speech(audio_chunk, sample_rate)

            logger.debug(f"VAD detection: is_speech={is_speech}")

            return is_speech

        except Exception as e:
            logger.error(f"VAD detection error: {e}")
            return False


class BargeInHandler:
    """Handles barge-in execution (TTS cancellation, control signals)."""

    def __init__(self):
        """Initialize barge-in handler."""
        self.barge_in_count = 0

    async def execute_barge_in(
        self,
        session_id: str,
        tts_request_id: str,
        tts_provider,
        transport,
        audit_logger
    ):
        """Execute barge-in: cancel TTS + send stop playback control.

        Args:
            session_id: Voice session ID
            tts_request_id: TTS request ID to cancel
            tts_provider: TTS provider instance
            transport: Transport provider instance (WebSocket, etc.)
            audit_logger: Audit logger instance
        """
        logger.info(f"Executing barge-in (session={session_id}, tts_request={tts_request_id})")

        # 1. Cancel TTS synthesis
        cancelled = await tts_provider.cancel(tts_request_id)
        if cancelled:
            logger.info(f"TTS cancelled successfully: {tts_request_id}")
        else:
            logger.warning(f"TTS cancel failed (request not found): {tts_request_id}")

        # 2. Send stop playback control to client
        await transport.send_control(
            session_id=session_id,
            control_type="stop_playback",
            payload={"reason": "barge_in", "tts_request_id": tts_request_id}
        )

        # 3. Log audit event
        audit_logger.log_event(
            event_type="BARGE_IN_EXECUTED",
            session_id=session_id,
            metadata={
                "tts_request_id": tts_request_id,
                "barge_in_count": self.barge_in_count
            }
        )

        self.barge_in_count += 1
        logger.info(f"Barge-in executed (total_count={self.barge_in_count})")


# Utility function to create default config
def create_default_barge_in_config() -> BargeInConfig:
    """Create default barge-in configuration.

    Returns:
        Default BargeInConfig instance
    """
    return BargeInConfig(
        enabled=True,
        vad_energy_threshold=0.03,
        detection_mode="rms_or_vad",
        cancel_delay_ms=100,
        min_speech_duration_ms=200
    )
