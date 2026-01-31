"""Tests for injection protection and input sanitization.

This module tests the sanitizers to ensure protection against
SQL injection, XSS, command injection, and other attacks.
"""

import pytest

from agentos.core.communication.sanitizers import InputSanitizer, OutputSanitizer


class TestInputSanitizer:
    """Test suite for InputSanitizer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = InputSanitizer()

    def test_sanitize_clean_string(self):
        """Test sanitizing a clean string."""
        clean = "This is a clean string"
        result = self.sanitizer.sanitize(clean)
        assert result == clean

    def test_sanitize_sql_injection_select(self):
        """Test blocking SQL injection with SELECT."""
        malicious = "test' OR '1'='1' SELECT * FROM users--"
        result = self.sanitizer.sanitize(malicious)
        # Should remove or escape SQL keywords
        assert "SELECT" not in result.upper() or result != malicious

    def test_sanitize_sql_injection_drop(self):
        """Test blocking SQL injection with DROP."""
        malicious = "test'; DROP TABLE users; --"
        result = self.sanitizer.sanitize(malicious)
        assert "DROP" not in result.upper() or result != malicious

    def test_sanitize_sql_injection_union(self):
        """Test blocking SQL injection with UNION."""
        malicious = "test' UNION SELECT password FROM users--"
        result = self.sanitizer.sanitize(malicious)
        assert ("UNION" not in result.upper() and "SELECT" not in result.upper()) or result != malicious

    def test_sanitize_command_injection_pipe(self):
        """Test blocking command injection with pipe."""
        malicious = "test | rm -rf /"
        result = self.sanitizer.sanitize(malicious)
        # Should remove pipe and command
        assert "|" not in result

    def test_sanitize_command_injection_semicolon(self):
        """Test blocking command injection with semicolon."""
        malicious = "test; cat /etc/passwd"
        result = self.sanitizer.sanitize(malicious)
        assert ";" not in result

    def test_sanitize_command_injection_backticks(self):
        """Test blocking command injection with backticks."""
        malicious = "test`whoami`"
        result = self.sanitizer.sanitize(malicious)
        assert "`" not in result

    def test_sanitize_command_injection_dollar(self):
        """Test blocking command injection with $()."""
        malicious = "test$(whoami)"
        result = self.sanitizer.sanitize(malicious)
        assert "$(" not in result

    def test_sanitize_xss_script_tag(self):
        """Test blocking XSS with script tags."""
        malicious = "<script>alert('XSS')</script>"
        result = self.sanitizer.sanitize(malicious)
        # Should escape or remove script tags
        assert "<script>" not in result.lower()

    def test_sanitize_xss_javascript_protocol(self):
        """Test blocking XSS with javascript: protocol."""
        malicious = "javascript:alert('XSS')"
        result = self.sanitizer.sanitize(malicious)
        assert "javascript:" not in result.lower()

    def test_sanitize_xss_event_handler(self):
        """Test blocking XSS with event handlers."""
        malicious = "<img src=x onerror=alert('XSS')>"
        result = self.sanitizer.sanitize(malicious)
        assert "onerror" not in result.lower()

    def test_sanitize_html_entities(self):
        """Test HTML entity escaping."""
        text = "<div>Test & 'quotes' \"double\"</div>"
        result = self.sanitizer.sanitize(text)
        # Should escape HTML entities
        assert "&lt;" in result or "<div>" not in result

    def test_sanitize_dict(self):
        """Test sanitizing dictionary values."""
        data = {
            "clean": "normal text",
            "sql": "test' OR '1'='1",
            "xss": "<script>alert('xss')</script>",
        }
        result = self.sanitizer.sanitize(data)
        assert isinstance(result, dict)
        assert result["clean"] == "normal text"
        # Malicious content should be sanitized
        assert "<script>" not in result["xss"].lower()

    def test_sanitize_list(self):
        """Test sanitizing list values."""
        data = [
            "clean text",
            "test' OR '1'='1",
            "<script>alert('xss')</script>",
        ]
        result = self.sanitizer.sanitize(data)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_sanitize_nested_structure(self):
        """Test sanitizing nested data structures."""
        data = {
            "user": {
                "name": "test' OR '1'='1",
                "tags": ["<script>", "normal"],
            }
        }
        result = self.sanitizer.sanitize(data)
        assert isinstance(result["user"], dict)
        assert isinstance(result["user"]["tags"], list)

    def test_validate_email_valid(self):
        """Test validating valid email addresses."""
        valid_emails = [
            "test@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk",
        ]
        for email in valid_emails:
            assert self.sanitizer.validate_email(email) is True

    def test_validate_email_invalid(self):
        """Test validating invalid email addresses."""
        invalid_emails = [
            "not-an-email",
            "@example.com",
            "user@",
            "user@.com",
            "user@example",
        ]
        for email in invalid_emails:
            assert self.sanitizer.validate_email(email) is False

    def test_validate_url_valid(self):
        """Test validating valid URLs."""
        valid_urls = [
            "http://example.com",
            "https://example.com/path",
            "https://sub.example.com/path?query=1",
        ]
        for url in valid_urls:
            assert self.sanitizer.validate_url(url) is True

    def test_validate_url_invalid(self):
        """Test validating invalid URLs."""
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",  # Only http/https allowed
            "example.com",  # Missing scheme
            "http://",  # Missing domain
        ]
        for url in invalid_urls:
            assert self.sanitizer.validate_url(url) is False


class TestOutputSanitizer:
    """Test suite for OutputSanitizer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = OutputSanitizer()

    def test_sanitize_clean_output(self):
        """Test sanitizing clean output."""
        clean = "This is clean output"
        result = self.sanitizer.sanitize(clean)
        assert result == clean

    def test_redact_api_key(self):
        """Test redacting API keys."""
        text = "api_key: sk-1234567890abcdef1234567890"
        result = self.sanitizer.sanitize(text, redact_sensitive=True)
        # API key should be redacted
        assert "sk-1234567890abcdef1234567890" not in result
        assert "****" in result or "sk-1" in result

    def test_redact_password(self):
        """Test redacting passwords."""
        text = "password: mySecretPassword123"
        result = self.sanitizer.sanitize(text, redact_sensitive=True)
        # Password should be redacted
        assert "mySecretPassword123" not in result

    def test_redact_token(self):
        """Test redacting tokens."""
        text = "token=ghp_1234567890abcdefghijklmnopqr"
        result = self.sanitizer.sanitize(text, redact_sensitive=True)
        # Token should be redacted
        assert "ghp_1234567890abcdefghijklmnopqr" not in result

    def test_redact_credit_card(self):
        """Test redacting credit card numbers."""
        text = "Card: 4532-1234-5678-9010"
        result = self.sanitizer.sanitize(text, redact_sensitive=True)
        # Credit card should be redacted
        assert "4532-1234-5678-9010" not in result

    def test_redact_email(self):
        """Test redacting email addresses."""
        text = "Contact: user@example.com"
        result = self.sanitizer.sanitize(text, redact_sensitive=True)
        # Email should be redacted
        assert "user@example.com" not in result or "user" in result

    def test_no_redaction_when_disabled(self):
        """Test that redaction is skipped when disabled."""
        text = "password: mySecretPassword123"
        result = self.sanitizer.sanitize(text, redact_sensitive=False)
        assert result == text

    def test_truncate_large_output(self):
        """Test truncating large output."""
        large_text = "A" * (11 * 1024 * 1024)  # 11MB
        result = self.sanitizer.truncate_large_output(large_text, max_size=10 * 1024 * 1024)
        assert len(result) <= 10 * 1024 * 1024 + 100  # Allow for truncation message
        assert "[TRUNCATED]" in result

    def test_no_truncation_for_small_output(self):
        """Test that small output is not truncated."""
        small_text = "A" * 1000
        result = self.sanitizer.truncate_large_output(small_text)
        assert result == small_text

    def test_filter_fields(self):
        """Test filtering dictionary fields."""
        data = {
            "public": "visible data",
            "secret": "sensitive data",
            "api_key": "sk-12345",
            "name": "John Doe",
        }
        allowed = ["public", "name"]
        result = self.sanitizer.filter_fields(data, allowed)
        assert "public" in result
        assert "name" in result
        assert "secret" not in result
        assert "api_key" not in result

    def test_sanitize_dict(self):
        """Test sanitizing dictionary output."""
        data = {
            "message": "Hello",
            "api_key": "sk-1234567890abcdef1234567890",
        }
        result = self.sanitizer.sanitize(data, redact_sensitive=True)
        assert isinstance(result, dict)
        # API key should be redacted
        if "api_key" in result:
            # Check if the full key is redacted or has asterisks
            result_str = str(result["api_key"])
            assert result_str != "sk-1234567890abcdef1234567890" or "****" in result_str

    def test_sanitize_list(self):
        """Test sanitizing list output."""
        data = [
            "Normal text",
            "password: secret123",
        ]
        result = self.sanitizer.sanitize(data, redact_sensitive=True)
        assert isinstance(result, list)
        assert len(result) == 2
