"""SMS Provider Protocol and Data Models.

This module defines the interface contract for SMS providers (e.g., Twilio, AWS SNS, etc.)
and standardized data models for SMS operations.

Design Principles:
    - Provider-agnostic: Interface works with any SMS provider
    - Type-safe: Uses Protocol for static type checking
    - Simple: Minimal interface focused on sending SMS
    - Extensible: Easy to add new providers without changing interface

Provider Implementations:
    - Twilio: See agentos.communicationos.providers.sms.twilio
    - AWS SNS: Planned for future implementation
    - Custom: Implement ISmsProvider protocol
"""

from __future__ import annotations

from typing import Protocol, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SendResult:
    """Result of an SMS send operation.

    Attributes:
        success: Whether the SMS was accepted by the provider
        message_sid: Provider's message ID (for tracking/debugging)
        error_code: Provider-specific error code (if failed)
        error_message: Human-readable error description (if failed)
        timestamp: When the send operation completed (epoch milliseconds)
        segments_count: Number of SMS segments sent (for billing)
        cost: Cost in USD (if available from provider)
    """
    success: bool
    message_sid: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: Optional[int] = None
    segments_count: int = 1
    cost: Optional[float] = None

    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            from datetime import timezone
            self.timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)


class ISmsProvider(Protocol):
    """Protocol interface for SMS providers.

    Any SMS provider implementation must satisfy this protocol.
    This allows swapping providers without changing adapter code.

    Usage:
        >>> from agentos.communicationos.providers.sms import ISmsProvider
        >>> from agentos.communicationos.providers.sms.twilio import TwilioSmsProvider
        >>>
        >>> provider: ISmsProvider = TwilioSmsProvider(
        ...     account_sid="AC...",
        ...     auth_token="...",
        ...     from_number="+15551234567"
        ... )
        >>> result = provider.send_sms(
        ...     to_number="+15559876543",
        ...     message_text="Hello from AgentOS!"
        ... )
        >>> if result.success:
        ...     print(f"SMS sent: {result.message_sid}")
    """

    def send_sms(
        self,
        to_number: str,
        message_text: str,
        from_number: Optional[str] = None,
        max_segments: int = 3,
    ) -> SendResult:
        """Send an SMS message.

        Args:
            to_number: Recipient phone number in E.164 format (e.g., +15551234567)
            message_text: Message content to send
            from_number: Override sender number (optional, uses provider default if not set)
            max_segments: Maximum SMS segments to send (default 3 = ~480 chars)

        Returns:
            SendResult with success status, message_sid, and optional error info

        Raises:
            ValueError: If to_number or message_text is invalid
            RuntimeError: If provider configuration is invalid

        Notes:
            - Messages are automatically truncated to max_segments * 160 characters
            - Each segment beyond the first incurs additional cost
            - Provider rate limits may apply
            - For send-only channels, delivery receipts are not tracked
        """
        ...

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate provider configuration.

        Returns:
            Tuple of (is_valid, error_message)
            - (True, None) if configuration is valid
            - (False, "error description") if configuration is invalid

        Checks:
            - Required credentials are present
            - Credentials format is correct
            - From number is valid E.164 format

        Note:
            This does NOT make an API call. It only validates config format.
            Use test_connection() to verify API access.
        """
        ...

    def test_connection(
        self,
        test_to_number: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """Test provider API connection and credentials.

        Args:
            test_to_number: Optional phone number to send test message to

        Returns:
            Tuple of (success, error_message)
            - (True, None) if connection test passed
            - (False, "error description") if connection test failed

        Notes:
            - If test_to_number is provided, sends a real test SMS
            - If test_to_number is None, validates credentials via API (no SMS sent)
            - Useful for setup wizard verification
            - May incur SMS charges if test message is sent
        """
        ...


from agentos.communicationos.providers.sms.twilio_provider import TwilioSmsProvider

__all__ = [
    "ISmsProvider",
    "SendResult",
    "TwilioSmsProvider",
]
