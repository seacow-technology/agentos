"""Slack Channel Module.

This module provides Slack integration for CommunicationOS through the
Slack Events API and Web API.

Exports:
    - SlackAdapter: Channel adapter for Slack
    - post_message: Send message via Slack Web API
    - verify_signature: Verify webhook signature
    - auth_test: Test authentication

Usage:
    from agentos.communicationos.channels.slack import SlackAdapter

    adapter = SlackAdapter(
        channel_id="slack_workspace_001",
        bot_token="xoxb-...",
        signing_secret="...",
        trigger_policy="mention_or_dm"
    )
"""

from agentos.communicationos.channels.slack.adapter import SlackAdapter
from agentos.communicationos.channels.slack.client import (
    post_message,
    verify_signature,
    auth_test,
    get_user_info,
)

__all__ = [
    "SlackAdapter",
    "post_message",
    "verify_signature",
    "auth_test",
    "get_user_info",
]
