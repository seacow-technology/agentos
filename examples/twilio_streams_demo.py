"""Demonstration of Twilio Media Streams transport provider.

This example shows how to use the TwilioStreamsTransportProvider for
bidirectional audio communication with Twilio Media Streams.

The provider handles:
1. Connection to Twilio Media Streams (call_sid, stream_sid)
2. μ-law ↔ PCM audio transcoding
3. Sending PCM audio (transcoded to μ-law for Twilio)
4. Receiving μ-law audio (transcoded to PCM for processing)
5. Control commands (mark, clear)
6. Session metadata and statistics

Usage:
    python examples/twilio_streams_demo.py
"""

import asyncio
import numpy as np
from agentos.core.communication.voice.providers.twilio_streams import (
    TwilioStreamsTransportProvider,
)


async def demo_basic_connection():
    """Demo 1: Basic connection and disconnection."""
    print("\n=== Demo 1: Basic Connection ===")

    provider = TwilioStreamsTransportProvider()

    # Connect to Twilio stream
    connection_params = {
        "call_sid": "CA1234567890abcdef1234567890abcdef",
        "stream_sid": "MZ9876543210fedcba9876543210fedcba",
        "from_number": "+14155551234",
        "to_number": "+14155559876",
        "call_status": "in-progress",
    }

    print(f"Connecting to Twilio stream...")
    metadata = await provider.connect(connection_params)
    print(f"Connected: {metadata}")
    print(f"Is connected: {provider.is_connected()}")

    # Disconnect
    print(f"Disconnecting...")
    await provider.disconnect()
    print(f"Is connected: {provider.is_connected()}")


async def demo_audio_transcoding():
    """Demo 2: Audio transcoding (PCM ↔ μ-law)."""
    print("\n=== Demo 2: Audio Transcoding ===")

    provider = TwilioStreamsTransportProvider()

    # Generate sample PCM audio (sine wave at 440Hz, 16kHz, 20ms)
    duration_ms = 20
    sample_rate = 16000
    frequency = 440  # A4 note
    num_samples = int(sample_rate * duration_ms / 1000)

    t = np.linspace(0, duration_ms / 1000, num_samples)
    sine_wave = np.sin(2 * np.pi * frequency * t)
    pcm_audio = (sine_wave * 32767 / 2).astype(np.int16)  # Convert to int16
    pcm_bytes = pcm_audio.tobytes()

    print(f"Generated PCM audio: {len(pcm_bytes)} bytes ({num_samples} samples)")

    # Transcode PCM → μ-law
    mulaw_bytes = provider._transcode_pcm_to_mulaw(pcm_bytes)
    print(f"Transcoded to μ-law: {len(mulaw_bytes)} bytes")
    print(f"Compression ratio: {len(pcm_bytes) / len(mulaw_bytes):.2f}x")

    # Transcode μ-law → PCM (roundtrip)
    pcm_roundtrip = provider._transcode_mulaw_to_pcm(mulaw_bytes)
    print(f"Transcoded back to PCM: {len(pcm_roundtrip)} bytes")

    # Compare
    print(f"Original PCM size: {len(pcm_bytes)} bytes")
    print(f"Roundtrip PCM size: {len(pcm_roundtrip)} bytes")
    print(f"Sizes match: {len(pcm_bytes) == len(pcm_roundtrip)}")


async def demo_audio_transmission():
    """Demo 3: Sending and receiving audio."""
    print("\n=== Demo 3: Audio Transmission ===")

    provider = TwilioStreamsTransportProvider()

    # Connect
    connection_params = {
        "call_sid": "CA1234567890abcdef1234567890abcdef",
        "stream_sid": "MZ9876543210fedcba9876543210fedcba",
    }
    await provider.connect(connection_params)

    # Generate and send audio chunks
    print("Sending audio chunks...")
    for i in range(5):
        # Generate PCM audio (20ms chunk)
        pcm_data = np.zeros(640, dtype=np.int16)  # Silence
        await provider.send_audio_chunk(pcm_data.tobytes())
        print(f"  Sent chunk {i + 1}/5")

    # Check statistics
    metadata = provider.get_transport_metadata()
    print(f"\nStatistics:")
    print(f"  Chunks sent: {metadata['chunks_sent']}")
    print(f"  Bytes sent: {metadata['bytes_sent']}")
    print(f"  Transcode errors: {metadata['transcode_errors']}")

    # Try receiving (MVP returns None)
    print("\nReceiving audio...")
    received = await provider.receive_audio_chunk()
    print(f"  Received: {received}")  # Will be None in MVP

    await provider.disconnect()


async def demo_control_commands():
    """Demo 4: Sending control commands."""
    print("\n=== Demo 4: Control Commands ===")

    provider = TwilioStreamsTransportProvider()

    # Connect
    connection_params = {
        "call_sid": "CA1234567890abcdef1234567890abcdef",
        "stream_sid": "MZ9876543210fedcba9876543210fedcba",
    }
    await provider.connect(connection_params)

    # Send mark events (for synchronization)
    print("Sending mark events...")
    await provider.send_control("mark", {"name": "segment_start"})
    print("  Sent mark: segment_start")

    await provider.send_control("mark", {"name": "segment_end"})
    print("  Sent mark: segment_end")

    # Send clear command
    print("Sending clear command...")
    await provider.send_control("clear")
    print("  Sent clear")

    # Check statistics
    metadata = provider.get_transport_metadata()
    print(f"\nMarks sent: {metadata['marks_sent']}")

    await provider.disconnect()


async def demo_twilio_events():
    """Demo 5: Handling Twilio events."""
    print("\n=== Demo 5: Twilio Event Handling ===")

    provider = TwilioStreamsTransportProvider()

    # Simulate Twilio events
    print("Processing Twilio events...")

    # Start event
    start_event = {
        "event": "start",
        "start": {
            "callSid": "CA1234567890",
            "streamSid": "MZ9876543210",
            "customParameters": {},
        }
    }
    provider.handle_twilio_event(start_event)
    print("  Handled start event")

    # Media event
    import base64
    mulaw_data = b'\xff' * 160  # 20ms of silence
    media_event = {
        "event": "media",
        "media": {
            "payload": base64.b64encode(mulaw_data).decode("utf-8"),
            "timestamp": "1234567890",
        }
    }
    provider.handle_twilio_event(media_event)
    print("  Handled media event")

    # Mark event
    mark_event = {
        "event": "mark",
        "mark": {
            "name": "playback_complete",
        }
    }
    provider.handle_twilio_event(mark_event)
    print("  Handled mark event")

    # Stop event
    stop_event = {
        "event": "stop",
        "stop": {
            "callSid": "CA1234567890",
            "streamSid": "MZ9876543210",
        }
    }
    provider.handle_twilio_event(stop_event)
    print("  Handled stop event")


async def demo_error_handling():
    """Demo 6: Error handling."""
    print("\n=== Demo 6: Error Handling ===")

    provider = TwilioStreamsTransportProvider()

    # Try operations before connecting
    print("Testing operations before connection...")
    try:
        await provider.send_audio_chunk(b'\x00' * 640)
    except RuntimeError as e:
        print(f"  Expected error: {e}")

    try:
        await provider.receive_audio_chunk()
    except RuntimeError as e:
        print(f"  Expected error: {e}")

    try:
        await provider.send_control("mark", {"name": "test"})
    except RuntimeError as e:
        print(f"  Expected error: {e}")

    # Test invalid connection parameters
    print("\nTesting invalid connection parameters...")
    try:
        await provider.connect({"call_sid": "INVALID"})
    except ValueError as e:
        print(f"  Expected error: {e}")

    # Test invalid audio data
    print("\nTesting invalid audio data...")
    connection_params = {
        "call_sid": "CA1234567890abcdef1234567890abcdef",
        "stream_sid": "MZ9876543210fedcba9876543210fedcba",
    }
    await provider.connect(connection_params)

    try:
        await provider.send_audio_chunk(b'')
    except ValueError as e:
        print(f"  Expected error: {e}")

    await provider.disconnect()


async def demo_full_session():
    """Demo 7: Full session lifecycle with realistic audio."""
    print("\n=== Demo 7: Full Session Lifecycle ===")

    provider = TwilioStreamsTransportProvider()

    # 1. Connect
    print("1. Connecting to Twilio stream...")
    connection_params = {
        "call_sid": "CA1234567890abcdef1234567890abcdef",
        "stream_sid": "MZ9876543210fedcba9876543210fedcba",
        "from_number": "+14155551234",
        "to_number": "+14155559876",
        "call_status": "in-progress",
    }
    metadata = await provider.connect(connection_params)
    print(f"   Connected: call_sid={metadata['call_sid']}")

    # 2. Send greeting audio
    print("\n2. Sending greeting audio...")
    for i in range(10):  # 10 chunks = 200ms of audio
        # Generate PCM audio with varying amplitude
        t = np.linspace(0, 0.02, 640)  # 20ms at 16kHz
        frequency = 440 + i * 50  # Increasing pitch
        sine_wave = np.sin(2 * np.pi * frequency * t)
        pcm_audio = (sine_wave * 16384).astype(np.int16)
        await provider.send_audio_chunk(pcm_audio.tobytes())

    print(f"   Sent 10 audio chunks")

    # 3. Send synchronization mark
    print("\n3. Sending synchronization mark...")
    await provider.send_control("mark", {"name": "greeting_complete"})

    # 4. Simulate receiving audio
    print("\n4. Receiving audio...")
    for i in range(5):
        received = await provider.receive_audio_chunk()
        # MVP: will be None
        if received is None:
            print(f"   No audio available (chunk {i + 1}/5)")

    # 5. Get session statistics
    print("\n5. Session statistics:")
    metadata = provider.get_transport_metadata()
    print(f"   Chunks sent: {metadata['chunks_sent']}")
    print(f"   Bytes sent: {metadata['bytes_sent']}")
    print(f"   Chunks received: {metadata['chunks_received']}")
    print(f"   Bytes received: {metadata['bytes_received']}")
    print(f"   Marks sent: {metadata['marks_sent']}")
    print(f"   Transcode errors: {metadata['transcode_errors']}")

    # 6. Disconnect
    print("\n6. Disconnecting...")
    await provider.disconnect()
    print(f"   Disconnected")


async def main():
    """Run all demos."""
    print("=" * 60)
    print("Twilio Media Streams Transport Provider Demo")
    print("=" * 60)

    demos = [
        ("Basic Connection", demo_basic_connection),
        ("Audio Transcoding", demo_audio_transcoding),
        ("Audio Transmission", demo_audio_transmission),
        ("Control Commands", demo_control_commands),
        ("Twilio Events", demo_twilio_events),
        ("Error Handling", demo_error_handling),
        ("Full Session", demo_full_session),
    ]

    for name, demo_func in demos:
        try:
            await demo_func()
        except Exception as e:
            print(f"\n[ERROR in {name}] {e}")

    print("\n" + "=" * 60)
    print("Demo completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
