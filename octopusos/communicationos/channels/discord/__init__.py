"""Discord Channel Adapter.

This module provides the Discord channel adapter for CommunicationOS.
"""

# Import client for direct usage
from agentos.communicationos.channels.discord.client import (
    DiscordClient,
    DiscordClientError,
    DiscordRateLimitError,
    DiscordAuthError,
    DiscordInteractionExpiredError,
)

# Import adapter
from agentos.communicationos.channels.discord.adapter import DiscordAdapter

__all__ = [
    "DiscordClient",
    "DiscordClientError",
    "DiscordRateLimitError",
    "DiscordAuthError",
    "DiscordInteractionExpiredError",
    "DiscordAdapter",
]
