"""Channel adapters for CommunicationOS.

This package contains specific channel adapter implementations that integrate
external communication platforms with AgentOS.

Available Adapters:
    - whatsapp_twilio: WhatsApp integration via Twilio's Business API
    - telegram: Telegram Bot API integration
    - slack: Slack integration via Slack Events API
"""

from agentos.communicationos.channels.whatsapp_twilio import (
    WhatsAppTwilioAdapter,
    verify_twilio_signature,
)
from agentos.communicationos.channels.telegram import (
    TelegramAdapter,
    send_message as telegram_send_message,
    set_webhook as telegram_set_webhook,
)
from agentos.communicationos.channels.slack import (
    SlackAdapter,
    post_message as slack_post_message,
    verify_signature as slack_verify_signature,
    auth_test as slack_auth_test,
)

__all__ = [
    "WhatsAppTwilioAdapter",
    "verify_twilio_signature",
    "TelegramAdapter",
    "telegram_send_message",
    "telegram_set_webhook",
    "SlackAdapter",
    "slack_post_message",
    "slack_verify_signature",
    "slack_auth_test",
]
