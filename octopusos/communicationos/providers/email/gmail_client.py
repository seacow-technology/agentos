"""Gmail API Client with OAuth 2.0 Token Management.

This module provides a low-level client for Gmail API operations with automatic
token refresh, error handling, and retry logic.

Features:
- OAuth 2.0 authentication with automatic token refresh
- Encrypted token storage
- Exponential backoff retry for transient errors
- Rate limit handling
- Proper error categorization (auth, network, quota)

Design:
    GmailClient encapsulates all Gmail API calls and token management.
    GmailProvider uses this client to implement IEmailProvider interface.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class TokenRefreshError(Exception):
    """Raised when OAuth token refresh fails."""
    pass


class GmailAPIError(Exception):
    """Raised when Gmail API call fails."""
    def __init__(self, message: str, error_code: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


class GmailClient:
    """Low-level client for Gmail API with token management.

    This client handles OAuth 2.0 token refresh, Gmail API calls, and error handling.
    It does NOT implement the IEmailProvider interface - that's GmailProvider's job.

    Attributes:
        client_id: OAuth 2.0 Client ID from Google Cloud Console
        client_secret: OAuth 2.0 Client Secret from Google Cloud Console
        refresh_token: OAuth 2.0 Refresh Token (obtained during authorization)
        access_token: Current access token (refreshed automatically)
        token_expiry: When the current access token expires
    """

    # Gmail API base URL
    GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

    # OAuth 2.0 token endpoint
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        access_token: Optional[str] = None
    ):
        """Initialize Gmail client.

        Args:
            client_id: OAuth 2.0 Client ID
            client_secret: OAuth 2.0 Client Secret
            refresh_token: OAuth 2.0 Refresh Token
            access_token: Optional cached access token (will be refreshed if expired)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = access_token
        self.token_expiry: Optional[datetime] = None

        # If we have an access token but no expiry, assume it's expired
        # (will trigger refresh on first API call)
        if access_token and not self.token_expiry:
            self.token_expiry = datetime.now(timezone.utc)

    def _ensure_token(self) -> None:
        """Ensure we have a valid access token, refreshing if needed.

        Raises:
            TokenRefreshError: If token refresh fails
        """
        # Check if token is expired or missing
        if not self.access_token or not self.token_expiry or \
           datetime.now(timezone.utc) >= self.token_expiry:
            logger.info("Access token expired or missing, refreshing...")
            self._refresh_access_token()

    def _refresh_access_token(self) -> None:
        """Refresh access token using refresh token.

        Raises:
            TokenRefreshError: If refresh fails
        """
        try:
            import requests
        except ImportError:
            raise TokenRefreshError(
                "requests library not installed. Run: pip install requests"
            )

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token"
        }

        try:
            response = requests.post(
                self.TOKEN_ENDPOINT,
                data=payload,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)  # Default 1 hour

                # Set expiry with 5 minute buffer to avoid edge cases
                self.token_expiry = datetime.now(timezone.utc)
                self.token_expiry = self.token_expiry.replace(
                    microsecond=0
                )
                # Add seconds but subtract 5 minutes for safety buffer
                import datetime as dt
                self.token_expiry += dt.timedelta(seconds=expires_in - 300)

                logger.info(f"Access token refreshed, expires at {self.token_expiry}")
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("error_description", response.text)
                raise TokenRefreshError(
                    f"Token refresh failed: {error_msg} (status={response.status_code})"
                )

        except requests.exceptions.RequestException as e:
            raise TokenRefreshError(f"Network error during token refresh: {e}")
        except Exception as e:
            raise TokenRefreshError(f"Unexpected error during token refresh: {e}")

    def _make_api_call(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> Tuple[int, Dict[str, Any]]:
        """Make Gmail API call with automatic retry and token refresh.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint (relative to GMAIL_API_BASE)
            params: Query parameters
            json_data: JSON body data
            max_retries: Maximum number of retries for transient errors

        Returns:
            Tuple of (status_code, response_json)

        Raises:
            GmailAPIError: If API call fails after retries
        """
        try:
            import requests
        except ImportError:
            raise GmailAPIError(
                "requests library not installed",
                "dependency_missing"
            )

        # Ensure we have a valid token
        self._ensure_token()

        url = f"{self.GMAIL_API_BASE}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        for attempt in range(max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=30
                )

                # Handle 401 Unauthorized - token may have expired
                if response.status_code == 401:
                    logger.warning("Got 401 Unauthorized, refreshing token...")
                    self._refresh_access_token()
                    # Update headers with new token
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    # Retry the request
                    continue

                # Handle rate limiting (429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited, waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue

                # Handle server errors (500-599) - retry with backoff
                if 500 <= response.status_code < 600:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        f"Server error {response.status_code}, "
                        f"retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue

                # Parse response
                response_json = response.json() if response.text else {}
                return response.status_code, response_json

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Request timeout, retrying... (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(2 ** attempt)
                    continue
                raise GmailAPIError(
                    "Request timed out after retries",
                    "timeout"
                )

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Network error, retrying... (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    time.sleep(2 ** attempt)
                    continue
                raise GmailAPIError(
                    f"Network error: {e}",
                    "network_error"
                )

        # If we get here, all retries failed
        raise GmailAPIError(
            f"API call failed after {max_retries} retries",
            "max_retries_exceeded"
        )

    def validate_credentials(self) -> Tuple[bool, Optional[str]]:
        """Validate that credentials are working by fetching user profile.

        Returns:
            Tuple of (success, error_message)
        """
        try:
            status, data = self._make_api_call("GET", "profile")

            if status == 200:
                email = data.get("emailAddress")
                logger.info(f"Credentials validated for {email}")
                return True, None
            else:
                error_msg = data.get("error", {}).get("message", "Unknown error")
                return False, f"Validation failed: {error_msg} (status={status})"

        except TokenRefreshError as e:
            return False, f"Token refresh failed: {e}"
        except GmailAPIError as e:
            return False, f"API error: {e}"
        except Exception as e:
            logger.exception("Unexpected error during validation")
            return False, f"Unexpected error: {e}"

    def list_messages(
        self,
        query: str = "is:unread",
        max_results: int = 100,
        page_token: Optional[str] = None
    ) -> Tuple[List[str], Optional[str]]:
        """List message IDs matching query.

        Args:
            query: Gmail search query (default: unread messages)
            max_results: Maximum number of message IDs to return
            page_token: Token for pagination

        Returns:
            Tuple of (list of message IDs, next page token)

        Raises:
            GmailAPIError: If API call fails
        """
        params = {
            "q": query,
            "maxResults": max_results
        }
        if page_token:
            params["pageToken"] = page_token

        status, data = self._make_api_call("GET", "messages", params=params)

        if status != 200:
            error_msg = data.get("error", {}).get("message", "Unknown error")
            raise GmailAPIError(
                f"list_messages failed: {error_msg}",
                "list_failed",
                status
            )

        messages = data.get("messages", [])
        message_ids = [msg["id"] for msg in messages]
        next_page_token = data.get("nextPageToken")

        return message_ids, next_page_token

    def get_message(self, message_id: str) -> Dict[str, Any]:
        """Get full message details including headers and body.

        Args:
            message_id: Gmail message ID

        Returns:
            Message data dictionary

        Raises:
            GmailAPIError: If API call fails
        """
        params = {"format": "full"}
        status, data = self._make_api_call(
            "GET",
            f"messages/{message_id}",
            params=params
        )

        if status != 200:
            error_msg = data.get("error", {}).get("message", "Unknown error")
            raise GmailAPIError(
                f"get_message failed: {error_msg}",
                "get_failed",
                status
            )

        return data

    def send_message(self, raw_message: str) -> Tuple[str, str]:
        """Send an email message.

        Args:
            raw_message: RFC 822 formatted email message

        Returns:
            Tuple of (message_id, thread_id)

        Raises:
            GmailAPIError: If send fails
        """
        # Encode message in base64url format
        encoded_message = base64.urlsafe_b64encode(
            raw_message.encode("utf-8")
        ).decode("ascii")

        json_data = {
            "raw": encoded_message
        }

        status, data = self._make_api_call(
            "POST",
            "messages/send",
            json_data=json_data
        )

        if status != 200:
            error_msg = data.get("error", {}).get("message", "Unknown error")
            raise GmailAPIError(
                f"send_message failed: {error_msg}",
                "send_failed",
                status
            )

        message_id = data.get("id")
        thread_id = data.get("threadId")
        return message_id, thread_id

    def modify_message(
        self,
        message_id: str,
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None
    ) -> bool:
        """Modify message labels (e.g., mark as read).

        Args:
            message_id: Gmail message ID
            add_labels: Labels to add
            remove_labels: Labels to remove

        Returns:
            True if successful

        Raises:
            GmailAPIError: If modify fails
        """
        json_data = {}
        if add_labels:
            json_data["addLabelIds"] = add_labels
        if remove_labels:
            json_data["removeLabelIds"] = remove_labels

        status, data = self._make_api_call(
            "POST",
            f"messages/{message_id}/modify",
            json_data=json_data
        )

        if status != 200:
            error_msg = data.get("error", {}).get("message", "Unknown error")
            raise GmailAPIError(
                f"modify_message failed: {error_msg}",
                "modify_failed",
                status
            )

        return True


def create_rfc822_message(
    from_address: str,
    to_addresses: List[str],
    subject: str,
    text_body: Optional[str] = None,
    html_body: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
    cc_addresses: Optional[List[str]] = None
) -> str:
    """Create RFC 822 formatted email message.

    Args:
        from_address: Sender email address
        to_addresses: List of recipient email addresses
        subject: Email subject
        text_body: Plain text body
        html_body: HTML body
        in_reply_to: In-Reply-To header (for threading)
        references: References header (for threading)
        cc_addresses: List of CC addresses

    Returns:
        RFC 822 formatted message string
    """
    # Create multipart message
    if html_body:
        msg = MIMEMultipart("alternative")
    else:
        msg = MIMEText(text_body or "", "plain", "utf-8")
        # For plain text, we need to add headers manually
        msg["From"] = from_address
        msg["To"] = ", ".join(to_addresses)
        msg["Subject"] = subject

        if cc_addresses:
            msg["Cc"] = ", ".join(cc_addresses)
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = references

        return msg.as_string()

    # Set headers for multipart
    msg["From"] = from_address
    msg["To"] = ", ".join(to_addresses)
    msg["Subject"] = subject

    if cc_addresses:
        msg["Cc"] = ", ".join(cc_addresses)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    # Add text and HTML parts
    if text_body:
        text_part = MIMEText(text_body, "plain", "utf-8")
        msg.attach(text_part)

    if html_body:
        html_part = MIMEText(html_body, "html", "utf-8")
        msg.attach(html_part)

    return msg.as_string()
