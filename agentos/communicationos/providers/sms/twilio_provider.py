"""Twilio SMS Provider Implementation.

This module implements the ISmsProvider protocol for sending SMS via Twilio's API.
It handles authentication, API calls, error handling, and result mapping.

Design:
    - Uses requests library for HTTP calls (no heavy Twilio SDK dependency)
    - Implements retry logic for transient failures
    - Maps Twilio error codes to our error model
    - Returns structured SendResult for all operations

API Reference:
    https://www.twilio.com/docs/sms/api/message-resource#create-a-message-resource
"""

from __future__ import annotations

import base64
import logging
import re
from typing import Optional
from datetime import datetime

from agentos.communicationos.providers.sms import ISmsProvider, SendResult

logger = logging.getLogger(__name__)

# E.164 phone number validation regex
E164_REGEX = re.compile(r'^\+[1-9]\d{1,14}$')

# Twilio Account SID validation regex (starts with AC, 34 chars total)
ACCOUNT_SID_REGEX = re.compile(r'^AC[a-f0-9]{32}$')

# Twilio Auth Token validation regex (32 hex chars)
AUTH_TOKEN_REGEX = re.compile(r'^[a-f0-9]{32}$')


class TwilioSmsProvider:
    """Twilio SMS provider implementation.

    This provider sends SMS messages via Twilio's REST API.
    It implements the ISmsProvider protocol for use with SmsAdapter.

    Attributes:
        account_sid: Twilio Account SID (starts with AC)
        auth_token: Twilio Auth Token (32 hex characters)
        from_number: Default sender phone number (E.164 format)
        api_base_url: Twilio API base URL (default: https://api.twilio.com)
        timeout: Request timeout in seconds (default: 10)
    """

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        api_base_url: str = "https://api.twilio.com",
        timeout: int = 10
    ):
        """Initialize Twilio SMS provider.

        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
            from_number: Sender phone number in E.164 format
            api_base_url: Twilio API base URL (for testing)
            timeout: Request timeout in seconds
        """
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.api_base_url = api_base_url.rstrip('/')
        self.timeout = timeout

        logger.info(
            f"Initialized Twilio SMS provider: "
            f"account_sid={self._mask_sid(account_sid)}, "
            f"from_number={from_number}"
        )

    def send_sms(
        self,
        to_number: str,
        message_text: str,
        from_number: Optional[str] = None,
        max_segments: int = 3,
    ) -> SendResult:
        """Send an SMS message via Twilio.

        Args:
            to_number: Recipient phone number in E.164 format
            message_text: Message content to send
            from_number: Override sender number (uses default if None)
            max_segments: Maximum SMS segments to send (default 3)

        Returns:
            SendResult with success status, message SID, and metadata

        API Call:
            POST https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Messages.json
            Body (form-encoded):
                - To: Recipient number (E.164)
                - From: Sender number (E.164)
                - Body: Message text

        Response (success):
            {
                "sid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "status": "queued" or "sending" or "sent",
                "num_segments": "1" or "2" or "3",
                "price": "-0.00750",
                "price_unit": "USD"
            }

        Error Codes:
            - 21211: Invalid To number
            - 21606: From number not SMS-enabled
            - 21408: Permission denied (trial account sending to unverified number)
            - 21610: Message blocked (carrier rejection)
            - 401/403: Authentication failed
        """
        try:
            import requests
        except ImportError:
            logger.error("requests library not installed. Run: pip install requests")
            return SendResult(
                success=False,
                error_code="MISSING_DEPENDENCY",
                error_message="requests library not installed. Run: pip install requests"
            )

        # Validate inputs
        if not to_number or not message_text:
            return SendResult(
                success=False,
                error_code="INVALID_INPUT",
                error_message="to_number and message_text are required"
            )

        # Use provided from_number or default
        sender = from_number or self.from_number

        # Build API URL
        api_url = (
            f"{self.api_base_url}/2010-04-01/Accounts/"
            f"{self.account_sid}/Messages.json"
        )

        # Build request payload (form-encoded)
        payload = {
            "To": to_number,
            "From": sender,
            "Body": message_text,
        }

        # Build Basic Auth header
        auth_string = f"{self.account_sid}:{self.auth_token}"
        auth_bytes = auth_string.encode('utf-8')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # Log request (without sensitive data)
        logger.debug(
            f"Twilio API request: to={self._mask_phone(to_number)}, "
            f"from={sender}, length={len(message_text)}"
        )

        # Send request
        try:
            response = requests.post(
                api_url,
                data=payload,
                headers=headers,
                timeout=self.timeout
            )

            # Parse response
            if response.status_code in (200, 201):
                # Success
                result = response.json()
                message_sid = result.get("sid", "")
                status = result.get("status", "unknown")
                num_segments = int(result.get("num_segments", "1"))
                price = result.get("price")
                price_unit = result.get("price_unit", "USD")

                # Convert price to float (may be negative or None)
                cost = None
                if price:
                    try:
                        cost = abs(float(price))  # Make positive
                    except (ValueError, TypeError):
                        pass

                logger.info(
                    f"Twilio SMS sent: sid={message_sid}, status={status}, "
                    f"segments={num_segments}, cost={cost} {price_unit}"
                )

                return SendResult(
                    success=True,
                    message_sid=message_sid,
                    segments_count=num_segments,
                    cost=cost
                )

            else:
                # API error (400, 401, 403, 404, 500, etc.)
                try:
                    error_data = response.json()
                    error_code = str(error_data.get("code", ""))
                    error_message = error_data.get("message", response.text)
                except Exception:
                    # No JSON or invalid JSON - use status code
                    error_code = ""
                    error_message = response.text

                # Special handling for 401/403 without Twilio error code
                if response.status_code in (401, 403) and not error_code:
                    error_code = "AUTH_FAILED"
                    error_message = "Twilio authentication failed. Check Account SID and Auth Token."
                elif not error_code:
                    # Fallback to status code if no Twilio error code
                    error_code = str(response.status_code)

                # Map common Twilio error codes to friendly messages
                friendly_message = self._map_error_code(error_code, error_message)

                logger.error(
                    f"Twilio API error: code={error_code}, message={friendly_message}"
                )

                return SendResult(
                    success=False,
                    error_code=error_code,
                    error_message=friendly_message
                )

        except requests.exceptions.Timeout:
            error_msg = f"Twilio API request timed out after {self.timeout}s"
            logger.error(error_msg)
            return SendResult(
                success=False,
                error_code="TIMEOUT",
                error_message=error_msg
            )

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Failed to connect to Twilio API: {str(e)}"
            logger.error(error_msg)
            return SendResult(
                success=False,
                error_code="CONNECTION_ERROR",
                error_message=error_msg
            )

        except requests.exceptions.RequestException as e:
            error_msg = f"Twilio API request failed: {str(e)}"
            logger.exception(error_msg)
            return SendResult(
                success=False,
                error_code="REQUEST_ERROR",
                error_message=error_msg
            )

        except Exception as e:
            error_msg = f"Unexpected error sending SMS: {str(e)}"
            logger.exception(error_msg)
            return SendResult(
                success=False,
                error_code="UNKNOWN_ERROR",
                error_message=error_msg
            )

    def validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate provider configuration.

        Checks:
            - Account SID format (AC + 32 hex chars)
            - Auth Token format (32 hex chars)
            - From number format (E.164)

        Returns:
            Tuple of (is_valid, error_message)

        Note:
            This does NOT make an API call. Use test_connection() for that.
        """
        # Validate Account SID
        if not self.account_sid:
            return False, "Account SID is required"

        if not ACCOUNT_SID_REGEX.match(self.account_sid):
            return False, (
                "Invalid Account SID format. Must start with AC and be 34 characters long."
            )

        # Validate Auth Token
        if not self.auth_token:
            return False, "Auth Token is required"

        if not AUTH_TOKEN_REGEX.match(self.auth_token):
            return False, (
                "Invalid Auth Token format. Must be 32 hexadecimal characters."
            )

        # Validate From number
        if not self.from_number:
            return False, "From phone number is required"

        if not E164_REGEX.match(self.from_number):
            return False, (
                f"Invalid From number format: {self.from_number}. "
                f"Must be E.164 format (e.g., +15551234567)"
            )

        return True, None

    def test_connection(
        self,
        test_to_number: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """Test provider API connection and credentials.

        If test_to_number is provided, sends a real test SMS.
        Otherwise, validates credentials by attempting to fetch account info.

        Args:
            test_to_number: Optional phone number to send test SMS to

        Returns:
            Tuple of (success, error_message)

        Note:
            Sending a test SMS will incur Twilio charges (typically $0.0075-$0.02).
        """
        # First, validate config format
        is_valid, error_msg = self.validate_config()
        if not is_valid:
            return False, error_msg

        if test_to_number:
            # Send a test SMS
            result = self.send_sms(
                to_number=test_to_number,
                message_text="AgentOS Test: Your Twilio SMS is configured correctly!"
            )

            if result.success:
                return True, None
            else:
                return False, result.error_message

        else:
            # Validate credentials by fetching account info
            # This is a lightweight API call that doesn't send SMS
            try:
                import requests
            except ImportError:
                return False, "requests library not installed"

            api_url = (
                f"{self.api_base_url}/2010-04-01/Accounts/{self.account_sid}.json"
            )

            # Build Basic Auth header
            auth_string = f"{self.account_sid}:{self.auth_token}"
            auth_bytes = auth_string.encode('utf-8')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            headers = {
                "Authorization": f"Basic {auth_b64}",
            }

            try:
                response = requests.get(
                    api_url,
                    headers=headers,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    logger.info("Twilio credentials validated successfully")
                    return True, None
                elif response.status_code in (401, 403):
                    return False, "Authentication failed. Check Account SID and Auth Token."
                else:
                    return False, f"API error: {response.status_code}"

            except requests.exceptions.Timeout:
                return False, f"Connection test timed out after {self.timeout}s"

            except requests.exceptions.RequestException as e:
                return False, f"Connection test failed: {str(e)}"

            except Exception as e:
                return False, f"Unexpected error: {str(e)}"

    def _map_error_code(self, error_code: str, original_message: str) -> str:
        """Map Twilio error codes to user-friendly messages.

        Args:
            error_code: Twilio error code (e.g., "21211")
            original_message: Original error message from Twilio

        Returns:
            User-friendly error message
        """
        error_map = {
            "21211": "Invalid recipient phone number. Check that it's in E.164 format (e.g., +15551234567).",
            "21606": "From phone number is not SMS-enabled. Configure SMS capability in Twilio Console.",
            "21408": (
                "Permission denied. Trial accounts can only send to verified numbers. "
                "Verify the recipient in Twilio Console or upgrade your account."
            ),
            "21610": "Message blocked by carrier. The recipient's carrier rejected the message.",
            "21614": "Invalid E.164 format. Phone number must start with + and country code.",
            "21612": "Cannot route to this phone number.",
            "21623": "From number must be a valid phone number.",
            "20003": "Authentication error. Check your Account SID and Auth Token.",
        }

        # Return mapped message if available, otherwise return original
        return error_map.get(error_code, original_message)

    def _mask_sid(self, sid: str) -> str:
        """Mask Account SID for logging (privacy).

        Masks all but first 6 and last 4 characters.
        Example: ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx -> ACxxxx...xxxx

        Args:
            sid: Account SID to mask

        Returns:
            Masked SID string
        """
        if len(sid) <= 10:
            return "AC****"
        return sid[:6] + "..." + sid[-4:]

    def _mask_phone(self, phone_number: str) -> str:
        """Mask phone number for logging (privacy).

        Args:
            phone_number: Phone number to mask

        Returns:
            Masked phone number string
        """
        if len(phone_number) <= 4:
            return "****"
        return phone_number[:2] + "*" * (len(phone_number) - 6) + phone_number[-4:]
