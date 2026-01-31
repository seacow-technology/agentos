"""
Speech-to-Text (STT) providers for AgentOS voice communication.
"""

from agentos.core.communication.voice.stt.base import ISTTProvider
from agentos.core.communication.voice.stt.whisper_local import WhisperLocalSTT
from agentos.core.communication.voice.stt.vad import VADDetector

__all__ = ["ISTTProvider", "WhisperLocalSTT", "VADDetector"]
