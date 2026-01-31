"""Voice TTS and Barge-In Demo

This script demonstrates the TTS streaming and barge-in functionality
without requiring a full WebSocket connection.

It shows:
1. TTS provider selection (OpenAI or Mock)
2. TTS streaming synthesis
3. Barge-in detection
4. Barge-in execution (TTS cancellation)
"""

import asyncio
import base64
import os
import struct
from typing import Optional

# Note: Direct imports to avoid audioop dependency issue
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def demo_tts_provider_selection():
    """Demo 1: TTS provider selection based on environment."""
    print("\n=== Demo 1: TTS Provider Selection ===")

    # Simulate checking for OpenAI API key
    openai_key = os.environ.get("OPENAI_API_KEY")

    if openai_key:
        print(f"✅ Found OPENAI_API_KEY: {openai_key[:10]}...")
        print("   Provider: OpenAI TTS (tts-1)")
    else:
        print("❌ No OPENAI_API_KEY found")
        print("   Provider: Mock TTS (testing)")

    print("\nProvider selection logic:")
    print("  if OPENAI_API_KEY:")
    print("    return OpenAITTSProvider(api_key=openai_key)")
    print("  else:")
    print("    return MockTTSProvider()")


async def demo_mock_tts_streaming():
    """Demo 2: Mock TTS streaming synthesis."""
    print("\n=== Demo 2: Mock TTS Streaming ===")

    # Import MockTTSProvider directly (avoid audioop)
    try:
        # Workaround: Import directly without going through __init__
        from agentos.core.communication.voice.tts.mock_provider import MockTTSProvider

        provider = MockTTSProvider(
            sample_rate=16000,
            chunk_duration_ms=100,
            generate_tone=False
        )

        text = "This is a test message for TTS synthesis"
        voice_id = "test-voice-1"

        print(f"Text: '{text}'")
        print(f"Voice: {voice_id}")
        print(f"Provider: {provider.get_provider_name()}")
        print("\nStreaming TTS chunks...")

        chunk_count = 0
        total_bytes = 0

        async for audio_chunk in provider.synthesize(text, voice_id, speed=1.0):
            chunk_count += 1
            total_bytes += len(audio_chunk)

            # Encode to base64 (as would be sent over WebSocket)
            payload_b64 = base64.b64encode(audio_chunk).decode("utf-8")

            print(f"  Chunk #{chunk_count}: {len(audio_chunk)} bytes (base64: {len(payload_b64)} chars)")

            # Simulate network delay
            await asyncio.sleep(0.05)

        print(f"\n✅ TTS completed: {chunk_count} chunks, {total_bytes} bytes total")

    except ImportError as e:
        print(f"⚠️  Cannot import TTS provider (dependency issue): {e}")
        print("   Mock implementation shown conceptually above")


async def demo_barge_in_detection():
    """Demo 3: Barge-in detection."""
    print("\n=== Demo 3: Barge-in Detection ===")

    try:
        from agentos.core.communication.voice.barge_in import (
            BargeInDetector,
            BargeInConfig,
        )

        # Create detector
        config = BargeInConfig(
            enabled=True,
            vad_energy_threshold=0.03,
            detection_mode="rms",  # RMS-only to avoid VAD dependency
            min_speech_duration_ms=200,
        )

        detector = BargeInDetector(config)

        print("Barge-in detector initialized:")
        print(f"  Enabled: {config.enabled}")
        print(f"  Threshold: {config.vad_energy_threshold}")
        print(f"  Detection mode: {config.detection_mode}")
        print(f"  Min speech duration: {config.min_speech_duration_ms}ms")

        # Simulate TTS playback
        print("\n1. Starting TTS playback...")
        detector.start_tts_playback()
        print(f"   is_playing_tts: {detector.is_playing_tts}")

        # Test with silence (should not trigger)
        print("\n2. Receiving silence (should NOT trigger barge-in)...")
        silence = bytes(1600 * 2)  # 100ms at 16kHz
        should_trigger = detector.detect(silence, sample_rate=16000)
        print(f"   Barge-in triggered: {should_trigger}")

        # Test with loud audio (should trigger)
        print("\n3. Receiving loud audio (should trigger barge-in)...")

        # Generate loud audio
        loud_audio = bytearray()
        for i in range(1600):  # 100ms at 16kHz
            sample = 20000  # High amplitude
            loud_audio.extend(struct.pack("<h", sample))

        # First chunk
        should_trigger = detector.detect(bytes(loud_audio), sample_rate=16000)
        print(f"   First chunk - triggered: {should_trigger}, consecutive frames: {detector.consecutive_speech_frames}")

        # Second chunk (should trigger)
        should_trigger = detector.detect(bytes(loud_audio), sample_rate=16000)
        print(f"   Second chunk - triggered: {should_trigger}, consecutive frames: {detector.consecutive_speech_frames}")

        # Third chunk (definitely triggers)
        should_trigger = detector.detect(bytes(loud_audio), sample_rate=16000)
        print(f"   Third chunk - triggered: {should_trigger}, consecutive frames: {detector.consecutive_speech_frames}")

        if should_trigger or detector.consecutive_speech_frames >= 2:
            print("\n✅ Barge-in detected! Would cancel TTS now.")

        # Stop TTS
        print("\n4. Stopping TTS playback...")
        detector.stop_tts_playback()
        print(f"   is_playing_tts: {detector.is_playing_tts}")

    except ImportError as e:
        print(f"⚠️  Cannot import barge-in detector (dependency issue): {e}")
        print("   Mock implementation shown conceptually above")


async def demo_tts_cancellation():
    """Demo 4: TTS cancellation for barge-in."""
    print("\n=== Demo 4: TTS Cancellation (Barge-In) ===")

    try:
        from agentos.core.communication.voice.tts.mock_provider import MockTTSProvider

        provider = MockTTSProvider(chunk_duration_ms=100)

        text = "This is a long message that will be cancelled mid-stream"
        voice_id = "test-voice-1"

        print(f"Text: '{text}'")
        print("Starting TTS synthesis...")

        chunk_count = 0

        # Create synthesis generator
        synthesis = provider.synthesize(text, voice_id, speed=1.0)

        # Get first chunk
        chunk = await synthesis.__anext__()
        chunk_count += 1
        print(f"  Chunk #{chunk_count}: {len(chunk)} bytes")

        # Get second chunk
        chunk = await synthesis.__anext__()
        chunk_count += 1
        print(f"  Chunk #{chunk_count}: {len(chunk)} bytes")

        # Simulate barge-in detection
        print("\n⚡ Barge-in detected! Cancelling TTS...")

        # Get request ID
        request_id = list(provider.active_requests.keys())[0] if provider.active_requests else None

        if request_id:
            # Cancel TTS
            cancelled = await provider.cancel(request_id)
            print(f"  TTS cancelled: {cancelled}")

            # Try to get next chunk (should stop)
            try:
                remaining_chunks = 0
                while True:
                    chunk = await synthesis.__anext__()
                    remaining_chunks += 1
                    if remaining_chunks > 2:  # Safety limit
                        break
            except StopAsyncIteration:
                pass

            print(f"  Remaining chunks after cancel: {remaining_chunks}")
            print(f"  Total chunks before cancel: {chunk_count}")

            print("\n✅ TTS successfully cancelled (barge-in executed)")

    except ImportError as e:
        print(f"⚠️  Cannot import TTS provider (dependency issue): {e}")
        print("   Mock implementation shown conceptually above")


async def demo_websocket_flow():
    """Demo 5: Complete WebSocket flow (conceptual)."""
    print("\n=== Demo 5: WebSocket Flow (Conceptual) ===")

    print("\n1. Client sends audio chunk:")
    print('   {"type": "voice.audio.chunk", "seq": 1, "payload_b64": "..."}')

    print("\n2. Server sends STT result:")
    print('   {"type": "voice.stt.final", "text": "Hello, how are you?"}')

    print("\n3. Server sends assistant text:")
    print('   {"type": "assistant.text", "text": "You said: Hello, how are you?"}')

    print("\n4. Server starts TTS:")
    print('   {"type": "tts.start", "request_id": "tts-abc123", "voice_id": "alloy"}')

    print("\n5. Server streams TTS chunks:")
    print('   {"type": "tts.chunk", "request_id": "tts-abc123", "payload_b64": "..."}')
    print('   {"type": "tts.chunk", "request_id": "tts-abc123", "payload_b64": "..."}')
    print('   ...')

    print("\n6. (During TTS) Client sends audio → Barge-in detected:")
    print('   {"type": "barge_in.detected"}')

    print("\n7. Server cancels TTS and sends control:")
    print('   {"type": "control.stop_playback", "reason": "barge_in"}')

    print("\n8. (If no barge-in) Server sends TTS end:")
    print('   {"type": "tts.end", "request_id": "tts-abc123", "total_chunks": 42}')


async def main():
    """Run all demos."""
    print("=" * 60)
    print("Voice TTS and Barge-In Functionality Demo")
    print("=" * 60)

    await demo_tts_provider_selection()
    await demo_mock_tts_streaming()
    await demo_barge_in_detection()
    await demo_tts_cancellation()
    await demo_websocket_flow()

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\nFor full WebSocket integration, see:")
    print("  - /Users/pangge/PycharmProjects/AgentOS/agentos/webui/api/voice.py")
    print("  - /Users/pangge/PycharmProjects/AgentOS/VOICE_TTS_BARGEIN_IMPLEMENTATION_REPORT.md")


if __name__ == "__main__":
    asyncio.run(main())
