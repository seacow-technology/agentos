"""Voice provider implementations.

This module contains provider-specific implementations for different
voice communication backends (local WebSocket, Twilio, etc.).

Providers are organized into two layers:
1. High-level providers (IVoiceProvider): Session management and configuration
2. Transport providers (IVoiceTransportProvider): Audio streaming and transcoding
"""

from agentos.core.communication.voice.providers.base import (
    IVoiceProvider,
    IVoiceTransportProvider,
)
from agentos.core.communication.voice.providers.local import LocalProvider
from agentos.core.communication.voice.providers.twilio import TwilioProvider
from agentos.core.communication.voice.providers.twilio_streams import (
    TwilioStreamsTransportProvider,
)

__all__ = [
    # High-level provider interfaces
    "IVoiceProvider",
    "IVoiceTransportProvider",
    # High-level provider implementations
    "LocalProvider",
    "TwilioProvider",
    # Transport layer implementations
    "TwilioStreamsTransportProvider",
]
