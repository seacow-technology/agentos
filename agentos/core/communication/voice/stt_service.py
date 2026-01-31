"""
Voice communication service for AgentOS.

Integrates STT, TTS, and VAD components with configuration support.
"""

import logging
import os
from typing import Optional

from agentos.core.communication.voice.stt import VADDetector, WhisperLocalSTT

logger = logging.getLogger(__name__)


class VoiceService:
    """
    Voice communication service that integrates STT and VAD.

    Configuration via environment variables:
    - VOICE_STT_MODEL: Whisper model name (default: "base")
    - VOICE_STT_DEVICE: Device for inference (default: "cpu")
    - VOICE_STT_LANGUAGE: Target language code or None for auto-detection (default: None)
    - VOICE_VAD_AGGRESSIVENESS: VAD aggressiveness level 0-3 (default: 2)
    """

    def __init__(
        self,
        stt_model: Optional[str] = None,
        stt_device: Optional[str] = None,
        stt_language: Optional[str] = None,
        vad_aggressiveness: Optional[int] = None,
    ):
        """
        Initialize VoiceService.

        Args:
            stt_model: Whisper model name (overrides env var).
            stt_device: Device for inference (overrides env var).
            stt_language: Target language code (overrides env var).
            vad_aggressiveness: VAD aggressiveness level (overrides env var).
        """
        # Load configuration from environment variables
        self.stt_model = stt_model or os.getenv("VOICE_STT_MODEL", "base")
        self.stt_device = stt_device or os.getenv("VOICE_STT_DEVICE", "cpu")
        self.stt_language = stt_language or os.getenv("VOICE_STT_LANGUAGE")

        # Parse VAD aggressiveness (default: 2)
        vad_agg_str = os.getenv("VOICE_VAD_AGGRESSIVENESS", "2")
        if vad_aggressiveness is not None:
            self.vad_aggressiveness = vad_aggressiveness
        else:
            try:
                self.vad_aggressiveness = int(vad_agg_str)
            except ValueError:
                logger.warning(
                    f"Invalid VOICE_VAD_AGGRESSIVENESS value: {vad_agg_str}, using default 2"
                )
                self.vad_aggressiveness = 2

        # Initialize components (lazy initialization)
        self._stt: Optional[WhisperLocalSTT] = None
        self._vad: Optional[VADDetector] = None

        logger.info(
            f"VoiceService initialized with config: "
            f"stt_model={self.stt_model}, "
            f"stt_device={self.stt_device}, "
            f"stt_language={self.stt_language or 'auto'}, "
            f"vad_aggressiveness={self.vad_aggressiveness}"
        )

    def get_stt(self) -> WhisperLocalSTT:
        """
        Get or create STT provider.

        Returns:
            WhisperLocalSTT instance.
        """
        if self._stt is None:
            self._stt = WhisperLocalSTT(
                model_name=self.stt_model,
                device=self.stt_device,
                language=self.stt_language,
            )
            logger.info("STT provider initialized")

        return self._stt

    def get_vad(self) -> VADDetector:
        """
        Get or create VAD detector.

        Returns:
            VADDetector instance.
        """
        if self._vad is None:
            self._vad = VADDetector(aggressiveness=self.vad_aggressiveness)
            logger.info("VAD detector initialized")

        return self._vad

    async def transcribe_audio(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw audio data in PCM int16 format.
            sample_rate: Audio sample rate in Hz (default: 16000).

        Returns:
            Transcribed text as a string.
        """
        stt = self.get_stt()
        return await stt.transcribe_audio(audio_bytes, sample_rate)

    def is_speech(self, audio_chunk: bytes, sample_rate: int = 16000) -> bool:
        """
        Detect if audio chunk contains speech.

        Args:
            audio_chunk: Raw audio data in PCM int16 format (10, 20, or 30 ms).
            sample_rate: Audio sample rate in Hz (default: 16000).

        Returns:
            True if speech is detected, False otherwise.
        """
        vad = self.get_vad()
        return vad.is_speech(audio_chunk, sample_rate)
