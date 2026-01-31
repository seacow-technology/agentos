"""
Demo script for AgentOS Voice STT integration.

This script demonstrates how to use the WhisperLocalSTT and VADDetector
in a practical scenario.

Prerequisites:
    pip install faster-whisper>=1.0.0 webrtcvad>=2.0.10 numpy>=1.24.0

Usage:
    python examples/voice_stt_demo.py
"""

import asyncio
import logging
import sys
from pathlib import Path

import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def demo_basic_stt():
    """Demonstrate basic STT usage."""
    logger.info("=" * 60)
    logger.info("Demo 1: Basic STT Usage")
    logger.info("=" * 60)

    from agentos.core.communication.voice.stt import WhisperLocalSTT

    # Create STT instance
    stt = WhisperLocalSTT(model_name="base", device="cpu", language=None)

    # Generate 2 seconds of silence
    logger.info("Generating 2 seconds of silence...")
    audio = np.zeros(32000, dtype=np.int16)  # 2 seconds at 16kHz
    audio_bytes = audio.tobytes()

    # Transcribe
    logger.info("Transcribing audio...")
    result = await stt.transcribe_audio(audio_bytes, sample_rate=16000)
    logger.info(f"Result: '{result}' (empty is expected for silence)")


def demo_basic_vad():
    """Demonstrate basic VAD usage."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("Demo 2: Basic VAD Usage")
    logger.info("=" * 60)

    from agentos.core.communication.voice.stt import VADDetector

    # Create VAD instance
    vad = VADDetector(aggressiveness=2)

    # Generate 20ms silence frame
    sample_rate = 16000
    frame_duration_ms = 20
    samples_per_frame = int(sample_rate * frame_duration_ms / 1000)

    silence_frame = np.zeros(samples_per_frame, dtype=np.int16)
    silence_bytes = silence_frame.tobytes()

    # Test speech detection
    logger.info("Testing speech detection on silence...")
    is_speech = vad.is_speech(silence_bytes, sample_rate=sample_rate)
    logger.info(f"Is speech: {is_speech} (False is expected for silence)")

    # Test silence end detection
    logger.info("Testing silence end detection with 30 frames (600ms)...")
    buffer = [silence_bytes] * 30
    silence_end = vad.detect_silence_end(buffer, sample_rate=sample_rate, threshold_ms=500)
    logger.info(f"Silence end detected: {silence_end}")


async def demo_voice_service():
    """Demonstrate VoiceService usage."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("Demo 3: VoiceService Integration")
    logger.info("=" * 60)

    from agentos.core.communication.voice.service import VoiceService

    # Create service with explicit configuration
    service = VoiceService(
        stt_model="base", stt_device="cpu", stt_language=None, vad_aggressiveness=2
    )

    # Test STT
    logger.info("Testing STT via service...")
    audio = np.zeros(16000, dtype=np.int16)  # 1 second of silence
    result = await service.transcribe_audio(audio.tobytes(), sample_rate=16000)
    logger.info(f"Transcription: '{result}'")

    # Test VAD
    logger.info("Testing VAD via service...")
    silence_frame = np.zeros(320, dtype=np.int16)  # 20ms at 16kHz
    is_speech = service.is_speech(silence_frame.tobytes(), sample_rate=16000)
    logger.info(f"Is speech: {is_speech}")


async def demo_streaming():
    """Demonstrate streaming transcription."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("Demo 4: Streaming Transcription")
    logger.info("=" * 60)

    from agentos.core.communication.voice.stt import WhisperLocalSTT

    stt = WhisperLocalSTT(model_name="base", device="cpu")

    async def audio_stream_generator():
        """Generate audio stream chunks."""
        # Generate 5 chunks of 1 second silence each
        for i in range(5):
            logger.info(f"Generating chunk {i + 1}/5...")
            audio = np.zeros(16000, dtype=np.int16)
            yield audio.tobytes()
            await asyncio.sleep(0.1)  # Simulate streaming delay

    logger.info("Starting streaming transcription...")
    async for text in stt.transcribe_stream(audio_stream_generator()):
        logger.info(f"Streaming result: '{text}'")

    logger.info("Streaming transcription completed")


async def main():
    """Run all demos."""
    logger.info("AgentOS Voice STT Demo")
    logger.info("")

    try:
        # Demo 1: Basic STT
        await demo_basic_stt()

        # Demo 2: Basic VAD
        demo_basic_vad()

        # Demo 3: VoiceService
        await demo_voice_service()

        # Demo 4: Streaming
        await demo_streaming()

        logger.info("")
        logger.info("=" * 60)
        logger.info("✓ All demos completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
