"""Input and output sanitizers for security.

This module provides sanitization utilities to protect against
injection attacks, XSS, and other security vulnerabilities.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)


class InputSanitizer:
    """Sanitizer for input validation and cleaning.

    Protects against injection attacks, malicious inputs, and
    validates data before processing.
    """

    def __init__(self):
        """Initialize input sanitizer."""
        # SQL injection patterns
        self.sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
            r"(--|#|\/\*|\*\/)",
            r"(\bOR\b.*=.*)",
            r"(\bAND\b.*=.*)",
            r"(;.*--)",
        ]

        # Command injection patterns
        self.cmd_patterns = [
            r"[;&|`$]",
            r"\$\(",
            r"`.*`",
            r"\$\{.*\}",
        ]

        # Script injection patterns
        self.script_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
        ]

    def sanitize(self, data: Any) -> Any:
        """Sanitize input data.

        Args:
            data: Data to sanitize

        Returns:
            Sanitized data
        """
        if isinstance(data, dict):
            return {k: self.sanitize(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.sanitize(item) for item in data]
        elif isinstance(data, str):
            return self._sanitize_string(data)
        else:
            return data

    def _sanitize_string(self, value: str) -> str:
        """Sanitize a string value.

        Args:
            value: String to sanitize

        Returns:
            Sanitized string
        """
        # Check for SQL injection
        for pattern in self.sql_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {value[:50]}")
                # Remove suspicious patterns
                value = re.sub(pattern, "", value, flags=re.IGNORECASE)

        # Check for command injection
        for pattern in self.cmd_patterns:
            if re.search(pattern, value):
                logger.warning(f"Potential command injection detected: {value[:50]}")
                # Remove suspicious patterns
                value = re.sub(pattern, "", value)

        # Check for script injection
        for pattern in self.script_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential script injection detected: {value[:50]}")
                # Remove suspicious patterns
                value = re.sub(pattern, "", value, flags=re.IGNORECASE)

        # HTML escape for safety
        value = html.escape(value)

        return value.strip()

    def validate_email(self, email: str) -> bool:
        """Validate email format.

        Args:
            email: Email address to validate

        Returns:
            True if valid, False otherwise
        """
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    def validate_url(self, url: str) -> bool:
        """Validate URL format.

        Args:
            url: URL to validate

        Returns:
            True if valid, False otherwise
        """
        pattern = r"^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(:[0-9]+)?(/.*)?$"
        return bool(re.match(pattern, url))


class OutputSanitizer:
    """Sanitizer for output filtering and redaction.

    Protects against data leakage by filtering sensitive information
    from outputs.
    """

    def __init__(self):
        """Initialize output sanitizer."""
        # Patterns for sensitive data
        self.sensitive_patterns = {
            "api_key": r"(api[_-]?key|apikey)[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9_-]{20,})",
            "password": r"(password|passwd|pwd)[\"']?\s*[:=]\s*[\"']?([^\s\"']{6,})",
            "token": r"(token|auth)[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9_-]{20,})",
            "secret": r"(secret|private[_-]?key)[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9_-]{20,})",
            "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            "email": r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
            "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        }

    def sanitize(self, data: Any, redact_sensitive: bool = True) -> Any:
        """Sanitize output data.

        Args:
            data: Data to sanitize
            redact_sensitive: Whether to redact sensitive information

        Returns:
            Sanitized data
        """
        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                # Check if key name suggests sensitive data
                if redact_sensitive and self._is_sensitive_key(k):
                    result[k] = self._redact_value(v)
                else:
                    result[k] = self.sanitize(v, redact_sensitive)
            return result
        elif isinstance(data, list):
            return [self.sanitize(item, redact_sensitive) for item in data]
        elif isinstance(data, str):
            if redact_sensitive:
                return self._redact_sensitive(data)
            return data
        else:
            return data

    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a dictionary key name suggests sensitive data.

        Args:
            key: Dictionary key to check

        Returns:
            True if key suggests sensitive data
        """
        sensitive_keys = [
            "api_key", "apikey", "api-key",
            "password", "passwd", "pwd",
            "token", "auth", "authorization",
            "secret", "private_key", "private-key",
            "credit_card", "creditcard",
            "ssn", "social_security",
        ]
        key_lower = key.lower()
        return any(sens in key_lower for sens in sensitive_keys)

    def _redact_value(self, value: Any) -> str:
        """Redact a sensitive value.

        Args:
            value: Value to redact

        Returns:
            Redacted value as string
        """
        value_str = str(value)
        if len(value_str) > 4:
            return value_str[:4] + "*" * (min(len(value_str) - 4, 20))
        else:
            return "****"

    def _redact_sensitive(self, value: str) -> str:
        """Redact sensitive information from string.

        Args:
            value: String to redact

        Returns:
            Redacted string
        """
        result = value

        for name, pattern in self.sensitive_patterns.items():
            matches = re.finditer(pattern, result, re.IGNORECASE)
            for match in matches:
                # Redact the sensitive part
                if len(match.groups()) > 1:
                    # Pattern with capture groups (e.g., key=value)
                    sensitive_part = match.group(2)
                    redacted = sensitive_part[:4] + "*" * (len(sensitive_part) - 4)
                    result = result.replace(sensitive_part, redacted)
                else:
                    # Pattern without capture groups
                    sensitive_part = match.group(0)
                    redacted = sensitive_part[:4] + "*" * (len(sensitive_part) - 4)
                    result = result.replace(sensitive_part, redacted)

                logger.info(f"Redacted {name} from output")

        return result

    def truncate_large_output(self, data: str, max_size: int = 10 * 1024 * 1024) -> str:
        """Truncate large output to prevent memory issues.

        Args:
            data: Data to truncate
            max_size: Maximum size in bytes

        Returns:
            Truncated data
        """
        if len(data) > max_size:
            logger.warning(f"Truncating output from {len(data)} to {max_size} bytes")
            return data[:max_size] + "... [TRUNCATED]"
        return data

    def filter_fields(self, data: Dict[str, Any], allowed_fields: List[str]) -> Dict[str, Any]:
        """Filter dictionary to only include allowed fields.

        Args:
            data: Dictionary to filter
            allowed_fields: List of allowed field names

        Returns:
            Filtered dictionary
        """
        return {k: v for k, v in data.items() if k in allowed_fields}
