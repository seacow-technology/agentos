"""SMS Channel Package (v2: Bidirectional).

This package provides bidirectional SMS communication through SMS providers like Twilio.

Version 2 Characteristics:
    - Bidirectional (send + receive via webhook)
    - Webhook signature verification (HMAC-SHA1)
    - Idempotent message deduplication (MessageSid)
    - 1:1 conversation tracking
    - Async reply processing via MessageBus

Components:
    - manifest.json: Channel configuration and setup wizard
    - KEY_MAPPING.md: Phone number and message ID mapping rules
    - adapter.py: SMS adapter with webhook support
    - README.md: Channel documentation

Provider Support:
    - Twilio: Full support (send + receive)
    - AWS SNS: Planned for future
    - Custom providers: Implement ISmsProvider protocol

Security:
    - Path token in webhook URL (prevents URL guessing)
    - Twilio signature verification (HMAC-SHA1, mandatory)
    - Constant-time comparison (prevents timing attacks)
"""

from agentos.communicationos.channels.sms.adapter import SmsAdapter

__all__ = ["SmsAdapter"]

__version__ = "2.0.0"
__variant__ = "bidirectional"
