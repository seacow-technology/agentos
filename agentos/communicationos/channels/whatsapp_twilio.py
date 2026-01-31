"""WhatsApp Twilio Channel Adapter.

This module implements a ChannelAdapter for WhatsApp via Twilio's Business API.
It handles webhook parsing, message sending, and signature verification.

Architecture:
    - parse_event(): Converts Twilio webhook data to InboundMessage
    - send_message(): Sends OutboundMessage via Twilio API
    - verify_signature(): Validates webhook authenticity
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin

from agentos.communicationos.models import (
    InboundMessage,
    OutboundMessage,
    MessageType,
    Attachment,
    AttachmentType,
)
from agentos.core.time import utc_now

logger = logging.getLogger(__name__)


def verify_twilio_signature(
    auth_token: str,
    twilio_signature: str,
    url: str,
    params: Dict[str, Any]
) -> bool:
    """Verify Twilio webhook signature.

    Twilio signs webhook requests with HMAC-SHA256 to prove authenticity.
    We MUST verify this signature to prevent webhook spoofing.

    Args:
        auth_token: Twilio Auth Token (shared secret)
        twilio_signature: X-Twilio-Signature header value
        url: Full webhook URL (including protocol and domain)
        params: POST parameters from the webhook

    Returns:
        True if signature is valid, False otherwise

    Security Note:
        This is a critical security control. Always verify signatures before
        processing webhook data to prevent spoofing attacks.

    Reference:
        https://www.twilio.com/docs/usage/security#validating-requests
    """
    # Concatenate the URL and sorted parameters
    data = url
    for key in sorted(params.keys()):
        data += key + params[key]

    # Compute HMAC-SHA256
    mac = hmac.new(
        auth_token.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    )
    expected_signature = mac.digest().hex()

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_signature, twilio_signature)


class WhatsAppTwilioAdapter:
    """Channel adapter for WhatsApp via Twilio.

    This adapter implements the ChannelAdapter protocol for WhatsApp messaging
    through Twilio's Business API.

    Attributes:
        channel_id: Unique identifier for this channel instance
        account_sid: Twilio Account SID
        auth_token: Twilio Auth Token
        phone_number: WhatsApp-enabled phone number (E.164 format)
        messaging_service_sid: Optional Messaging Service SID
    """

    def __init__(
        self,
        channel_id: str,
        account_sid: str,
        auth_token: str,
        phone_number: str,
        messaging_service_sid: Optional[str] = None
    ):
        """Initialize WhatsApp Twilio adapter.

        Args:
            channel_id: Unique channel identifier (e.g., "whatsapp_twilio_001")
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token (kept secret)
            phone_number: WhatsApp phone number in E.164 format
            messaging_service_sid: Optional Messaging Service SID
        """
        self.channel_id = channel_id
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.phone_number = phone_number
        self.messaging_service_sid = messaging_service_sid

        # Lazy import to avoid circular dependencies
        try:
            from twilio.rest import Client
            self._client = Client(account_sid, auth_token)
        except ImportError:
            logger.error(
                "Twilio SDK not installed. Run: pip install twilio"
            )
            raise ImportError(
                "Twilio SDK is required for WhatsApp adapter. "
                "Install with: pip install twilio"
            )

    def get_channel_id(self) -> str:
        """Get the channel identifier this adapter handles.

        Returns:
            Channel ID string
        """
        return self.channel_id

    def parse_event(self, webhook_data: Dict[str, Any]) -> InboundMessage:
        """Parse Twilio webhook data into InboundMessage.

        Twilio sends webhook POST requests with form-encoded data containing
        message details. This method converts that into our unified format.

        Args:
            webhook_data: Dictionary of webhook POST parameters

        Returns:
            InboundMessage in unified format

        Raises:
            ValueError: If required fields are missing or invalid

        Webhook Fields Reference:
            - MessageSid: Unique message identifier
            - From: Sender's WhatsApp number (whatsapp:+1234567890)
            - To: Recipient's WhatsApp number (whatsapp:+1234567890)
            - Body: Message text content
            - NumMedia: Number of media attachments
            - MediaUrl{N}: URL to media file
            - MediaContentType{N}: MIME type of media
        """
        # Extract required fields
        message_sid = webhook_data.get("MessageSid")
        from_number = webhook_data.get("From", "")
        to_number = webhook_data.get("To", "")
        body = webhook_data.get("Body", "")
        num_media = int(webhook_data.get("NumMedia", 0))

        if not message_sid:
            raise ValueError("Missing MessageSid in webhook data")

        # Extract WhatsApp number from "whatsapp:+1234567890" format
        user_key = from_number.replace("whatsapp:", "") if from_number else ""
        if not user_key:
            raise ValueError("Missing From number in webhook data")

        # For WhatsApp, conversation_key is typically the user's number
        # (1-on-1 conversations, no group support in this basic implementation)
        conversation_key = user_key

        # Determine message type
        message_type = MessageType.TEXT
        attachments = []

        # Parse media attachments if present
        if num_media > 0:
            for i in range(num_media):
                media_url = webhook_data.get(f"MediaUrl{i}")
                media_content_type = webhook_data.get(f"MediaContentType{i}")

                if media_url:
                    # Determine attachment type from MIME type
                    attachment_type = self._mime_to_attachment_type(
                        media_content_type or ""
                    )

                    attachments.append(Attachment(
                        type=attachment_type,
                        url=media_url,
                        mime_type=media_content_type,
                        metadata={"index": i}
                    ))

            # Set message type based on first attachment
            if attachments:
                first_attachment_type = attachments[0].type
                if first_attachment_type == AttachmentType.IMAGE:
                    message_type = MessageType.IMAGE
                elif first_attachment_type == AttachmentType.AUDIO:
                    message_type = MessageType.AUDIO
                elif first_attachment_type == AttachmentType.VIDEO:
                    message_type = MessageType.VIDEO
                elif first_attachment_type == AttachmentType.DOCUMENT:
                    message_type = MessageType.FILE

        # Extract additional metadata
        profile_name = webhook_data.get("ProfileName", "")
        account_sid = webhook_data.get("AccountSid", "")

        # Create InboundMessage
        message = InboundMessage(
            channel_id=self.channel_id,
            user_key=user_key,
            conversation_key=conversation_key,
            message_id=message_sid,
            timestamp=utc_now(),
            type=message_type,
            text=body if body else None,
            attachments=attachments,
            raw=webhook_data,  # Store original data for debugging
            metadata={
                "profile_name": profile_name,
                "account_sid": account_sid,
                "to_number": to_number,
            }
        )

        logger.info(
            f"Parsed Twilio webhook: message_id={message_sid}, "
            f"from={user_key}, type={message_type.value}"
        )

        return message

    def send_message(self, message: OutboundMessage) -> bool:
        """Send an outbound message through Twilio WhatsApp API.

        Args:
            message: OutboundMessage to send

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Format WhatsApp numbers
            from_number = f"whatsapp:{self.phone_number}"
            to_number = f"whatsapp:{message.user_key}"

            # Prepare message parameters
            params = {
                "from_": from_number,
                "to": to_number,
            }

            # Add body text
            if message.text:
                params["body"] = message.text

            # Add media URL if attachments present
            # Note: Twilio supports one media URL per message for WhatsApp
            if message.attachments and len(message.attachments) > 0:
                first_attachment = message.attachments[0]
                if first_attachment.url:
                    params["media_url"] = [first_attachment.url]

                # If there are multiple attachments, log a warning
                if len(message.attachments) > 1:
                    logger.warning(
                        f"WhatsApp via Twilio supports only 1 media per message. "
                        f"Sending first attachment only. Channel: {self.channel_id}"
                    )

            # Send message via Twilio
            twilio_message = self._client.messages.create(**params)

            logger.info(
                f"Sent WhatsApp message via Twilio: sid={twilio_message.sid}, "
                f"to={message.user_key}, status={twilio_message.status}"
            )

            return True

        except Exception as e:
            logger.exception(
                f"Failed to send WhatsApp message via Twilio: {e}"
            )
            return False

    def _mime_to_attachment_type(self, mime_type: str) -> AttachmentType:
        """Convert MIME type to AttachmentType.

        Args:
            mime_type: MIME type string (e.g., "image/jpeg")

        Returns:
            AttachmentType enum value
        """
        mime_lower = mime_type.lower()

        if mime_lower.startswith("image/"):
            return AttachmentType.IMAGE
        elif mime_lower.startswith("audio/"):
            return AttachmentType.AUDIO
        elif mime_lower.startswith("video/"):
            return AttachmentType.VIDEO
        else:
            return AttachmentType.DOCUMENT

    def verify_webhook_signature(
        self,
        signature: str,
        url: str,
        params: Dict[str, Any]
    ) -> bool:
        """Verify webhook request signature.

        Args:
            signature: X-Twilio-Signature header value
            url: Full webhook URL
            params: POST parameters

        Returns:
            True if signature is valid, False otherwise
        """
        return verify_twilio_signature(
            self.auth_token,
            signature,
            url,
            params
        )
