"""Email Provider Protocol and Data Models.

This module defines the IEmailProvider protocol interface that all email providers
(Gmail, Outlook, SMTP/IMAP) must implement. It also defines standardized data models
for email envelopes, validation results, and send results.

Design Principles:
- Provider-agnostic: Works with any email provider (OAuth or SMTP/IMAP)
- Thread-aware: Properly handles Message-ID, References, In-Reply-To headers
- Type-safe: Pydantic models ensure data validation
- Security-focused: Separate models for credentials and sensitive data

Architecture:
    EmailAdapter (channels/email/adapter.py) uses IEmailProvider to:
        1. fetch_messages(): Poll for new messages
        2. send_message(): Send outbound messages with proper threading
        3. validate_credentials(): Verify provider credentials

    Providers implement IEmailProvider:
        - GmailProvider: Uses Gmail API with OAuth 2.0
        - OutlookProvider: Uses Microsoft Graph API with OAuth 2.0
        - SmtpImapProvider: Uses standard SMTP/IMAP protocols
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol
from email.utils import parseaddr

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class EmailProviderType(str, Enum):
    """Supported email provider types.

    Attributes:
        GMAIL: Gmail with OAuth 2.0 (uses Gmail API)
        OUTLOOK: Outlook/Microsoft 365 with OAuth 2.0 (uses Microsoft Graph API)
        SMTP_IMAP: Generic SMTP/IMAP (uses standard protocols)
    """

    GMAIL = "gmail"
    OUTLOOK = "outlook"
    SMTP_IMAP = "smtp_imap"


class EmailEnvelope(BaseModel):
    """Standardized email envelope representing a single email message.

    This model represents an email in a provider-agnostic format. Email adapters
    convert provider-specific email formats to this standard structure.

    Attributes:
        provider_message_id: Provider-specific unique message ID (for marking as read, etc.)
        message_id: Standard RFC 5322 Message-ID header (globally unique)
        in_reply_to: RFC 5322 In-Reply-To header (Message-ID of parent message)
        references: RFC 5322 References header (space-separated list of Message-IDs in thread)
        from_address: Sender email address (parsed from From header)
        from_name: Sender display name (parsed from From header)
        to_addresses: List of recipient email addresses
        cc_addresses: List of CC recipient email addresses (optional)
        subject: Email subject line
        date: Email date (from Date header, timezone-aware UTC)
        text_body: Plain text body content
        html_body: HTML body content (optional)
        attachments: List of attachment metadata (filenames, content types, sizes)
        raw_headers: Dictionary of all email headers (for debugging and advanced processing)
        thread_hint: Computed thread identifier (for conversation_key mapping)
    """

    provider_message_id: str = Field(
        ...,
        description="Provider-specific message ID (e.g., Gmail msg ID, IMAP UID)"
    )

    message_id: str = Field(
        ...,
        description="RFC 5322 Message-ID header value (unique identifier)"
    )

    in_reply_to: Optional[str] = Field(
        None,
        description="RFC 5322 In-Reply-To header (Message-ID of parent message)"
    )

    references: Optional[str] = Field(
        None,
        description="RFC 5322 References header (space-separated Message-IDs)"
    )

    from_address: str = Field(
        ...,
        description="Sender email address"
    )

    from_name: Optional[str] = Field(
        None,
        description="Sender display name"
    )

    to_addresses: List[str] = Field(
        default_factory=list,
        description="List of recipient email addresses"
    )

    cc_addresses: List[str] = Field(
        default_factory=list,
        description="List of CC recipient email addresses"
    )

    subject: str = Field(
        default="",
        description="Email subject line"
    )

    date: datetime = Field(
        ...,
        description="Email date from Date header (timezone-aware UTC)"
    )

    text_body: Optional[str] = Field(
        None,
        description="Plain text body content"
    )

    html_body: Optional[str] = Field(
        None,
        description="HTML body content"
    )

    attachments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of attachment metadata (filename, content_type, size)"
    )

    raw_headers: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary of all email headers"
    )

    thread_hint: Optional[str] = Field(
        None,
        description="Computed thread identifier for conversation_key"
    )

    @field_validator('date')
    @classmethod
    def validate_date(cls, v: datetime) -> datetime:
        """Ensure date is timezone-aware and in UTC."""
        if v.tzinfo is None:
            raise ValueError("date must be timezone-aware")
        return v

    @field_validator('from_address', 'to_addresses', 'cc_addresses')
    @classmethod
    def validate_email_addresses(cls, v):
        """Validate email address format."""
        if isinstance(v, str):
            # Single email address
            if not v or '@' not in v:
                raise ValueError(f"Invalid email address: {v}")
        elif isinstance(v, list):
            # List of email addresses
            for addr in v:
                if not addr or '@' not in addr:
                    raise ValueError(f"Invalid email address in list: {addr}")
        return v

    def compute_thread_root(self) -> str:
        """Compute the thread root Message-ID for conversation_key.

        Thread Detection Algorithm:
        1. If References header exists, use the first Message-ID (oldest in thread)
        2. If only In-Reply-To exists, use that Message-ID (direct parent)
        3. If neither exists, current message_id becomes the thread root

        Returns:
            Thread root Message-ID to use as conversation_key
        """
        # Parse References header (space or newline separated Message-IDs)
        if self.references:
            # Split by whitespace and get first Message-ID
            refs = self.references.strip().split()
            if refs:
                thread_root = refs[0].strip('<>')
                logger.debug(
                    f"Thread root from References: {thread_root} "
                    f"(message_id={self.message_id})"
                )
                return thread_root

        # Fall back to In-Reply-To header
        if self.in_reply_to:
            thread_root = self.in_reply_to.strip('<>')
            logger.debug(
                f"Thread root from In-Reply-To: {thread_root} "
                f"(message_id={self.message_id})"
            )
            return thread_root

        # No threading headers - this is a new thread
        thread_root = self.message_id.strip('<>')
        logger.debug(f"New thread root: {thread_root}")
        return thread_root

    def get_reply_headers(self) -> Dict[str, str]:
        """Generate proper reply headers for sending a reply to this message.

        Returns:
            Dictionary with In-Reply-To and References headers for reply
        """
        # In-Reply-To should be the Message-ID we're replying to
        in_reply_to = f"<{self.message_id.strip('<>')}>"

        # References should include existing References + current Message-ID
        references_list = []
        if self.references:
            # Parse existing references
            refs = self.references.strip().split()
            references_list.extend([ref.strip() for ref in refs])

        # Add current message ID to references
        current_msg_id = f"<{self.message_id.strip('<>')}>"
        if current_msg_id not in references_list:
            references_list.append(current_msg_id)

        references = " ".join(references_list)

        return {
            "In-Reply-To": in_reply_to,
            "References": references
        }

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "provider_message_id": "18d4c2f1a2b3c4d5",
                    "message_id": "<CABcD1234567890@mail.gmail.com>",
                    "in_reply_to": None,
                    "references": None,
                    "from_address": "user@example.com",
                    "from_name": "John Doe",
                    "to_addresses": ["agent@example.com"],
                    "cc_addresses": [],
                    "subject": "Question about AgentOS",
                    "date": "2026-02-01T10:30:00Z",
                    "text_body": "Hello, I have a question about AgentOS...",
                    "html_body": "<p>Hello, I have a question about AgentOS...</p>",
                    "attachments": [],
                    "raw_headers": {},
                    "thread_hint": "CABcD1234567890@mail.gmail.com"
                }
            ]
        }
    }


class ValidationResult(BaseModel):
    """Result of email provider credential validation.

    Attributes:
        valid: True if credentials are valid and working
        error_message: Human-readable error message if validation failed
        error_code: Machine-readable error code (e.g., "invalid_credentials", "network_error")
        metadata: Additional provider-specific validation metadata
    """

    valid: bool = Field(
        ...,
        description="True if credentials are valid"
    )

    error_message: Optional[str] = Field(
        None,
        description="Human-readable error message if validation failed"
    )

    error_code: Optional[str] = Field(
        None,
        description="Machine-readable error code"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional provider-specific metadata"
    )


class SendResult(BaseModel):
    """Result of sending an email message.

    Attributes:
        success: True if message was sent successfully
        provider_message_id: Provider-assigned message ID (for tracking sent message)
        message_id: RFC 5322 Message-ID header value (for threading)
        error_message: Human-readable error message if send failed
        error_code: Machine-readable error code (e.g., "rate_limit", "quota_exceeded")
        metadata: Additional provider-specific send metadata
    """

    success: bool = Field(
        ...,
        description="True if message was sent successfully"
    )

    provider_message_id: Optional[str] = Field(
        None,
        description="Provider-assigned message ID"
    )

    message_id: Optional[str] = Field(
        None,
        description="RFC 5322 Message-ID header value"
    )

    error_message: Optional[str] = Field(
        None,
        description="Human-readable error message if send failed"
    )

    error_code: Optional[str] = Field(
        None,
        description="Machine-readable error code"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional provider-specific metadata"
    )


class IEmailProvider(Protocol):
    """Protocol interface that all email providers must implement.

    This protocol defines the contract for email providers. Each provider
    (GmailProvider, OutlookProvider, SmtpImapProvider) must implement these
    methods to be compatible with the EmailAdapter.

    Methods:
        validate_credentials(): Verify provider credentials are valid
        fetch_messages(): Poll for new messages since last check
        send_message(): Send an outbound message with proper threading
        mark_as_read(): Mark a message as read (optional, provider-dependent)
    """

    def validate_credentials(self) -> ValidationResult:
        """Validate that provider credentials are correct and working.

        This method should attempt to authenticate with the provider and verify
        that basic operations (read, send) are permitted.

        Returns:
            ValidationResult indicating success or failure

        Example:
            result = provider.validate_credentials()
            if result.valid:
                print("Credentials are valid")
            else:
                print(f"Validation failed: {result.error_message}")
        """
        ...

    def fetch_messages(
        self,
        folder: str = "INBOX",
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[EmailEnvelope]:
        """Fetch new messages from the provider.

        This method polls the provider for new messages since the last check.
        It should only return unread messages or messages received after 'since'.

        Args:
            folder: Mailbox folder to fetch from (default: "INBOX")
            since: Only fetch messages received after this time (UTC)
            limit: Maximum number of messages to fetch (default: 100)

        Returns:
            List of EmailEnvelope objects representing new messages

        Raises:
            Exception: If fetch operation fails (network error, auth error, etc.)

        Example:
            from datetime import datetime, timezone, timedelta
            since = datetime.now(timezone.utc) - timedelta(hours=1)
            messages = provider.fetch_messages(folder="INBOX", since=since, limit=50)
            for msg in messages:
                print(f"New message: {msg.subject} from {msg.from_address}")
        """
        ...

    def send_message(
        self,
        to_addresses: List[str],
        subject: str,
        text_body: Optional[str] = None,
        html_body: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> SendResult:
        """Send an outbound email message.

        This method sends an email with proper threading headers (In-Reply-To,
        References) to maintain conversation context.

        Args:
            to_addresses: List of recipient email addresses
            subject: Email subject line
            text_body: Plain text body content (optional)
            html_body: HTML body content (optional)
            in_reply_to: Message-ID of parent message (for threading)
            references: References header value (for threading)
            cc_addresses: List of CC recipient addresses (optional)
            attachments: List of attachment data (optional)

        Returns:
            SendResult indicating success or failure, with assigned Message-ID

        Raises:
            Exception: If send operation fails

        Example:
            result = provider.send_message(
                to_addresses=["user@example.com"],
                subject="Re: Question about AgentOS",
                text_body="Thank you for your question...",
                in_reply_to="<CABcD1234567890@mail.gmail.com>",
                references="<CABcD1234567890@mail.gmail.com>"
            )
            if result.success:
                print(f"Message sent: {result.message_id}")
            else:
                print(f"Send failed: {result.error_message}")
        """
        ...

    def mark_as_read(self, provider_message_id: str) -> bool:
        """Mark a message as read (optional, provider-dependent).

        This method marks a message as read in the provider's system. Some
        providers may not support this operation.

        Args:
            provider_message_id: Provider-specific message ID

        Returns:
            True if successfully marked as read, False otherwise

        Example:
            success = provider.mark_as_read("18d4c2f1a2b3c4d5")
            if success:
                print("Message marked as read")
        """
        ...


# Helper function to parse email addresses with display names
def parse_email_address(address_str: str) -> tuple[str, str]:
    """Parse email address string into (name, email) tuple.

    This function handles various email address formats:
    - "user@example.com" -> ("", "user@example.com")
    - "John Doe <user@example.com>" -> ("John Doe", "user@example.com")
    - "<user@example.com>" -> ("", "user@example.com")

    Args:
        address_str: Email address string to parse

    Returns:
        Tuple of (display_name, email_address)

    Example:
        name, email = parse_email_address("John Doe <john@example.com>")
        # name = "John Doe", email = "john@example.com"
    """
    name, email = parseaddr(address_str)
    return (name.strip(), email.strip().lower())


# Helper function to compute conversation key from email envelope
def compute_conversation_key(envelope: EmailEnvelope) -> str:
    """Compute conversation_key from email envelope threading headers.

    This function implements the thread detection algorithm to determine
    which conversation this email belongs to.

    Args:
        envelope: EmailEnvelope to compute conversation key for

    Returns:
        Conversation key (thread root Message-ID)

    Example:
        conv_key = compute_conversation_key(envelope)
        # conv_key = "CABcD1234567890@mail.gmail.com"
    """
    return envelope.compute_thread_root()


# Export provider implementations
try:
    from agentos.communicationos.providers.email.gmail_provider import (
        GmailProvider,
        generate_auth_url,
        exchange_code_for_tokens
    )
    _GMAIL_AVAILABLE = True
except ImportError:
    _GMAIL_AVAILABLE = False
    GmailProvider = None
    generate_auth_url = None
    exchange_code_for_tokens = None


__all__ = [
    "EmailProviderType",
    "EmailEnvelope",
    "ValidationResult",
    "SendResult",
    "IEmailProvider",
    "parse_email_address",
    "compute_conversation_key",
    "GmailProvider",
    "generate_auth_url",
    "exchange_code_for_tokens",
]
