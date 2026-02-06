"""Telegram channel adapter package.

This package provides Telegram Bot API integration for CommunicationOS.

Components:
    - adapter: TelegramAdapter class for webhook parsing and message handling
    - client: Telegram Bot API HTTP client for sending messages
"""

from agentos.communicationos.channels.telegram.adapter import TelegramAdapter
from agentos.communicationos.channels.telegram.client import (
    send_message,
    set_webhook,
    get_webhook_info,
    delete_webhook,
)

__all__ = [
    "TelegramAdapter",
    "send_message",
    "set_webhook",
    "get_webhook_info",
    "delete_webhook",
]
