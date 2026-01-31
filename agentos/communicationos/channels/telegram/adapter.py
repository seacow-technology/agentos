"""Telegram Channel Adapter.

This module implements a ChannelAdapter for Telegram via Telegram Bot API.
It handles webhook parsing, message sending, and secret token verification.

Architecture:
    - parse_update(): Converts Telegram update to InboundMessage
    - send_message(): Sends OutboundMessage via Telegram Bot API
    - verify_secret(): Validates X-Telegram-Bot-Api-Secret-Token header
    - Bot loop protection: Ignores messages from bots (from.is_bot == true)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from agentos.communicationos.models import (
    InboundMessage,
    OutboundMessage,
    MessageType,
    Attachment,
    AttachmentType,
    Location,
)
from agentos.core.time import utc_now

logger = logging.getLogger(__name__)


class TelegramAdapter:
    """Channel adapter for Telegram Bot API.

    This adapter implements the ChannelAdapter protocol for Telegram messaging
    through Telegram's Bot API.

    Attributes:
        channel_id: Unique identifier for this channel instance
        bot_token: Telegram Bot Token from @BotFather
        webhook_secret: Secret token for webhook verification
    """

    def __init__(
        self,
        channel_id: str,
        bot_token: str,
        webhook_secret: str
    ):
        """Initialize Telegram adapter.

        Args:
            channel_id: Unique channel identifier (e.g., "telegram_bot_001")
            bot_token: Telegram Bot Token from @BotFather
            webhook_secret: Secret token for webhook verification
        """
        self.channel_id = channel_id
        self.bot_token = bot_token
        self.webhook_secret = webhook_secret

    def get_channel_id(self) -> str:
        """Get the channel identifier this adapter handles.

        Returns:
            Channel ID string
        """
        return self.channel_id

    def parse_update(self, update_data: Dict[str, Any]) -> Optional[InboundMessage]:
        """Parse Telegram update data into InboundMessage.

        Telegram sends webhook POST requests with JSON data containing update
        information. This method converts that into our unified format.

        Args:
            update_data: Dictionary of Telegram update data

        Returns:
            InboundMessage in unified format, or None if should be ignored
            (e.g., messages from bots)

        Raises:
            ValueError: If required fields are missing or invalid

        Update Fields Reference:
            - update_id: Unique update identifier
            - message: Message object containing:
                - message_id: Unique message identifier
                - from: User object (sender)
                - chat: Chat object (conversation)
                - date: Unix timestamp
                - text: Text content (for text messages)
                - photo: Photo array (for image messages)
                - document: Document object (for file messages)
                - audio: Audio object (for audio messages)
                - video: Video object (for video messages)
                - location: Location object (for location messages)

        Bot Loop Protection:
            Messages where from.is_bot == true are ignored to prevent bot loops.
        """
        # Extract message object from update
        message = update_data.get("message")
        if not message:
            # Could be edited_message, channel_post, etc.
            # For now, we only handle regular messages
            logger.debug("Update does not contain a message object, ignoring")
            return None

        # Bot loop protection: Ignore messages from bots
        from_user = message.get("from", {})
        if from_user.get("is_bot", False):
            logger.debug(
                f"Ignoring message from bot: user_id={from_user.get('id')}, "
                f"username={from_user.get('username')}"
            )
            return None

        # Extract required fields
        update_id = update_data.get("update_id")
        message_id = message.get("message_id")
        chat = message.get("chat", {})
        date_timestamp = message.get("date")

        if not all([update_id, message_id, chat, date_timestamp]):
            raise ValueError("Missing required fields in Telegram update")

        # Extract user and conversation identifiers
        user_id = from_user.get("id")
        chat_id = chat.get("id")

        if not user_id or not chat_id:
            raise ValueError("Missing user_id or chat_id in Telegram update")

        # Convert to strings for consistency
        user_key = str(user_id)
        conversation_key = str(chat_id)
        message_id_str = str(message_id)

        # Convert Unix timestamp to timezone-aware datetime (UTC)
        timestamp = datetime.fromtimestamp(date_timestamp, tz=timezone.utc)

        # Determine message type and extract content
        message_type = MessageType.TEXT
        text = None
        attachments = []
        location = None

        # Text message
        if "text" in message:
            text = message["text"]
            message_type = MessageType.TEXT

        # Photo message
        elif "photo" in message:
            message_type = MessageType.IMAGE
            # Telegram sends multiple sizes, get the largest one
            photos = message["photo"]
            if photos:
                largest_photo = max(photos, key=lambda p: p.get("file_size", 0))
                file_id = largest_photo.get("file_id")
                if file_id:
                    attachments.append(Attachment(
                        type=AttachmentType.IMAGE,
                        url=file_id,  # Store file_id, actual URL retrieved via API
                        mime_type="image/jpeg",
                        size_bytes=largest_photo.get("file_size"),
                        metadata={
                            "file_id": file_id,
                            "width": largest_photo.get("width"),
                            "height": largest_photo.get("height"),
                        }
                    ))
            # Caption is like text for media messages
            text = message.get("caption")

        # Audio message
        elif "audio" in message or "voice" in message:
            message_type = MessageType.AUDIO
            audio_obj = message.get("audio") or message.get("voice")
            file_id = audio_obj.get("file_id")
            if file_id:
                attachments.append(Attachment(
                    type=AttachmentType.AUDIO,
                    url=file_id,
                    mime_type=audio_obj.get("mime_type", "audio/ogg"),
                    filename=audio_obj.get("file_name"),
                    size_bytes=audio_obj.get("file_size"),
                    metadata={
                        "file_id": file_id,
                        "duration": audio_obj.get("duration"),
                    }
                ))
            text = message.get("caption")

        # Video message
        elif "video" in message:
            message_type = MessageType.VIDEO
            video_obj = message["video"]
            file_id = video_obj.get("file_id")
            if file_id:
                attachments.append(Attachment(
                    type=AttachmentType.VIDEO,
                    url=file_id,
                    mime_type=video_obj.get("mime_type", "video/mp4"),
                    filename=video_obj.get("file_name"),
                    size_bytes=video_obj.get("file_size"),
                    metadata={
                        "file_id": file_id,
                        "duration": video_obj.get("duration"),
                        "width": video_obj.get("width"),
                        "height": video_obj.get("height"),
                    }
                ))
            text = message.get("caption")

        # Document/File message
        elif "document" in message:
            message_type = MessageType.FILE
            doc_obj = message["document"]
            file_id = doc_obj.get("file_id")
            if file_id:
                attachments.append(Attachment(
                    type=AttachmentType.DOCUMENT,
                    url=file_id,
                    mime_type=doc_obj.get("mime_type", "application/octet-stream"),
                    filename=doc_obj.get("file_name"),
                    size_bytes=doc_obj.get("file_size"),
                    metadata={
                        "file_id": file_id,
                    }
                ))
            text = message.get("caption")

        # Location message
        elif "location" in message:
            message_type = MessageType.LOCATION
            loc_obj = message["location"]
            location = Location(
                latitude=loc_obj["latitude"],
                longitude=loc_obj["longitude"]
            )

        # Extract additional metadata
        username = from_user.get("username", "")
        first_name = from_user.get("first_name", "")
        last_name = from_user.get("last_name", "")
        chat_type = chat.get("type", "private")

        # Build display name
        display_name = username or f"{first_name} {last_name}".strip() or user_key

        # Create InboundMessage
        inbound_message = InboundMessage(
            channel_id=self.channel_id,
            user_key=user_key,
            conversation_key=conversation_key,
            message_id=f"tg_{update_id}_{message_id_str}",  # Unique ID for deduplication
            timestamp=timestamp,
            type=message_type,
            text=text,
            attachments=attachments,
            location=location,
            raw=update_data,  # Store original data for debugging
            metadata={
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "display_name": display_name,
                "chat_id": chat_id,
                "chat_type": chat_type,
                "message_id": message_id,
                "update_id": update_id,
            }
        )

        logger.info(
            f"Parsed Telegram update: update_id={update_id}, "
            f"message_id={message_id}, from={display_name}, type={message_type.value}"
        )

        return inbound_message

    def send_message(self, message: OutboundMessage) -> bool:
        """Send an outbound message through Telegram Bot API.

        Args:
            message: OutboundMessage to send

        Returns:
            True if sent successfully, False otherwise
        """
        from agentos.communicationos.channels.telegram.client import send_message as send_telegram_message

        try:
            # Extract chat_id from conversation_key
            chat_id = message.conversation_key

            # Extract reply_to_message_id if present
            reply_to_message_id = None
            if message.reply_to_message_id:
                # Extract actual message_id from our composite ID (tg_{update_id}_{message_id})
                parts = message.reply_to_message_id.split("_")
                if len(parts) >= 3 and parts[0] == "tg":
                    reply_to_message_id = int(parts[2])
                else:
                    # Fallback: try to parse as integer
                    try:
                        reply_to_message_id = int(message.reply_to_message_id)
                    except (ValueError, TypeError):
                        logger.warning(
                            f"Could not parse reply_to_message_id: {message.reply_to_message_id}"
                        )

            # Send message based on type
            success = send_telegram_message(
                bot_token=self.bot_token,
                chat_id=chat_id,
                text=message.text or "",
                reply_to_message_id=reply_to_message_id
            )

            if success:
                logger.info(
                    f"Sent Telegram message: chat_id={chat_id}, "
                    f"type={message.type.value}"
                )
            else:
                logger.error(
                    f"Failed to send Telegram message: chat_id={chat_id}"
                )

            return success

        except Exception as e:
            logger.exception(
                f"Failed to send Telegram message: {e}"
            )
            return False

    def verify_secret(self, secret_token: Optional[str]) -> bool:
        """Verify webhook secret token.

        Telegram allows setting a secret token that will be sent with every
        webhook request in the X-Telegram-Bot-Api-Secret-Token header.

        Args:
            secret_token: X-Telegram-Bot-Api-Secret-Token header value

        Returns:
            True if secret token is valid, False otherwise

        Security Note:
            This is a critical security control. Always verify the secret token
            before processing webhook data to prevent spoofing attacks.

        Reference:
            https://core.telegram.org/bots/api#setwebhook
        """
        if not secret_token:
            logger.warning("Missing X-Telegram-Bot-Api-Secret-Token header")
            return False

        # Constant-time comparison to prevent timing attacks
        import hmac
        return hmac.compare_digest(secret_token, self.webhook_secret)
