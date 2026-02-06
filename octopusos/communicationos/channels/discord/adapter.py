"""Discord Channel Adapter with Slash Command Support.

This module implements a ChannelAdapter for Discord via Discord Interactions API.
It handles Slash Commands with proper defer mechanisms and async processing.

Architecture:
    - parse_interaction(): Converts Discord slash command to InboundMessage
    - handle_slash_command(): Immediately returns defer response (type 5)
    - process_slash_command_async(): Background async processing
    - send_message(): Sends OutboundMessage via webhook edit
    - verify_signature(): Validates Ed25519 signature using public key

Key Discord Complexities:
    - Interactions MUST respond within 3 seconds (use defer)
    - Defer: Return type 5 (DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE)
    - Actual processing: Background async after defer
    - Interaction tokens expire after 15 minutes
    - Ed25519 signature verification required
    - Idempotency: Track interaction.id to prevent duplicate processing

V1 Scope:
    - Slash Commands only (type=2)
    - No Message Components, Modal Submits, etc.
    - Simple text responses only
    - No embeds or attachments in v1
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from agentos.communicationos.models import (
    InboundMessage,
    OutboundMessage,
    MessageType,
)
from agentos.communicationos.channels.discord.client import DiscordClient
from agentos.core.time import utc_now

logger = logging.getLogger(__name__)


class DiscordAdapter:
    """Channel adapter for Discord Interactions API.

    This adapter implements the ChannelAdapter protocol for Discord Slash Commands
    through Discord's Interactions API.

    Attributes:
        channel_id: Unique identifier for this channel instance
        application_id: Discord Application ID
        public_key: Discord Application Public Key (for signature verification)
        bot_token: Discord Bot Token (for editing responses)
    """

    # Discord Interaction Types
    INTERACTION_TYPE_PING = 1
    INTERACTION_TYPE_APPLICATION_COMMAND = 2

    # Discord Interaction Response Types
    RESPONSE_TYPE_PONG = 1
    RESPONSE_TYPE_DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5

    def __init__(
        self,
        channel_id: str,
        application_id: str,
        public_key: str,
        bot_token: str,
    ):
        """Initialize Discord adapter.

        Args:
            channel_id: Unique channel identifier (e.g., "discord_bot_001")
            application_id: Discord Application ID
            public_key: Discord Application Public Key (for Ed25519 signature verification)
            bot_token: Discord Bot Token (for editing interaction responses)
        """
        self.channel_id = channel_id
        self.application_id = application_id
        self.public_key = public_key
        self.bot_token = bot_token

        # Track processed interaction IDs for idempotency
        self._processed_interactions: set[str] = set()

        # Initialize Discord client
        self._client = DiscordClient(
            application_id=application_id,
            bot_token=bot_token
        )

    def get_channel_id(self) -> str:
        """Get the channel identifier this adapter handles.

        Returns:
            Channel ID string
        """
        return self.channel_id

    def verify_signature(
        self,
        signature: str,
        timestamp: str,
        body: bytes
    ) -> bool:
        """Verify Discord interaction signature using Ed25519.

        Args:
            signature: X-Signature-Ed25519 header value
            timestamp: X-Signature-Timestamp header value
            body: Raw request body as bytes

        Returns:
            True if signature is valid, False otherwise

        Security:
            This is CRITICAL for security. Always verify the signature before
            processing webhook data to prevent spoofing attacks.

        Reference:
            https://discord.com/developers/docs/interactions/receiving-and-responding#security-and-authorization
        """
        try:
            from nacl.signing import VerifyKey
            from nacl.exceptions import BadSignatureError

            # Construct the message to verify: timestamp + body
            message = timestamp.encode() + body

            # Decode the signature from hex
            signature_bytes = bytes.fromhex(signature)

            # Create verify key from public key
            verify_key = VerifyKey(bytes.fromhex(self.public_key))

            # Verify the signature
            verify_key.verify(message, signature_bytes)

            logger.debug(f"Discord signature verified for channel: {self.channel_id}")
            return True

        except ImportError:
            logger.warning("PyNaCl not installed - signature verification unavailable")
            return False
        except ValueError as e:
            logger.warning(f"Invalid signature format: {e}")
            return False
        except Exception as e:
            # This will catch BadSignatureError if PyNaCl is installed
            logger.warning(f"Discord signature verification failed: {e}")
            return False

    def handle_ping(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Discord PING interaction (type=1).

        Discord sends PING to verify your endpoint during initial setup.
        You must respond with type=1 (PONG).

        Args:
            interaction: Discord interaction data

        Returns:
            Response dict with type=1 (PONG)

        Reference:
            https://discord.com/developers/docs/interactions/receiving-and-responding#interaction-object
        """
        logger.info(f"Handling Discord PING for channel: {self.channel_id}")
        return {"type": self.RESPONSE_TYPE_PONG}

    def handle_slash_command(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """Handle slash command interaction by returning immediate defer.

        This is the KEY to avoiding Discord's 3-second timeout:
        1. Immediately return type=5 (DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE)
        2. Discord shows "Bot is thinking..." to the user
        3. Process command in background via process_slash_command_async()
        4. Edit the original response when processing is complete

        Args:
            interaction: Discord interaction data

        Returns:
            Response dict with type=5 (DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE)

        Critical:
            This MUST return within 3 seconds or Discord will timeout and retry.

        Reference:
            https://discord.com/developers/docs/interactions/receiving-and-responding#interaction-response-object-interaction-callback-type
        """
        interaction_id = interaction.get("id")
        logger.info(
            f"Deferring Discord slash command: interaction_id={interaction_id}, "
            f"channel={self.channel_id}"
        )

        # Return defer immediately (within 3 seconds)
        return {"type": self.RESPONSE_TYPE_DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE}

    def parse_interaction(self, interaction: Dict[str, Any]) -> Optional[InboundMessage]:
        """Parse Discord interaction into InboundMessage.

        Discord sends webhook POST requests with JSON data containing interaction
        information. This method converts that into our unified format.

        Args:
            interaction: Dictionary of Discord interaction data

        Returns:
            InboundMessage in unified format, or None if should be ignored
            (e.g., duplicate interactions)

        Raises:
            ValueError: If required fields are missing or invalid

        Interaction Structure (type=2 APPLICATION_COMMAND):
            - id: Unique interaction ID (for idempotency)
            - type: 2 for APPLICATION_COMMAND (slash command)
            - data: Command data containing:
                - name: Command name (e.g., "ask")
                - options: Array of command options/arguments
            - user: User who invoked the command (in DM)
            - member: Member who invoked (in guild)
                - user: Nested user object
            - channel_id: Channel where command was invoked
            - guild_id: Guild ID (if in a server)
            - token: Interaction token (valid for 15 minutes)

        Idempotency:
            Interaction IDs are tracked to prevent duplicate processing.

        Reference:
            https://discord.com/developers/docs/interactions/receiving-and-responding#interaction-object
        """
        # Extract interaction type
        interaction_type = interaction.get("type")

        # Only process APPLICATION_COMMAND (type=2) interactions
        if interaction_type != self.INTERACTION_TYPE_APPLICATION_COMMAND:
            logger.debug(f"Ignoring non-slash-command interaction type: {interaction_type}")
            return None

        # Extract required fields
        interaction_id = interaction.get("id")
        channel_id = interaction.get("channel_id")
        token = interaction.get("token")

        # Validate required fields
        if not interaction_id:
            logger.warning("Interaction missing 'id' field, ignoring")
            return None
        if not channel_id:
            logger.warning("Interaction missing 'channel_id' field, ignoring")
            return None
        if not token:
            logger.warning("Interaction missing 'token' field, ignoring")
            return None

        # Idempotency: Check if we've already processed this interaction
        if interaction_id in self._processed_interactions:
            logger.info(f"Skipping duplicate interaction: {interaction_id}")
            return None

        # Extract user information
        # In guilds: interaction.member.user
        # In DMs: interaction.user
        member = interaction.get("member")
        user = interaction.get("user")

        if member and "user" in member:
            user = member["user"]

        if not user:
            logger.warning("Interaction missing user information, ignoring")
            return None

        user_id = user.get("id")
        user_name = user.get("username")

        if not user_id:
            logger.warning("User missing 'id' field, ignoring")
            return None

        # Extract command data
        data = interaction.get("data", {})
        command_name = data.get("name", "unknown")
        options = data.get("options", [])

        # Build text content from command name and options
        # Example: "/ask question: What is AgentOS?"
        text_parts = [f"/{command_name}"]
        for option in options:
            option_name = option.get("name", "")
            option_value = option.get("value", "")
            text_parts.append(f"{option_name}: {option_value}")

        text = " ".join(text_parts)

        # Use interaction.id as message_id for deduplication
        message_id = f"discord_interaction_{interaction_id}"

        # Guild context
        guild_id = interaction.get("guild_id")

        # Conversation key: channel_id (same channel = same conversation)
        conversation_key = channel_id

        # Timestamp (Discord doesn't provide, use current time)
        timestamp = utc_now()

        # Create InboundMessage
        inbound_message = InboundMessage(
            channel_id=self.channel_id,
            user_key=user_id,
            conversation_key=conversation_key,
            message_id=message_id,
            timestamp=timestamp,
            type=MessageType.TEXT,
            text=text,
            raw=interaction,  # Store original data for debugging
            metadata={
                "interaction_id": interaction_id,
                "interaction_token": token,
                "command_name": command_name,
                "command_options": options,
                "discord_channel_id": channel_id,
                "discord_guild_id": guild_id,
                "discord_user_id": user_id,
                "discord_user_name": user_name,
            }
        )

        # Mark interaction as processed (idempotency)
        self._processed_interactions.add(interaction_id)
        # Keep only last 10000 interaction IDs to prevent memory growth
        if len(self._processed_interactions) > 10000:
            self._processed_interactions = set(list(self._processed_interactions)[5000:])

        logger.info(
            f"Parsed Discord interaction: interaction_id={interaction_id}, "
            f"command={command_name}, user={user_name}, channel={channel_id}"
        )

        return inbound_message

    async def process_slash_command_async(
        self,
        interaction: Dict[str, Any],
        message_bus,
    ) -> None:
        """Process slash command asynchronously after defer.

        This function runs in the background after handle_slash_command()
        has returned the defer response. It performs the actual processing:
        1. Parse interaction to InboundMessage
        2. Process through MessageBus (dedupe, rate limit, audit)
        3. Forward to chat/business logic
        4. Get reply text
        5. Edit original interaction response

        Args:
            interaction: Discord interaction data
            message_bus: MessageBus instance for processing

        Important:
            - Must complete within 15 minutes (interaction token expiry)
            - Any exceptions should be logged but not crash the app
            - Edit response even if processing fails (send error message)

        Reference:
            https://discord.com/developers/docs/interactions/receiving-and-responding#edit-original-interaction-response
        """
        interaction_id = interaction.get("id")
        interaction_token = interaction.get("token")

        try:
            logger.info(
                f"Starting async processing for interaction: {interaction_id}"
            )

            # Parse interaction to InboundMessage
            inbound_message = self.parse_interaction(interaction)

            if inbound_message is None:
                logger.info(f"Interaction ignored by parser: {interaction_id}")
                # Edit response to acknowledge
                await self._client.edit_original_response(
                    interaction_token=interaction_token,
                    content="Command acknowledged but not processed (likely duplicate)."
                )
                return

            # Process through MessageBus
            context = await message_bus.process_inbound(inbound_message)

            # Check processing status
            from agentos.communicationos.message_bus import ProcessingStatus

            if context.status == ProcessingStatus.REJECT:
                logger.info(
                    f"Message rejected by middleware: {context.error}"
                )
                # Edit response with rejection reason
                await self._client.edit_original_response(
                    interaction_token=interaction_token,
                    content=f"Command rejected: {context.error or 'Unknown reason'}"
                )
                return

            if context.status == ProcessingStatus.ERROR:
                logger.error(
                    f"Error processing message: {context.error}"
                )
                # Edit response with error
                await self._client.edit_original_response(
                    interaction_token=interaction_token,
                    content=f"Error processing command: {context.error or 'Unknown error'}"
                )
                return

            # Command processed successfully
            # In production, you would:
            # 1. Check if message is a command
            # 2. Process command or forward to chat
            # 3. Get reply text from business logic
            # 4. Edit original response with reply

            # For now, send a placeholder success message
            # TODO: Integrate with actual chat/command processing
            reply_text = (
                f"Command received: {inbound_message.text}\n\n"
                f"Note: Full chat integration pending. "
                f"This is a placeholder response from Discord adapter."
            )

            # Edit the original deferred response
            await self._client.edit_original_response(
                interaction_token=interaction_token,
                content=reply_text
            )

            logger.info(
                f"Successfully processed and replied to interaction: {interaction_id}"
            )

        except Exception as e:
            logger.exception(
                f"Failed to process slash command async: {e}"
            )

            # Try to edit response with error (best effort)
            try:
                await self._client.edit_original_response(
                    interaction_token=interaction_token,
                    content=f"An error occurred while processing your command: {str(e)}"
                )
            except Exception as edit_error:
                logger.exception(
                    f"Failed to edit response with error message: {edit_error}"
                )

    def send_message(self, message: OutboundMessage) -> bool:
        """Send an outbound message through Discord webhook.

        For Discord interactions, we don't directly send messages.
        Instead, we edit the original deferred response.

        This method is provided for ChannelAdapter protocol compatibility,
        but for Discord slash commands, you should use edit_original_response
        directly via the async processing flow.

        Args:
            message: OutboundMessage to send

        Returns:
            False (not supported for Discord interactions in v1)

        Note:
            To send followup messages, use create_followup_message from client.
            For v1, we only support editing the original deferred response.
        """
        logger.warning(
            "send_message() called on Discord adapter. "
            "Discord interactions should use edit_original_response via async processing. "
            "This is a no-op in v1."
        )
        return False
