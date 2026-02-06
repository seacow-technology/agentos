"""Voice communication module for AgentOS.

This module provides a complete voice communication infrastructure including:
- Session management for real-time voice interactions
- Policy-based security and governance
- Multiple provider support (local WebSocket, Twilio PSTN)
- Speech-to-text integration
- Comprehensive audit logging

Main exports:
- VoiceService: Main service for session management
- VoiceSession: Session model
- VoicePolicy: Policy engine
- VoiceProvider/STTProvider: Provider enums
"""

from agentos.core.communication.voice.models import (
    VoiceSession,
    VoiceSessionState,
    VoiceProvider,
    STTProvider,
    VoiceEvent,
    VoiceEventType,
)
from agentos.core.communication.voice.policy import VoicePolicy
from agentos.core.communication.voice.service import VoiceService

__all__ = [
    # Service
    "VoiceService",
    # Models
    "VoiceSession",
    "VoiceSessionState",
    "VoiceProvider",
    "STTProvider",
    "VoiceEvent",
    "VoiceEventType",
    # Policy
    "VoicePolicy",
]
