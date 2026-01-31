"""Text-to-Speech (TTS) providers for voice communication.

This package provides a unified interface for various TTS engines,
supporting streaming audio synthesis for low-latency voice interactions.

Supported Providers:
- OpenAI TTS (tts-1, tts-1-hd)
- ElevenLabs (planned)
- Local TTS engines (planned)
- Mock TTS (testing)
"""

__all__ = ["ITTSProvider", "OpenAITTSProvider", "MockTTSProvider"]
