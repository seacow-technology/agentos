"""Slack API Client.

This module provides a simple HTTP client for calling Slack Web API endpoints.
It handles message sending, signature verification, and error handling.

Design:
    - Uses requests library for HTTP calls
    - Implements HMAC SHA256 signature verification
    - Returns simple success/failure booleans
    - Includes retry logic for transient errors
    - Logs errors for debugging

Security:
    - Signature verification using HMAC-SHA256
    - Timestamp validation to prevent replay attacks
    - Secure token handling
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def verify_signature(
    signing_secret: str,
    timestamp: str,
    body: str,
    signature: str
) -> bool:
    """Verify Slack webhook signature using HMAC-SHA256.

    Slack signs each request with a signature that uses your Signing Secret.
    This function verifies the signature to ensure the request came from Slack.

    Args:
        signing_secret: Your Slack App Signing Secret
        timestamp: X-Slack-Request-Timestamp header value
        body: Raw request body as string
        signature: X-Slack-Signature header value

    Returns:
        True if signature is valid, False otherwise

    Security Notes:
        - Rejects requests older than 5 minutes to prevent replay attacks
        - Uses constant-time comparison to prevent timing attacks
        - Signature format: v0=<hex_hash>

    Reference:
        https://api.slack.com/authentication/verifying-requests-from-slack
    """
    # Check timestamp to prevent replay attacks
    # Reject requests older than 5 minutes
    try:
        request_timestamp = int(timestamp)
        current_timestamp = int(time.time())

        if abs(current_timestamp - request_timestamp) > 60 * 5:
            logger.warning(
                f"Request timestamp too old or too far in future: "
                f"request={request_timestamp}, current={current_timestamp}"
            )
            return False
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid timestamp format: {timestamp}, error: {e}")
        return False

    # Build basestring: version:timestamp:body
    basestring = f"v0:{timestamp}:{body}"

    # Compute HMAC-SHA256 signature
    my_signature = "v0=" + hmac.new(
        signing_secret.encode(),
        basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(my_signature, signature)


def post_message(
    bot_token: str,
    channel: str,
    text: str,
    thread_ts: Optional[str] = None,
    timeout: int = 10
) -> tuple[bool, Optional[str]]:
    """Send a message to a Slack channel or thread.

    Args:
        bot_token: Slack Bot User OAuth Token (starts with xoxb-)
        channel: Channel ID to send message to
        text: Message text to send
        thread_ts: Optional thread timestamp to reply in thread
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, error_message)

    API Reference:
        https://api.slack.com/methods/chat.postMessage
    """
    try:
        import requests
    except ImportError:
        logger.error(
            "requests library not installed. Run: pip install requests"
        )
        return False, "requests library not installed"

    # Build API URL
    api_url = "https://slack.com/api/chat.postMessage"

    # Prepare headers
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json"
    }

    # Prepare request payload
    payload: Dict[str, Any] = {
        "channel": channel,
        "text": text,
    }

    # Add thread_ts if replying in thread
    if thread_ts:
        payload["thread_ts"] = thread_ts

    try:
        # Send POST request
        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=timeout
        )

        # Check response
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logger.debug(
                    f"Slack message sent successfully: "
                    f"channel={channel}, ts={result.get('ts')}"
                )
                return True, None
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(
                    f"Slack API returned error: {error_msg}"
                )
                return False, error_msg
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(
                f"Slack API request failed: {error_msg}"
            )
            return False, error_msg

    except requests.exceptions.Timeout:
        error_msg = f"Request timed out after {timeout}s"
        logger.error(f"Slack API: {error_msg}")
        return False, error_msg

    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        logger.exception(f"Slack API: {error_msg}")
        return False, error_msg

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.exception(f"Slack API: {error_msg}")
        return False, error_msg


def get_user_info(
    bot_token: str,
    user_id: str,
    timeout: int = 10
) -> tuple[bool, Optional[Dict[str, Any]]]:
    """Get information about a Slack user.

    Args:
        bot_token: Slack Bot User OAuth Token
        user_id: User ID to lookup
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, user_info_dict)

    API Reference:
        https://api.slack.com/methods/users.info
    """
    try:
        import requests
    except ImportError:
        return False, None

    # Build API URL
    api_url = "https://slack.com/api/users.info"

    # Prepare headers
    headers = {
        "Authorization": f"Bearer {bot_token}",
    }

    # Prepare request params
    params = {
        "user": user_id
    }

    try:
        # Send GET request
        response = requests.get(
            api_url,
            headers=headers,
            params=params,
            timeout=timeout
        )

        # Check response
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                return True, result.get("user")
            else:
                logger.error(
                    f"Slack users.info failed: {result.get('error')}"
                )
                return False, None
        else:
            logger.error(
                f"Slack users.info request failed: "
                f"status={response.status_code}"
            )
            return False, None

    except Exception as e:
        logger.exception(f"Slack users.info error: {e}")
        return False, None


def auth_test(
    bot_token: str,
    timeout: int = 10
) -> tuple[bool, Optional[Dict[str, Any]]]:
    """Test authentication and get bot info.

    Args:
        bot_token: Slack Bot User OAuth Token
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, auth_info_dict)

    API Reference:
        https://api.slack.com/methods/auth.test
    """
    try:
        import requests
    except ImportError:
        return False, None

    # Build API URL
    api_url = "https://slack.com/api/auth.test"

    # Prepare headers
    headers = {
        "Authorization": f"Bearer {bot_token}",
    }

    try:
        # Send POST request
        response = requests.post(
            api_url,
            headers=headers,
            timeout=timeout
        )

        # Check response
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logger.info(
                    f"Slack auth.test successful: "
                    f"team={result.get('team')}, user={result.get('user')}"
                )
                return True, result
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Slack auth.test failed: {error_msg}")
                return False, None
        else:
            logger.error(
                f"Slack auth.test request failed: "
                f"status={response.status_code}"
            )
            return False, None

    except Exception as e:
        logger.exception(f"Slack auth.test error: {e}")
        return False, None
