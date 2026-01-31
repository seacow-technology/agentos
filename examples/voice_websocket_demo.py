#!/usr/bin/env python3
"""
Voice WebSocket Client Demo

This script demonstrates how to use the Voice WebSocket API:
1. Create a voice session via REST API
2. Connect to WebSocket
3. Send audio chunks
4. Receive STT results and assistant responses
5. Stop the session

Usage:
    # Start the AgentOS WebUI server first:
    uvicorn agentos.webui.app:app --reload

    # Then run this demo:
    python3 examples/voice_websocket_demo.py

Requirements:
    pip install websockets requests
"""

import asyncio
import json
import base64
import struct
import requests
import websockets
from datetime import datetime


# Configuration
API_BASE_URL = "http://localhost:8000"
WS_BASE_URL = "ws://localhost:8000"


def create_voice_session(project_id: str = "demo-project") -> dict:
    """Create a voice session via REST API"""

    url = f"{API_BASE_URL}/api/voice/sessions"
    payload = {
        "project_id": project_id,
        "provider": "local",
        "stt_provider": "whisper_local"
    }

    print(f"Creating voice session...")
    response = requests.post(url, json=payload)
    response.raise_for_status()

    data = response.json()
    if not data.get("ok"):
        raise Exception(f"Failed to create session: {data}")

    session_data = data["data"]
    print(f"✓ Session created: {session_data['session_id']}")
    print(f"  - WebSocket URL: {session_data['ws_url']}")

    return session_data


def stop_voice_session(session_id: str):
    """Stop a voice session via REST API"""

    url = f"{API_BASE_URL}/api/voice/sessions/{session_id}/stop"

    print(f"Stopping session {session_id}...")
    response = requests.post(url)
    response.raise_for_status()

    data = response.json()
    if not data.get("ok"):
        raise Exception(f"Failed to stop session: {data}")

    print(f"✓ Session stopped")


def generate_mock_audio(duration_seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generate mock PCM audio data (sine wave)

    Args:
        duration_seconds: Duration of audio in seconds
        sample_rate: Sample rate in Hz

    Returns:
        PCM audio bytes (16-bit signed little-endian)
    """
    import math

    num_samples = int(duration_seconds * sample_rate)
    audio_data = bytearray()

    # Generate a simple sine wave (440 Hz - A4 note)
    frequency = 440.0
    for i in range(num_samples):
        # Generate sine wave sample (-1.0 to 1.0)
        t = i / sample_rate
        sample = math.sin(2.0 * math.pi * frequency * t)

        # Convert to 16-bit signed integer (-32768 to 32767)
        sample_int = int(sample * 32767)

        # Pack as little-endian 16-bit signed integer
        audio_data.extend(struct.pack('<h', sample_int))

    return bytes(audio_data)


async def test_voice_websocket(session_id: str):
    """Test voice WebSocket connection

    This demonstrates:
    1. Connecting to WebSocket
    2. Receiving session.ready event
    3. Sending audio chunks
    4. Receiving STT results
    5. Receiving assistant responses
    """

    ws_url = f"{WS_BASE_URL}/api/voice/sessions/{session_id}/events"

    print(f"\nConnecting to WebSocket: {ws_url}")

    async with websockets.connect(ws_url) as websocket:
        print(f"✓ WebSocket connected")

        # Wait for session.ready event
        print("\nWaiting for session.ready event...")
        ready_event = await websocket.recv()
        ready_data = json.loads(ready_event)
        print(f"✓ Received: {ready_data['type']}")
        print(f"  {json.dumps(ready_data, indent=2)}")

        # Generate mock audio (3 seconds)
        print("\nGenerating mock audio (3 seconds at 16kHz)...")
        full_audio = generate_mock_audio(duration_seconds=3.0, sample_rate=16000)
        print(f"✓ Generated {len(full_audio)} bytes of audio")

        # Split into chunks (simulate streaming)
        chunk_size = 8000  # ~0.25 seconds of 16kHz mono PCM
        chunks = [full_audio[i:i+chunk_size] for i in range(0, len(full_audio), chunk_size)]

        print(f"\nSending {len(chunks)} audio chunks...")
        for seq, chunk in enumerate(chunks):
            # Encode chunk to base64
            chunk_b64 = base64.b64encode(chunk).decode('utf-8')

            # Create audio chunk event
            event = {
                "type": "voice.audio.chunk",
                "session_id": session_id,
                "seq": seq,
                "format": {
                    "codec": "pcm_s16le",
                    "sample_rate": 16000,
                    "channels": 1
                },
                "payload_b64": chunk_b64,
                "t_ms": int(datetime.now().timestamp() * 1000)
            }

            # Send chunk
            await websocket.send(json.dumps(event))
            print(f"  ✓ Sent chunk #{seq} ({len(chunk)} bytes)")

            # Small delay to simulate real-time streaming
            await asyncio.sleep(0.1)

        # Send audio end event
        print("\nSending audio.end event...")
        end_event = {
            "type": "voice.audio.end",
            "session_id": session_id,
            "t_ms": int(datetime.now().timestamp() * 1000)
        }
        await websocket.send(json.dumps(end_event))
        print(f"✓ Sent audio.end")

        # Wait for STT and assistant response
        print("\nWaiting for responses...")
        timeout_seconds = 5
        start_time = asyncio.get_event_loop().time()

        while True:
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                print(f"⚠ Timeout after {timeout_seconds}s")
                break

            try:
                # Wait for message with timeout
                response = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=1.0
                )
                response_data = json.loads(response)
                event_type = response_data.get("type")

                print(f"\n✓ Received: {event_type}")
                print(f"  {json.dumps(response_data, indent=2)}")

                # Stop after receiving assistant response
                if event_type == "voice.assistant.text":
                    break

            except asyncio.TimeoutError:
                # No message received, continue waiting
                continue
            except websockets.exceptions.ConnectionClosed:
                print("✗ WebSocket connection closed")
                break

        print("\n✓ WebSocket test completed")


async def main():
    """Main demo flow"""

    print("=" * 60)
    print("Voice WebSocket Demo - AgentOS VoiceOS")
    print("=" * 60)

    try:
        # Step 1: Create session
        session_data = create_voice_session(project_id="demo-project-websocket")
        session_id = session_data["session_id"]

        # Step 2: Test WebSocket
        await test_voice_websocket(session_id)

        # Step 3: Stop session
        print("\n" + "=" * 60)
        stop_voice_session(session_id)

        print("\n" + "=" * 60)
        print("DEMO COMPLETED SUCCESSFULLY ✓")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to API server")
        print("  Make sure the server is running:")
        print("  uvicorn agentos.webui.app:app --reload")
        exit(1)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
