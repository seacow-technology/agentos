"""Gmail Provider Implementation.

This module implements the IEmailProvider protocol for Gmail using the Gmail API
with OAuth 2.0 authentication.

Features:
- OAuth 2.0 authentication with automatic token refresh
- Fetch unread messages with proper threading headers
- Send messages with In-Reply-To and References headers
- Mark messages as read
- Proper error handling and retry logic

Architecture:
    GmailProvider implements IEmailProvider protocol.
    Uses GmailClient for low-level Gmail API operations.
    Converts Gmail API data to EmailEnvelope standard format.

Example:
    provider = GmailProvider(
        client_id="xxx.apps.googleusercontent.com",
        client_secret="secret",
        refresh_token="refresh_token",
        email_address="user@gmail.com"
    )

    # Validate credentials
    result = provider.validate_credentials()
    if not result.valid:
        print(f"Validation failed: {result.error_message}")

    # Fetch messages
    messages = provider.fetch_messages(folder="INBOX", limit=10)
    for msg in messages:
        print(f"{msg.from_address}: {msg.subject}")

    # Send reply
    result = provider.send_message(
        to_addresses=["recipient@example.com"],
        subject="Re: Question",
        text_body="Thank you for your question...",
        in_reply_to="<msg-001@example.com>",
        references="<msg-001@example.com>"
    )
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Any

from agentos.communicationos.providers.email import (
    EmailEnvelope,
    ValidationResult,
    SendResult,
    parse_email_address
)
from agentos.communicationos.providers.email.gmail_client import (
    GmailClient,
    GmailAPIError,
    TokenRefreshError,
    create_rfc822_message
)

logger = logging.getLogger(__name__)


class GmailProvider:
    """Gmail email provider implementation using Gmail API.

    This provider implements the IEmailProvider protocol for Gmail accounts
    using OAuth 2.0 authentication and the Gmail API.

    Attributes:
        client: GmailClient instance for API operations
        email_address: User's email address
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        email_address: str,
        access_token: Optional[str] = None
    ):
        """Initialize Gmail provider.

        Args:
            client_id: OAuth 2.0 Client ID from Google Cloud Console
            client_secret: OAuth 2.0 Client Secret
            refresh_token: OAuth 2.0 Refresh Token
            email_address: User's Gmail address
            access_token: Optional cached access token
        """
        self.client = GmailClient(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            access_token=access_token
        )
        self.email_address = email_address

    def validate_credentials(self) -> ValidationResult:
        """Validate Gmail credentials by calling Gmail API.

        Returns:
            ValidationResult with success status and any error details
        """
        try:
            success, error_msg = self.client.validate_credentials()

            if success:
                return ValidationResult(
                    valid=True,
                    metadata={"email_address": self.email_address}
                )
            else:
                return ValidationResult(
                    valid=False,
                    error_message=error_msg,
                    error_code="validation_failed"
                )

        except TokenRefreshError as e:
            return ValidationResult(
                valid=False,
                error_message=f"Token refresh failed: {e}",
                error_code="token_refresh_failed"
            )
        except Exception as e:
            logger.exception("Unexpected error during credential validation")
            return ValidationResult(
                valid=False,
                error_message=f"Unexpected error: {e}",
                error_code="unexpected_error"
            )

    def fetch_messages(
        self,
        folder: str = "INBOX",
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[EmailEnvelope]:
        """Fetch new messages from Gmail.

        Args:
            folder: Mailbox folder (Gmail ignores this, uses labels)
            since: Only fetch messages after this time (optional)
            limit: Maximum number of messages to fetch

        Returns:
            List of EmailEnvelope objects

        Raises:
            GmailAPIError: If fetch operation fails
        """
        # Build Gmail search query
        query_parts = ["is:unread"]

        # Add date filter if provided
        if since:
            # Gmail uses YYYY/MM/DD format for date searches
            date_str = since.strftime("%Y/%m/%d")
            query_parts.append(f"after:{date_str}")

        query = " ".join(query_parts)

        try:
            # Get message IDs
            message_ids, _ = self.client.list_messages(
                query=query,
                max_results=limit
            )

            logger.info(f"Found {len(message_ids)} messages matching query: {query}")

            # Fetch full message details for each ID
            envelopes = []
            for msg_id in message_ids:
                try:
                    msg_data = self.client.get_message(msg_id)
                    envelope = self._parse_message_to_envelope(msg_data)
                    envelopes.append(envelope)
                except Exception as e:
                    logger.error(
                        f"Failed to parse message {msg_id}: {e}",
                        exc_info=True
                    )
                    # Continue with other messages
                    continue

            logger.info(f"Successfully parsed {len(envelopes)} messages")
            return envelopes

        except GmailAPIError as e:
            logger.error(f"Gmail API error: {e}")
            raise
        except Exception as e:
            logger.exception("Unexpected error fetching messages")
            raise

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
        """Send an email message via Gmail API.

        Args:
            to_addresses: List of recipient email addresses
            subject: Email subject
            text_body: Plain text body
            html_body: HTML body
            in_reply_to: In-Reply-To header for threading
            references: References header for threading
            cc_addresses: CC recipients
            attachments: Attachments (not yet implemented)

        Returns:
            SendResult with success status and message IDs
        """
        try:
            # Create RFC 822 message
            raw_message = create_rfc822_message(
                from_address=self.email_address,
                to_addresses=to_addresses,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
                in_reply_to=in_reply_to,
                references=references,
                cc_addresses=cc_addresses
            )

            # Send via Gmail API
            message_id, thread_id = self.client.send_message(raw_message)

            logger.info(
                f"Message sent successfully: message_id={message_id}, "
                f"thread_id={thread_id}"
            )

            return SendResult(
                success=True,
                provider_message_id=message_id,
                message_id=self._extract_message_id_from_raw(raw_message),
                metadata={
                    "thread_id": thread_id,
                    "gmail_message_id": message_id
                }
            )

        except GmailAPIError as e:
            logger.error(f"Failed to send message: {e}")
            return SendResult(
                success=False,
                error_message=str(e),
                error_code=e.error_code
            )
        except Exception as e:
            logger.exception("Unexpected error sending message")
            return SendResult(
                success=False,
                error_message=f"Unexpected error: {e}",
                error_code="unexpected_error"
            )

    def mark_as_read(self, provider_message_id: str) -> bool:
        """Mark a Gmail message as read.

        Args:
            provider_message_id: Gmail message ID

        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove UNREAD label
            self.client.modify_message(
                message_id=provider_message_id,
                remove_labels=["UNREAD"]
            )
            logger.info(f"Marked message as read: {provider_message_id}")
            return True

        except GmailAPIError as e:
            logger.error(f"Failed to mark message as read: {e}")
            return False
        except Exception as e:
            logger.exception("Unexpected error marking message as read")
            return False

    def _parse_message_to_envelope(self, msg_data: Dict[str, Any]) -> EmailEnvelope:
        """Parse Gmail API message data to EmailEnvelope.

        Args:
            msg_data: Gmail API message object

        Returns:
            EmailEnvelope instance

        Raises:
            ValueError: If required fields are missing
        """
        # Extract provider message ID
        provider_message_id = msg_data.get("id")
        if not provider_message_id:
            raise ValueError("Missing message ID in Gmail API response")

        # Extract headers
        payload = msg_data.get("payload", {})
        headers = payload.get("headers", [])
        headers_dict = {h["name"].lower(): h["value"] for h in headers}

        # Extract required headers
        message_id = headers_dict.get("message-id")
        from_header = headers_dict.get("from", "")
        to_header = headers_dict.get("to", "")
        subject = headers_dict.get("subject", "")
        date_header = headers_dict.get("date")

        if not message_id:
            raise ValueError(f"Missing Message-ID header for message {provider_message_id}")

        # Parse From header
        from_name, from_address = parse_email_address(from_header)

        # Parse To header (can be comma-separated)
        to_addresses = []
        if to_header:
            for addr in to_header.split(","):
                _, email = parse_email_address(addr.strip())
                if email:
                    to_addresses.append(email)

        # Parse CC header
        cc_addresses = []
        cc_header = headers_dict.get("cc", "")
        if cc_header:
            for addr in cc_header.split(","):
                _, email = parse_email_address(addr.strip())
                if email:
                    cc_addresses.append(email)

        # Parse date header
        date = self._parse_date_header(date_header)

        # Extract threading headers
        in_reply_to = headers_dict.get("in-reply-to")
        references = headers_dict.get("references")

        # Extract body
        text_body, html_body = self._extract_body(payload)

        # Create envelope
        envelope = EmailEnvelope(
            provider_message_id=provider_message_id,
            message_id=message_id,
            in_reply_to=in_reply_to,
            references=references,
            from_address=from_address,
            from_name=from_name,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            subject=subject,
            date=date,
            text_body=text_body,
            html_body=html_body,
            attachments=[],  # TODO: Parse attachments
            raw_headers=headers_dict,
            thread_hint=None  # Will be computed by compute_thread_root()
        )

        return envelope

    def _extract_body(self, payload: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """Extract text and HTML body from Gmail message payload.

        Gmail uses a nested MIME structure. This method recursively searches
        for text/plain and text/html parts.

        Args:
            payload: Gmail message payload object

        Returns:
            Tuple of (text_body, html_body)
        """
        text_body = None
        html_body = None

        # Check if payload has body data directly
        if "body" in payload and payload["body"].get("data"):
            mime_type = payload.get("mimeType", "")
            body_data = payload["body"]["data"]
            decoded_body = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

            if mime_type == "text/plain":
                text_body = decoded_body
            elif mime_type == "text/html":
                html_body = decoded_body

        # Check if payload has parts (multipart message)
        if "parts" in payload:
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")

                # Recursively handle nested multipart
                if mime_type.startswith("multipart/"):
                    nested_text, nested_html = self._extract_body(part)
                    if nested_text and not text_body:
                        text_body = nested_text
                    if nested_html and not html_body:
                        html_body = nested_html
                    continue

                # Extract body data
                if "body" in part and part["body"].get("data"):
                    body_data = part["body"]["data"]
                    decoded_body = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

                    if mime_type == "text/plain" and not text_body:
                        text_body = decoded_body
                    elif mime_type == "text/html" and not html_body:
                        html_body = decoded_body

        return text_body, html_body

    def _parse_date_header(self, date_header: Optional[str]) -> datetime:
        """Parse email Date header to timezone-aware datetime.

        Args:
            date_header: RFC 5322 date string

        Returns:
            Timezone-aware datetime in UTC

        Raises:
            ValueError: If date cannot be parsed
        """
        if not date_header:
            # Fallback to current time if Date header missing
            logger.warning("Missing Date header, using current time")
            return datetime.now(timezone.utc)

        try:
            # parsedate_to_datetime handles RFC 5322 format
            dt = parsedate_to_datetime(date_header)

            # Ensure timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            # Convert to UTC
            return dt.astimezone(timezone.utc)

        except Exception as e:
            logger.error(f"Failed to parse date header '{date_header}': {e}")
            # Fallback to current time
            return datetime.now(timezone.utc)

    def _extract_message_id_from_raw(self, raw_message: str) -> Optional[str]:
        """Extract Message-ID header from raw RFC 822 message.

        Args:
            raw_message: RFC 822 formatted message

        Returns:
            Message-ID value (without angle brackets) or None
        """
        try:
            for line in raw_message.split("\n"):
                if line.lower().startswith("message-id:"):
                    msg_id = line.split(":", 1)[1].strip()
                    # Remove angle brackets if present
                    return msg_id.strip("<>")
        except Exception as e:
            logger.error(f"Failed to extract Message-ID: {e}")

        return None


def generate_auth_url(
    client_id: str,
    redirect_uri: str = "http://localhost:8080/oauth2callback",
    scopes: Optional[List[str]] = None
) -> str:
    """Generate OAuth 2.0 authorization URL for user consent.

    Args:
        client_id: OAuth 2.0 Client ID
        redirect_uri: OAuth redirect URI (default: localhost)
        scopes: List of Gmail API scopes (default: read/send)

    Returns:
        Authorization URL for user to visit

    Example:
        url = generate_auth_url(client_id="xxx.apps.googleusercontent.com")
        print(f"Visit this URL to authorize: {url}")
        # User visits URL, authorizes app, gets redirected to redirect_uri with code
        # Exchange code for refresh_token using exchange_code_for_tokens()
    """
    if scopes is None:
        scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send"
        ]

    import urllib.parse
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",  # Request refresh token
        "prompt": "consent"  # Force consent screen to get refresh token
    }

    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str = "http://localhost:8080/oauth2callback"
) -> Dict[str, str]:
    """Exchange authorization code for access and refresh tokens.

    Args:
        client_id: OAuth 2.0 Client ID
        client_secret: OAuth 2.0 Client Secret
        code: Authorization code from redirect
        redirect_uri: OAuth redirect URI (must match auth URL)

    Returns:
        Dictionary with access_token, refresh_token, expires_in

    Raises:
        Exception: If token exchange fails

    Example:
        tokens = exchange_code_for_tokens(
            client_id="xxx.apps.googleusercontent.com",
            client_secret="secret",
            code="4/0Xxx..."
        )
        refresh_token = tokens["refresh_token"]  # Store this securely
    """
    try:
        import requests
    except ImportError:
        raise Exception("requests library not installed. Run: pip install requests")

    token_endpoint = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }

    response = requests.post(token_endpoint, data=payload, timeout=10)

    if response.status_code == 200:
        return response.json()
    else:
        error_data = response.json() if response.text else {}
        error_msg = error_data.get("error_description", response.text)
        raise Exception(f"Token exchange failed: {error_msg} (status={response.status_code})")
