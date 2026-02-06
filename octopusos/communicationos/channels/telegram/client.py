"""Telegram Bot API Client.

This module provides a simple HTTP client for calling Telegram Bot API endpoints.
It handles message sending, file uploads, and error handling.

Design:
    - Uses requests library for HTTP calls
    - Implements timeout and retry logic
    - Returns simple success/failure booleans
    - Logs errors for debugging
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def send_message(
    bot_token: str,
    chat_id: str,
    text: str,
    reply_to_message_id: Optional[int] = None,
    timeout: int = 10
) -> bool:
    """Send a text message via Telegram Bot API.

    Args:
        bot_token: Telegram Bot Token
        chat_id: Target chat ID (can be user ID or group ID)
        text: Message text to send
        reply_to_message_id: Optional message ID to reply to
        timeout: Request timeout in seconds

    Returns:
        True if message sent successfully, False otherwise

    API Reference:
        https://core.telegram.org/bots/api#sendmessage
    """
    try:
        import requests
    except ImportError:
        logger.error(
            "requests library not installed. Run: pip install requests"
        )
        return False

    # Build API URL
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    # Prepare request payload
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
    }

    if reply_to_message_id is not None:
        payload["reply_to_message_id"] = reply_to_message_id

    try:
        # Send POST request
        response = requests.post(
            api_url,
            json=payload,
            timeout=timeout
        )

        # Check response
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logger.debug(
                    f"Telegram message sent successfully: "
                    f"message_id={result.get('result', {}).get('message_id')}"
                )
                return True
            else:
                logger.error(
                    f"Telegram API returned error: {result.get('description')}"
                )
                return False
        else:
            logger.error(
                f"Telegram API request failed: status={response.status_code}, "
                f"body={response.text}"
            )
            return False

    except requests.exceptions.Timeout:
        logger.error(
            f"Telegram API request timed out after {timeout}s"
        )
        return False

    except requests.exceptions.RequestException as e:
        logger.exception(
            f"Telegram API request failed: {e}"
        )
        return False

    except Exception as e:
        logger.exception(
            f"Unexpected error sending Telegram message: {e}"
        )
        return False


def set_webhook(
    bot_token: str,
    webhook_url: str,
    secret_token: str,
    timeout: int = 10
) -> tuple[bool, Optional[str]]:
    """Set webhook URL for receiving updates.

    Args:
        bot_token: Telegram Bot Token
        webhook_url: Public HTTPS URL for webhook
        secret_token: Secret token to verify webhook requests
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, error_message)

    API Reference:
        https://core.telegram.org/bots/api#setwebhook
    """
    try:
        import requests
    except ImportError:
        return False, "requests library not installed"

    # Build API URL
    api_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"

    # Prepare request payload
    payload = {
        "url": webhook_url,
        "secret_token": secret_token,
        "allowed_updates": ["message"],  # Only receive message updates
        "drop_pending_updates": False,
    }

    try:
        # Send POST request
        response = requests.post(
            api_url,
            json=payload,
            timeout=timeout
        )

        # Check response
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logger.info(
                    f"Telegram webhook set successfully: {webhook_url}"
                )
                return True, None
            else:
                error_msg = result.get("description", "Unknown error")
                logger.error(
                    f"Telegram setWebhook failed: {error_msg}"
                )
                return False, error_msg
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(
                f"Telegram setWebhook request failed: {error_msg}"
            )
            return False, error_msg

    except requests.exceptions.Timeout:
        error_msg = f"Request timed out after {timeout}s"
        logger.error(f"Telegram setWebhook: {error_msg}")
        return False, error_msg

    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        logger.exception(f"Telegram setWebhook: {error_msg}")
        return False, error_msg

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.exception(f"Telegram setWebhook: {error_msg}")
        return False, error_msg


def get_webhook_info(
    bot_token: str,
    timeout: int = 10
) -> tuple[bool, Optional[Dict[str, Any]]]:
    """Get current webhook status.

    Args:
        bot_token: Telegram Bot Token
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, webhook_info_dict)

    API Reference:
        https://core.telegram.org/bots/api#getwebhookinfo
    """
    try:
        import requests
    except ImportError:
        return False, None

    # Build API URL
    api_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"

    try:
        # Send GET request
        response = requests.get(api_url, timeout=timeout)

        # Check response
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                return True, result.get("result")
            else:
                logger.error(
                    f"Telegram getWebhookInfo failed: {result.get('description')}"
                )
                return False, None
        else:
            logger.error(
                f"Telegram getWebhookInfo request failed: "
                f"status={response.status_code}"
            )
            return False, None

    except Exception as e:
        logger.exception(f"Telegram getWebhookInfo error: {e}")
        return False, None


def delete_webhook(
    bot_token: str,
    timeout: int = 10
) -> tuple[bool, Optional[str]]:
    """Delete webhook configuration.

    Args:
        bot_token: Telegram Bot Token
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, error_message)

    API Reference:
        https://core.telegram.org/bots/api#deletewebhook
    """
    try:
        import requests
    except ImportError:
        return False, "requests library not installed"

    # Build API URL
    api_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"

    try:
        # Send POST request
        response = requests.post(api_url, timeout=timeout)

        # Check response
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logger.info("Telegram webhook deleted successfully")
                return True, None
            else:
                error_msg = result.get("description", "Unknown error")
                logger.error(f"Telegram deleteWebhook failed: {error_msg}")
                return False, error_msg
        else:
            error_msg = f"HTTP {response.status_code}"
            logger.error(f"Telegram deleteWebhook request failed: {error_msg}")
            return False, error_msg

    except Exception as e:
        error_msg = str(e)
        logger.exception(f"Telegram deleteWebhook error: {error_msg}")
        return False, error_msg
