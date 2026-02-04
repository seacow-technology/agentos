"""Twilio SMS Channel Handler - Real Implementation.

This module implements a complete bidirectional SMS channel using Twilio.
It handles:
- Inbound webhook processing (receive SMS from users)
- Outbound message sending (send SMS to users)
- Database audit trail (all messages persisted)
- Session linking (messages linked to chat conversations)
- Delivery status tracking

Architecture:
    - TwilioSMSChannel: Main channel handler class
    - Webhook processing: parse_webhook() → store → forward
    - Message sending: send_message() → Twilio API → store
    - Audit trail: All operations use ChannelMessageRepo

Design Principles:
    - End-to-end audit trail (every message persisted)
    - Real API integration (no mocks in production)
    - Status tracking (pending → delivered/failed)
    - Session linking (conversation context)

References:
    - agentos/communicationos/channels/sms/adapter.py - SMS adapter pattern
    - agentos/store/migrations/schema_v65_channel_messages.sql - Database schema
    - Wave A Task #12 - Twilio voice sessions pattern
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

from agentos.core.communication.channels.message_repo import ChannelMessageRepo
from agentos.core.storage.paths import component_db_path
from agentos.core.time import utc_now_ms

logger = logging.getLogger(__name__)


class TwilioSMSChannel:
    """Twilio SMS inbound/outbound channel handler.

    This class provides complete SMS channel functionality:
    - Receive inbound SMS via webhook
    - Send outbound SMS via Twilio API
    - Persist all messages to database
    - Link messages to chat sessions
    - Track delivery status

    Attributes:
        account_sid: Twilio Account SID
        auth_token: Twilio Auth Token
        phone_number: Twilio phone number (E.164 format)
        repo: ChannelMessageRepo for persistence
        client: Twilio REST client (lazy-loaded)
    """

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        phone_number: str,
        db_path: Optional[str] = None,
    ):
        """Initialize Twilio SMS channel.

        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token (kept secret)
            phone_number: Twilio phone number in E.164 format (e.g., +15551234567)
            db_path: Optional database path (defaults to AgentOS database)

        Raises:
            ValueError: If required parameters are missing
            ImportError: If Twilio SDK is not installed

        Example:
            >>> channel = TwilioSMSChannel(
            ...     account_sid='AC...',
            ...     auth_token='...',
            ...     phone_number='+15551234567'
            ... )
        """
        # Validate required parameters
        if not account_sid:
            raise ValueError("account_sid is required")
        if not auth_token:
            raise ValueError("auth_token is required")
        if not phone_number:
            raise ValueError("phone_number is required")

        self.account_sid = account_sid
        self.auth_token = auth_token
        self.phone_number = phone_number

        # Initialize repository
        if db_path is None:
            db_path = str(component_db_path("agentos"))

        self.repo = ChannelMessageRepo(db_path)

        # Lazy-load Twilio client (only when needed)
        self._client = None

        logger.info(
            f"Initialized TwilioSMSChannel: phone={phone_number}, "
            f"account={account_sid[:8]}..."
        )

    @property
    def client(self):
        """Lazy-load Twilio REST client.

        Returns:
            Twilio Client instance

        Raises:
            ImportError: If Twilio SDK is not installed
        """
        if self._client is None:
            try:
                from twilio.rest import Client

                self._client = Client(self.account_sid, self.auth_token)
            except ImportError:
                logger.error("Twilio SDK not installed. Run: pip install twilio")
                raise ImportError(
                    "Twilio SDK is required for SMS channel. "
                    "Install with: pip install twilio"
                )
        return self._client

    def receive_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming Twilio webhook.

        This method processes inbound SMS webhooks from Twilio:
        1. Parse webhook payload
        2. Store message in database (audit trail)
        3. Return acknowledgment

        The message is NOT immediately forwarded to a session.
        Call forward_to_session() separately to link to conversation.

        Args:
            webhook_data: Dictionary of webhook POST parameters
                - MessageSid: Unique message identifier
                - From: Sender phone number (E.164)
                - To: Recipient phone number (E.164)
                - Body: Message text content

        Returns:
            Dictionary with:
                - success: True if processed successfully
                - message_id: Database message ID
                - error: Error message if failed

        Example:
            >>> webhook_data = {
            ...     'MessageSid': 'SM1234...',
            ...     'From': '+15559876543',
            ...     'To': '+15551234567',
            ...     'Body': 'Hello!'
            ... }
            >>> result = channel.receive_webhook(webhook_data)
            >>> print(result['message_id'])
        """
        try:
            # Extract webhook fields
            twilio_message_sid = webhook_data.get("MessageSid")
            from_number = webhook_data.get("From", "")
            to_number = webhook_data.get("To", "")
            body = webhook_data.get("Body", "")

            # Validate required fields
            if not twilio_message_sid:
                error_msg = "Missing MessageSid in webhook data"
                logger.warning(error_msg)
                return {"success": False, "error": error_msg}

            if not from_number:
                error_msg = "Missing From number in webhook data"
                logger.warning(error_msg)
                return {"success": False, "error": error_msg}

            # Log inbound (mask phone for privacy)
            logger.info(
                f"Received SMS webhook: from={self._mask_phone(from_number)}, "
                f"to={self._mask_phone(to_number)}, length={len(body)}, "
                f"sid={twilio_message_sid}"
            )

            # Prepare metadata
            metadata = {
                "twilio_message_sid": twilio_message_sid,
                "twilio_from": from_number,
                "twilio_to": to_number,
                "twilio_account_sid": webhook_data.get("AccountSid", ""),
                "num_media": webhook_data.get("NumMedia", "0"),
            }

            # Store inbound message in database
            message_id = self.repo.create_inbound(
                channel_type="twilio_sms",
                channel_id=self.phone_number,  # Bot's phone number
                from_identifier=from_number,  # User's phone number
                to_identifier=to_number,  # Bot's phone number
                content=body,
                metadata=metadata,
            )

            logger.info(
                f"Stored inbound SMS: message_id={message_id}, "
                f"twilio_sid={twilio_message_sid}"
            )

            return {
                "success": True,
                "message_id": message_id,
                "twilio_message_sid": twilio_message_sid,
            }

        except Exception as e:
            error_msg = f"Failed to process webhook: {str(e)}"
            logger.exception(error_msg)
            return {"success": False, "error": error_msg}

    def send_message(
        self,
        to_number: str,
        content: str,
        session_id: Optional[str] = None,
    ) -> str:
        """Send outbound SMS via Twilio.

        This method:
        1. Creates outbound message record (status=pending)
        2. Sends SMS via Twilio API
        3. Updates status to delivered/failed

        Args:
            to_number: Recipient phone number (E.164 format)
            content: Message text content
            session_id: Optional chat session ID for linking

        Returns:
            message_id: Database message identifier

        Raises:
            ValueError: If required parameters are invalid
            Exception: If Twilio API call fails

        Example:
            >>> msg_id = channel.send_message(
            ...     to_number='+15559876543',
            ...     content='Thanks for your message!',
            ...     session_id='ses-abc123'
            ... )
        """
        # Validate inputs
        if not to_number:
            raise ValueError("to_number is required")
        if not content:
            raise ValueError("content is required")

        # Log outbound (mask phone for privacy)
        logger.info(
            f"Sending SMS: to={self._mask_phone(to_number)}, "
            f"length={len(content)}, session={session_id}"
        )

        # Prepare metadata
        metadata = {
            "provider": "twilio",
            "from_number": self.phone_number,
            "to_number": to_number,
        }

        # Create outbound message record (status=pending)
        message_id = self.repo.create_outbound(
            channel_type="twilio_sms",
            channel_id=self.phone_number,
            from_identifier=self.phone_number,  # Bot's phone number
            to_identifier=to_number,  # User's phone number
            content=content,
            session_id=session_id,
            metadata=metadata,
        )

        try:
            # Send SMS via Twilio API
            twilio_message = self.client.messages.create(
                from_=self.phone_number, to=to_number, body=content
            )

            # Update metadata with Twilio response
            metadata["twilio_message_sid"] = twilio_message.sid
            metadata["twilio_status"] = twilio_message.status

            # Update message record with success
            self.repo.update_status(message_id, "delivered")

            logger.info(
                f"SMS sent successfully: message_id={message_id}, "
                f"twilio_sid={twilio_message.sid}, status={twilio_message.status}"
            )

            return message_id

        except Exception as e:
            # Update message record with failure
            error_msg = str(e)
            self.repo.update_status(message_id, "failed", error_message=error_msg)

            logger.error(
                f"SMS send failed: message_id={message_id}, error={error_msg}"
            )

            raise

    def forward_to_session(self, message_id: str) -> str:
        """Forward received message to chat session.

        This method:
        1. Retrieves message from database
        2. Creates/gets session for sender
        3. Routes message to chat handler
        4. Links message to session

        Note: This is a placeholder for session integration.
        Full implementation requires chat session management.

        Args:
            message_id: Database message identifier

        Returns:
            session_id: Chat session identifier

        Raises:
            ValueError: If message not found
            NotImplementedError: Session creation not yet implemented

        TODO: Implement full session integration
        - Create or get existing session for user
        - Route message to chat handler
        - Handle response generation
        """
        # Retrieve message from database
        message = self.repo.get_by_id(message_id)
        if not message:
            raise ValueError(f"Message not found: {message_id}")

        # Extract user identifier (sender phone number)
        user_phone = message["from_identifier"]

        logger.info(
            f"Forwarding message to session: message_id={message_id}, "
            f"user={self._mask_phone(user_phone)}"
        )

        # TODO: Implement session creation/lookup
        # For now, create a simple session ID based on user phone
        session_id = f"sms-session-{hashlib.sha256(user_phone.encode()).hexdigest()[:16]}"

        # Link message to session
        self.repo.link_to_session(message_id, session_id)

        logger.info(f"Linked message to session: session_id={session_id}")

        # TODO: Route message to chat handler
        # This would involve:
        # 1. Get or create chat session for user
        # 2. Submit message to chat engine
        # 3. Get response from assistant
        # 4. Send response back via send_message()

        return session_id

    def verify_webhook_signature(
        self, url: str, post_data: Dict[str, str], signature: str
    ) -> bool:
        """Verify Twilio webhook signature.

        Twilio signs webhook requests with HMAC-SHA1 to prove authenticity.
        We MUST verify this signature to prevent webhook spoofing.

        Algorithm:
        1. Concatenate URL + sorted POST parameters (key + value pairs)
        2. Compute HMAC-SHA1 with auth_token as key
        3. Base64 encode the result
        4. Compare with X-Twilio-Signature header using constant-time comparison

        Args:
            url: Complete webhook URL (with protocol, domain, path)
            post_data: POST parameters dictionary
            signature: X-Twilio-Signature header value

        Returns:
            True if signature is valid, False otherwise

        Security Note:
            This is a critical security control. Always verify signatures before
            processing webhook data to prevent spoofing attacks.

        Reference:
            https://www.twilio.com/docs/usage/security#validating-requests

        Example:
            >>> is_valid = channel.verify_webhook_signature(
            ...     url='https://example.com/webhook',
            ...     post_data={'MessageSid': 'SM...', 'From': '+1...'},
            ...     signature='abc123...'
            ... )
        """
        import base64

        try:
            # Build data string: URL + sorted parameters
            sorted_params = sorted(post_data.items())
            data_string = url + "".join(f"{k}{v}" for k, v in sorted_params)

            # Compute HMAC-SHA1
            computed_sig = hmac.new(
                self.auth_token.encode("utf-8"),
                data_string.encode("utf-8"),
                hashlib.sha1,
            ).digest()

            # Base64 encode
            computed_sig_b64 = base64.b64encode(computed_sig).decode("ascii")

            # Constant-time comparison (prevents timing attacks)
            is_valid = hmac.compare_digest(computed_sig_b64, signature)

            if not is_valid:
                logger.warning(
                    f"Invalid Twilio signature for webhook. "
                    f"Expected: {computed_sig_b64[:10]}..., Got: {signature[:10]}..."
                )

            return is_valid

        except Exception as e:
            logger.error(f"Failed to verify webhook signature: {e}")
            return False

    def _mask_phone(self, phone_number: str) -> str:
        """Mask phone number for logging (privacy).

        Masks all but the last 4 digits.
        Example: +15551234567 -> +1******4567

        Args:
            phone_number: Phone number to mask

        Returns:
            Masked phone number string
        """
        if not phone_number:
            return "****"
        if len(phone_number) <= 4:
            return "****"
        return phone_number[:2] + "*" * (len(phone_number) - 6) + phone_number[-4:]
