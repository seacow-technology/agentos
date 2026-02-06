"""SMS Channel Adapter with Inbound Webhook Support.

This module implements a bidirectional SMS channel adapter for SMS notifications via providers
like Twilio. It supports both outbound sending and inbound webhook processing.

Architecture:
    - handle_outbound(): Validates and sends SMS via provider
    - parse_inbound_webhook(): Converts webhook data to InboundMessage
    - verify_twilio_signature(): Validates webhook authenticity (HMAC-SHA1)
    - Audit logging (metadata only, no message content)

Design Principles:
    - Bidirectional: Supports both sending and receiving SMS
    - Secure: Signature verification with constant-time comparison
    - Validated: E.164 phone number format validation
    - Idempotent: MessageSid-based deduplication
    - Provider-agnostic: Uses ISmsProvider protocol
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re
from hmac import compare_digest
from typing import Optional, Dict, Any

from agentos.communicationos.models import OutboundMessage, InboundMessage, MessageType
from agentos.communicationos.providers.sms import ISmsProvider, SendResult
from agentos.communicationos.audit import AuditStore
from agentos.core.time import utc_now_ms, utc_now

logger = logging.getLogger(__name__)

# E.164 phone number validation regex
# Format: + followed by country code and number (1-15 digits total)
# Examples: +1234567890, +442071838750, +8613800138000
E164_REGEX = re.compile(r'^\+[1-9]\d{1,14}$')


class SmsAdapter:
    """Send-only SMS channel adapter.

    This adapter handles outbound SMS sending through an ISmsProvider implementation.
    It validates phone numbers, enforces message length limits, and logs all operations
    to an audit trail.

    Attributes:
        channel_id: Unique identifier for this channel instance
        provider: ISmsProvider implementation (e.g., TwilioSmsProvider)
        audit_store: Optional AuditStore for logging sends
        max_length: Maximum message length in characters (default 480)
    """

    def __init__(
        self,
        channel_id: str,
        provider: ISmsProvider,
        audit_store: Optional[AuditStore] = None,
        max_length: int = 480,
        webhook_auth_token: Optional[str] = None
    ):
        """Initialize SMS adapter.

        Args:
            channel_id: Unique channel identifier (e.g., "sms_twilio_001")
            provider: ISmsProvider implementation for sending SMS
            audit_store: Optional AuditStore for audit logging
            max_length: Maximum message length (default 480 chars = ~3 SMS segments)
            webhook_auth_token: Twilio Auth Token for webhook signature verification
        """
        self.channel_id = channel_id
        self.provider = provider
        self.audit_store = audit_store
        self.max_length = max_length
        self.webhook_auth_token = webhook_auth_token

        # Idempotent deduplication (in-memory)
        self._processed_message_sids = set()
        self._max_tracked_sids = 10000

        logger.info(
            f"Initialized SMS adapter: channel_id={channel_id}, "
            f"max_length={max_length}, webhook_enabled={webhook_auth_token is not None}"
        )

    def get_channel_id(self) -> str:
        """Get the channel identifier this adapter handles.

        Returns:
            Channel ID string
        """
        return self.channel_id

    def handle_outbound(self, message: OutboundMessage) -> SendResult:
        """Handle outbound SMS message.

        This method:
        1. Validates the recipient phone number (E.164 format)
        2. Validates message text (non-empty, within length limit)
        3. Sends SMS via provider
        4. Logs to audit trail (metadata only, no content)

        Args:
            message: OutboundMessage to send

        Returns:
            SendResult with success status and details

        Validation Rules:
            - to (user_key): Must be valid E.164 format (+ followed by digits)
            - text: Must be non-empty
            - text: Must be <= max_length characters
            - type: Must be MessageType.TEXT (SMS only supports text)

        Audit Logging:
            Only metadata is logged:
            - to_number_hash: SHA256 hash of recipient number (privacy)
            - provider: Provider name
            - message_sid: Provider's message ID
            - status: Send status (success/failure)
            - latency_ms: Time taken to send
            - segments_count: Number of SMS segments
            - cost: Cost if available from provider

        Security & Privacy:
            - Message text is NEVER logged to audit trail
            - Phone numbers are hashed before logging
            - Provider credentials are not exposed in logs
        """
        start_ms = utc_now_ms()

        # Validate message type
        if message.type != MessageType.TEXT:
            error_msg = f"SMS only supports text messages, got: {message.type.value}"
            logger.warning(f"SMS send validation failed: {error_msg}")
            return SendResult(
                success=False,
                error_code="INVALID_TYPE",
                error_message=error_msg
            )

        # Extract and validate recipient phone number
        to_number = message.user_key
        if not to_number:
            error_msg = "Missing recipient phone number (user_key)"
            logger.warning(f"SMS send validation failed: {error_msg}")
            return SendResult(
                success=False,
                error_code="MISSING_TO",
                error_message=error_msg
            )

        # Validate E.164 format
        if not self._is_valid_e164(to_number):
            error_msg = (
                f"Invalid phone number format: {to_number}. "
                f"Must be E.164 format (e.g., +15551234567)"
            )
            logger.warning(f"SMS send validation failed: {error_msg}")
            return SendResult(
                success=False,
                error_code="INVALID_E164",
                error_message=error_msg
            )

        # Validate message text
        text = message.text
        if not text:
            error_msg = "Message text is empty"
            logger.warning(f"SMS send validation failed: {error_msg}")
            return SendResult(
                success=False,
                error_code="EMPTY_TEXT",
                error_message=error_msg
            )

        # Validate message length
        if len(text) > self.max_length:
            error_msg = (
                f"Message text exceeds max length: {len(text)} > {self.max_length}. "
                f"Please shorten the message or increase max_length setting."
            )
            logger.warning(f"SMS send validation failed: {error_msg}")
            return SendResult(
                success=False,
                error_code="TEXT_TOO_LONG",
                error_message=error_msg
            )

        # Send SMS via provider
        logger.info(
            f"Sending SMS: channel={self.channel_id}, to={self._mask_phone(to_number)}, "
            f"length={len(text)}"
        )

        try:
            result = self.provider.send_sms(
                to_number=to_number,
                message_text=text,
                max_segments=self._calculate_max_segments(self.max_length)
            )

            # Calculate latency
            end_ms = utc_now_ms()
            latency_ms = end_ms - start_ms

            # Log result
            if result.success:
                logger.info(
                    f"SMS sent successfully: sid={result.message_sid}, "
                    f"segments={result.segments_count}, latency={latency_ms}ms"
                )
            else:
                logger.error(
                    f"SMS send failed: code={result.error_code}, "
                    f"message={result.error_message}, latency={latency_ms}ms"
                )

            # Audit log (metadata only, no message content)
            if self.audit_store:
                try:
                    self._audit_log_send(
                        to_number=to_number,
                        result=result,
                        latency_ms=latency_ms
                    )
                except Exception as e:
                    logger.warning(f"Failed to write audit log: {e}")
                    # Don't fail the send operation due to audit logging error

            return result

        except Exception as e:
            end_ms = utc_now_ms()
            latency_ms = end_ms - start_ms

            error_msg = f"Unexpected error sending SMS: {str(e)}"
            logger.exception(error_msg)

            return SendResult(
                success=False,
                error_code="PROVIDER_ERROR",
                error_message=error_msg,
                timestamp=end_ms
            )

    def _is_valid_e164(self, phone_number: str) -> bool:
        """Validate phone number is in E.164 format.

        E.164 format: + followed by country code and number
        - Starts with +
        - Followed by 1-15 digits
        - Total length: 2-16 characters

        Examples:
            - Valid: +1234567890, +442071838750, +8613800138000
            - Invalid: 1234567890, +0123456789, +123 456 7890

        Args:
            phone_number: Phone number string to validate

        Returns:
            True if valid E.164 format, False otherwise
        """
        if not phone_number:
            return False
        return E164_REGEX.match(phone_number) is not None

    def _calculate_max_segments(self, max_length: int) -> int:
        """Calculate maximum SMS segments from max length.

        SMS segment calculation:
        - Single segment: 160 characters
        - Multi-segment: 153 characters per segment (7 chars for concatenation header)

        Args:
            max_length: Maximum message length in characters

        Returns:
            Maximum number of segments to allow
        """
        if max_length <= 160:
            return 1
        else:
            # Multi-segment: 153 chars per segment
            return (max_length + 152) // 153  # Ceiling division

    def _mask_phone(self, phone_number: str) -> str:
        """Mask phone number for logging (privacy).

        Masks all but the last 4 digits.
        Example: +15551234567 -> +1******4567

        Args:
            phone_number: Phone number to mask

        Returns:
            Masked phone number string
        """
        if len(phone_number) <= 4:
            return "****"
        return phone_number[:2] + "*" * (len(phone_number) - 6) + phone_number[-4:]

    def _hash_phone(self, phone_number: str) -> str:
        """Hash phone number for audit logging (privacy).

        Uses SHA256 to create a one-way hash. This allows:
        - Tracking sends to the same number (collision detection)
        - Privacy: Original number cannot be recovered from hash

        Args:
            phone_number: Phone number to hash

        Returns:
            Hex-encoded SHA256 hash
        """
        return hashlib.sha256(phone_number.encode('utf-8')).hexdigest()

    def _audit_log_send(
        self,
        to_number: str,
        result: SendResult,
        latency_ms: int
    ) -> None:
        """Write audit log entry for SMS send.

        Logs metadata only - message content is NEVER logged.

        Args:
            to_number: Recipient phone number
            result: SendResult from provider
            latency_ms: Time taken to send in milliseconds
        """
        if not self.audit_store:
            return

        # Hash phone number for privacy
        to_hash = self._hash_phone(to_number)

        # Build audit metadata
        audit_metadata = {
            "to_hash": to_hash,
            "provider": self.provider.__class__.__name__,
            "message_sid": result.message_sid,
            "success": result.success,
            "error_code": result.error_code,
            "error_message": result.error_message,
            "latency_ms": latency_ms,
            "segments_count": result.segments_count,
            "cost": result.cost,
        }

        # Create a minimal OutboundMessage for audit logging
        # Note: We don't include the actual message text
        from agentos.communicationos.models import OutboundMessage
        audit_message = OutboundMessage(
            channel_id=self.channel_id,
            user_key=to_number,
            conversation_key=to_number,  # Same as user_key for SMS
            type=MessageType.TEXT,
            text="<redacted>",  # Don't log actual content
            metadata={"audit_only": True}
        )

        # Log to audit store
        from agentos.communicationos.message_bus import ProcessingStatus
        status = ProcessingStatus.STOP if result.success else ProcessingStatus.ERROR

        self.audit_store.log_outbound(
            message=audit_message,
            status=status,
            metadata=audit_metadata
        )

    def send_test_message(self, test_to_number: str) -> tuple[bool, Optional[str]]:
        """Send a test SMS message.

        This is a convenience method for testing the SMS configuration.
        Used by the setup wizard and connection test endpoint.

        Args:
            test_to_number: Phone number to send test message to (E.164 format)

        Returns:
            Tuple of (success, error_message)
            - (True, None) if test message sent successfully
            - (False, error_message) if test failed
        """
        # Create a test OutboundMessage
        test_message = OutboundMessage(
            channel_id=self.channel_id,
            user_key=test_to_number,
            conversation_key=test_to_number,
            type=MessageType.TEXT,
            text="AgentOS SMS Test: Connection successful! Your SMS channel is working.",
            metadata={"test": True}
        )

        # Send via handle_outbound
        result = self.handle_outbound(test_message)

        if result.success:
            return True, None
        else:
            error_msg = result.error_message or "Unknown error"
            if result.error_code:
                error_msg = f"[{result.error_code}] {error_msg}"
            return False, error_msg

    # ========================================================================
    # Inbound Webhook Support
    # ========================================================================

    def verify_twilio_signature(
        self,
        url: str,
        post_data: Dict[str, str],
        signature: str
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
        """
        if not self.webhook_auth_token:
            logger.error("webhook_auth_token not configured - cannot verify signature")
            return False

        # Build data string: URL + sorted parameters
        # Format: https://example.com/webhook?From=+1234&To=+5678 (but as key+value concatenation)
        sorted_params = sorted(post_data.items())
        data_string = url + ''.join(f"{k}{v}" for k, v in sorted_params)

        # Compute HMAC-SHA1
        computed_sig = hmac.new(
            self.webhook_auth_token.encode('utf-8'),
            data_string.encode('utf-8'),
            hashlib.sha1
        ).digest()

        # Base64 encode
        computed_sig_b64 = base64.b64encode(computed_sig).decode('ascii')

        # Constant-time comparison (prevents timing attacks)
        is_valid = compare_digest(computed_sig_b64, signature)

        if not is_valid:
            logger.warning(
                f"Invalid Twilio signature for webhook. "
                f"Expected: {computed_sig_b64[:10]}..., Got: {signature[:10]}..."
            )

        return is_valid

    def parse_inbound_webhook(
        self,
        post_data: Dict[str, str]
    ) -> Optional[InboundMessage]:
        """Parse Twilio inbound webhook data into InboundMessage.

        Twilio sends webhook POST requests with form-encoded data containing
        SMS details. This method converts that into our unified format.

        Args:
            post_data: Dictionary of webhook POST parameters

        Returns:
            InboundMessage if valid and not duplicate, None otherwise

        Webhook Fields (Twilio):
            - MessageSid: Unique message ID (e.g., "SM...")
            - From: Sender phone number (E.164 format, e.g., "+15551234567")
            - To: Recipient phone number (E.164 format)
            - Body: Message text content
            - NumMedia: Number of media attachments (v1 ignores media)

        Idempotency:
            Uses in-memory MessageSid tracking to prevent duplicate processing.
            Tracks up to 10,000 recent MessageSids.

        Security:
            Call verify_twilio_signature() BEFORE calling this method.
        """
        message_sid = post_data.get('MessageSid')
        from_number = post_data.get('From')
        to_number = post_data.get('To')
        body = post_data.get('Body', '')

        # Validate required fields
        if not all([message_sid, from_number, to_number]):
            logger.warning(
                f"Missing required fields in Twilio webhook: "
                f"MessageSid={message_sid}, From={from_number}, To={to_number}"
            )
            return None

        # Idempotent deduplication
        if message_sid in self._processed_message_sids:
            logger.info(f"Duplicate MessageSid detected: {message_sid} - ignoring")
            return None

        # Record MessageSid (memory management)
        self._processed_message_sids.add(message_sid)
        if len(self._processed_message_sids) > self._max_tracked_sids:
            # Remove oldest half when limit exceeded
            to_remove = len(self._processed_message_sids) - (self._max_tracked_sids // 2)
            # Convert to list to remove items (sets don't preserve order, so this is approximate)
            sids_list = list(self._processed_message_sids)
            for sid in sids_list[:to_remove]:
                self._processed_message_sids.discard(sid)
            logger.debug(f"Pruned {to_remove} old MessageSids from tracking set")

        # Log inbound (mask phone numbers)
        logger.info(
            f"Received SMS: from={self._mask_phone(from_number)}, "
            f"to={self._mask_phone(to_number)}, length={len(body)}, sid={message_sid}"
        )

        # Construct InboundMessage
        return InboundMessage(
            channel_id=self.channel_id,
            user_key=from_number,  # E.164 phone number
            conversation_key=from_number,  # SMS is 1:1, use sender as conversation key
            message_id=message_sid,  # Twilio's unique message ID
            timestamp=utc_now(),
            type=MessageType.TEXT,
            text=body,
            metadata={
                'twilio_from': from_number,
                'twilio_to': to_number,
                'twilio_message_sid': message_sid,
                'twilio_num_media': post_data.get('NumMedia', '0')
            }
        )
