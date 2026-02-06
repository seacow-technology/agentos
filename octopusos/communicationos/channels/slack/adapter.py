"""Slack Channel Adapter.

This module implements a ChannelAdapter for Slack via Slack Events API.
It handles webhook parsing, message sending, signature verification, and URL verification.

Architecture:
    - parse_event(): Converts Slack event to InboundMessage
    - send_message(): Sends OutboundMessage via Slack Web API
    - verify_signature(): Validates X-Slack-Signature header using HMAC SHA256
    - handle_url_verification(): Handles Slack URL verification challenge
    - Bot loop protection: Ignores messages with bot_id or subtype=bot_message
    - Thread handling: Preserves thread_ts for threaded conversations
    - Idempotency: Tracks event IDs to prevent duplicate processing

Key Slack Complexities:
    - Webhook MUST respond within 3 seconds (use async processing)
    - Idempotency: Slack retries failed events (check X-Slack-Retry-Num)
    - Threads: conversation_key includes channel + thread_ts
    - Bot loops: Must filter bot_id and subtype=bot_message
    - Trigger policies: dm_only | mention_or_dm | all_messages
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from agentos.communicationos.models import (
    InboundMessage,
    OutboundMessage,
    MessageType,
)
from agentos.core.time import utc_now

logger = logging.getLogger(__name__)


class SlackAdapter:
    """Channel adapter for Slack Events API.

    This adapter implements the ChannelAdapter protocol for Slack messaging
    through Slack's Events API and Web API.

    Attributes:
        channel_id: Unique identifier for this channel instance
        bot_token: Slack Bot User OAuth Token (xoxb-...)
        signing_secret: Slack App Signing Secret for webhook verification
        trigger_policy: When to respond (dm_only, mention_or_dm, all_messages)
    """

    def __init__(
        self,
        channel_id: str,
        bot_token: str,
        signing_secret: str,
        trigger_policy: str = "mention_or_dm"
    ):
        """Initialize Slack adapter.

        Args:
            channel_id: Unique channel identifier (e.g., "slack_workspace_001")
            bot_token: Slack Bot User OAuth Token (xoxb-...)
            signing_secret: Slack App Signing Secret
            trigger_policy: When to respond (dm_only, mention_or_dm, all_messages)
        """
        self.channel_id = channel_id
        self.bot_token = bot_token
        self.signing_secret = signing_secret
        self.trigger_policy = trigger_policy

        # Track processed event IDs for idempotency
        self._processed_events: set[str] = set()

    def get_channel_id(self) -> str:
        """Get the channel identifier this adapter handles.

        Returns:
            Channel ID string
        """
        return self.channel_id

    def handle_url_verification(self, event_data: Dict[str, Any]) -> Optional[str]:
        """Handle Slack URL verification challenge.

        When you configure your webhook URL in Slack, Slack sends a challenge
        request that must be responded to with the challenge value.

        Args:
            event_data: Dictionary of Slack event data

        Returns:
            Challenge string if this is a url_verification request, None otherwise

        Slack URL Verification Flow:
            1. You configure webhook URL in Slack app settings
            2. Slack sends POST with type="url_verification" and challenge
            3. You must respond with the challenge value within 3 seconds
            4. Slack marks the URL as verified

        Reference:
            https://api.slack.com/events/url_verification
        """
        if event_data.get("type") == "url_verification":
            challenge = event_data.get("challenge")
            if challenge:
                logger.info(f"Handling Slack URL verification for channel: {self.channel_id}")
                return challenge
            else:
                logger.error("URL verification request missing challenge")
        return None

    def verify_signature(
        self,
        timestamp: str,
        body: str,
        signature: str
    ) -> bool:
        """Verify Slack webhook signature.

        Args:
            timestamp: X-Slack-Request-Timestamp header value
            body: Raw request body as string
            signature: X-Slack-Signature header value

        Returns:
            True if signature is valid, False otherwise

        Security:
            This is CRITICAL for security. Always verify the signature before
            processing webhook data to prevent spoofing attacks.

        Reference:
            https://api.slack.com/authentication/verifying-requests-from-slack
        """
        from agentos.communicationos.channels.slack.client import verify_signature as verify_slack_signature

        return verify_slack_signature(
            self.signing_secret,
            timestamp,
            body,
            signature
        )

    def _should_process_event(self, event: Dict[str, Any]) -> bool:
        """Determine if this event should be processed based on trigger policy.

        Args:
            event: Slack event data

        Returns:
            True if event should be processed, False otherwise

        Trigger Policies:
            - dm_only: Only process direct messages
            - mention_or_dm: Process DMs and mentions (mentions handled via app_mention event)
            - all_messages: Process all messages in joined channels
        """
        channel_type = event.get("channel_type", "")

        # Always process DMs
        if channel_type == "im":
            return True

        # For dm_only policy, reject channel messages
        if self.trigger_policy == "dm_only":
            return False

        # For mention_or_dm policy, don't process regular channel messages
        # (mentions are handled via app_mention event type)
        if self.trigger_policy == "mention_or_dm":
            return False

        # For all_messages policy, process all channel messages
        if self.trigger_policy == "all_messages":
            return True

        return False

    def parse_event(self, event_data: Dict[str, Any]) -> Optional[InboundMessage]:
        """Parse Slack event data into InboundMessage.

        Slack sends webhook POST requests with JSON data containing event
        information. This method converts that into our unified format.

        Args:
            event_data: Dictionary of Slack event data

        Returns:
            InboundMessage in unified format, or None if should be ignored
            (e.g., messages from bots, duplicate events, filtered by policy)

        Raises:
            ValueError: If required fields are missing or invalid

        Event Structure:
            - type: "event_callback" for message events
            - event: Nested event object containing:
                - type: "message", "app_mention", etc.
                - user: User ID who sent the message
                - text: Message text
                - channel: Channel ID
                - ts: Message timestamp (unique ID)
                - thread_ts: Thread timestamp (if in thread)
                - bot_id: Present if message is from a bot
                - subtype: "bot_message" if from bot

        Bot Loop Protection:
            Messages with bot_id or subtype=bot_message are ignored.

        Thread Handling:
            If thread_ts is present, conversation_key is "{channel_id}:{thread_ts}"
            This ensures threaded conversations are tracked separately.

        Idempotency:
            Event IDs are tracked to prevent duplicate processing.
        """
        # Check for URL verification
        if event_data.get("type") == "url_verification":
            logger.debug("URL verification request, should be handled separately")
            return None

        # Extract event wrapper
        if event_data.get("type") != "event_callback":
            logger.debug(f"Ignoring non-event_callback type: {event_data.get('type')}")
            return None

        # Check for retry header (handled at webhook level, but log it)
        # Note: X-Slack-Retry-Num header indicates this is a retry
        # This should be checked at the webhook level before calling parse_event

        # Extract nested event
        event = event_data.get("event")
        if not event:
            logger.warning("Event data missing 'event' field")
            return None

        # Idempotency: Check if we've already processed this event
        event_id = event_data.get("event_id")
        if event_id and event_id in self._processed_events:
            logger.info(f"Skipping duplicate event: {event_id}")
            return None

        # Get event type
        event_type = event.get("type")

        # Bot loop protection: Ignore bot messages
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            logger.debug(
                f"Ignoring bot message: bot_id={event.get('bot_id')}, "
                f"subtype={event.get('subtype')}"
            )
            return None

        # Extract required fields first to check if valid
        user = event.get("user")
        text = event.get("text")
        channel = event.get("channel")
        ts = event.get("ts")
        thread_ts = event.get("thread_ts")

        # Validate required fields
        if not user:
            logger.warning("Event missing 'user' field, ignoring")
            return None
        if not channel:
            logger.warning("Event missing 'channel' field, ignoring")
            return None
        if not ts:
            logger.warning("Event missing 'ts' field, ignoring")
            return None

        # Only process message and app_mention events
        if event_type == "message":
            # Regular message event
            # Check trigger policy
            if not self._should_process_event(event):
                logger.debug(
                    f"Message filtered by trigger policy: {self.trigger_policy}"
                )
                return None
        elif event_type == "app_mention":
            # Bot was mentioned - always process regardless of policy
            pass
        else:
            logger.debug(f"Ignoring event type: {event_type}")
            return None

        # Build conversation_key
        # IMPORTANT: Include thread_ts if present to track threaded conversations separately
        if thread_ts:
            conversation_key = f"{channel}:{thread_ts}"
        else:
            conversation_key = channel

        # Convert Slack timestamp to datetime
        # Slack ts format: "1234567890.123456" (Unix timestamp with microseconds)
        try:
            timestamp_float = float(ts)
            timestamp = datetime.fromtimestamp(timestamp_float, tz=timezone.utc)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid Slack timestamp: {ts}, error: {e}")
            timestamp = utc_now()

        # Build message_id for deduplication
        # Use event_id if available, otherwise use client_msg_id or construct from event
        client_msg_id = event.get("client_msg_id")
        if event_id:
            message_id = f"slack_{event_id}"
        elif client_msg_id:
            message_id = f"slack_{client_msg_id}"
        else:
            # Fallback: construct from ts + channel + user
            message_id = f"slack_{ts}_{channel}_{user}"

        # Extract metadata
        channel_type = event.get("channel_type", "channel")

        # Create InboundMessage
        inbound_message = InboundMessage(
            channel_id=self.channel_id,
            user_key=user,
            conversation_key=conversation_key,
            message_id=message_id,
            timestamp=timestamp,
            type=MessageType.TEXT,
            text=text,
            raw=event_data,  # Store original data for debugging
            metadata={
                "user_id": user,
                "channel_id": channel,
                "channel_type": channel_type,
                "ts": ts,
                "thread_ts": thread_ts,
                "event_type": event_type,
                "event_id": event_id,
            }
        )

        # Mark event as processed (idempotency)
        if event_id:
            self._processed_events.add(event_id)
            # Keep only last 10000 event IDs to prevent memory growth
            if len(self._processed_events) > 10000:
                # Remove oldest 5000 (simple approach - could use LRU cache)
                self._processed_events = set(list(self._processed_events)[5000:])

        logger.info(
            f"Parsed Slack event: event_id={event_id}, "
            f"message_id={message_id}, user={user}, channel={channel}, "
            f"type={event_type}, thread={bool(thread_ts)}"
        )

        return inbound_message

    def send_message(self, message: OutboundMessage) -> bool:
        """Send an outbound message through Slack Web API.

        Args:
            message: OutboundMessage to send

        Returns:
            True if sent successfully, False otherwise

        Thread Handling:
            If the inbound message was in a thread (conversation_key contains ":"),
            the reply will be sent to the same thread by extracting thread_ts.
        """
        from agentos.communicationos.channels.slack.client import post_message

        try:
            # Extract channel from conversation_key
            # conversation_key format: "{channel_id}" or "{channel_id}:{thread_ts}"
            conversation_key = message.conversation_key
            thread_ts = None

            if ":" in conversation_key:
                # This is a thread - extract channel and thread_ts
                channel, thread_ts = conversation_key.split(":", 1)
            else:
                # This is a regular channel message
                channel = conversation_key

            # Send message via Slack API
            success, error = post_message(
                bot_token=self.bot_token,
                channel=channel,
                text=message.text or "",
                thread_ts=thread_ts
            )

            if success:
                logger.info(
                    f"Sent Slack message: channel={channel}, "
                    f"thread={bool(thread_ts)}, type={message.type.value}"
                )
            else:
                logger.error(
                    f"Failed to send Slack message: channel={channel}, "
                    f"error={error}"
                )

            return success

        except Exception as e:
            logger.exception(
                f"Failed to send Slack message: {e}"
            )
            return False
