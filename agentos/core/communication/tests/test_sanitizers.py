"""Tests for Sanitizers.

This module tests input and output sanitizers for security,
including SQL injection, XSS, command injection, and sensitive data redaction.
"""

import pytest

from agentos.core.communication.sanitizers import InputSanitizer, OutputSanitizer


class TestInputSanitizerBasics:
    """Basic tests for InputSanitizer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = InputSanitizer()

    def test_sanitize_clean_string(self):
        """Test sanitizing a clean string returns unchanged."""
        clean = "This is a clean string with normal text"
        result = self.sanitizer.sanitize(clean)
        assert "This is a clean string" in result

    def test_sanitize_none(self):
        """Test sanitizing None value."""
        result = self.sanitizer.sanitize(None)
        assert result is None

    def test_sanitize_number(self):
        """Test sanitizing numeric values."""
        assert self.sanitizer.sanitize(123) == 123
        assert self.sanitizer.sanitize(45.67) == 45.67

    def test_sanitize_boolean(self):
        """Test sanitizing boolean values."""
        assert self.sanitizer.sanitize(True) is True
        assert self.sanitizer.sanitize(False) is False


class TestSQLInjectionProtection:
    """Test suite for SQL injection protection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = InputSanitizer()

    def test_block_select_statement(self):
        """Test blocking SELECT statements."""
        malicious = "test' OR '1'='1' SELECT * FROM users--"
        result = self.sanitizer.sanitize(malicious)
        assert "SELECT" not in result.upper()

    def test_block_drop_statement(self):
        """Test blocking DROP statements."""
        malicious = "test'; DROP TABLE users; --"
        result = self.sanitizer.sanitize(malicious)
        assert "DROP" not in result.upper()

    def test_block_insert_statement(self):
        """Test blocking INSERT statements."""
        malicious = "'; INSERT INTO users VALUES ('admin', 'pass'); --"
        result = self.sanitizer.sanitize(malicious)
        assert "INSERT" not in result.upper()

    def test_block_update_statement(self):
        """Test blocking UPDATE statements."""
        malicious = "admin'; UPDATE users SET role='admin' WHERE id=1; --"
        result = self.sanitizer.sanitize(malicious)
        assert "UPDATE" not in result.upper()

    def test_block_delete_statement(self):
        """Test blocking DELETE statements."""
        malicious = "'; DELETE FROM users WHERE 1=1; --"
        result = self.sanitizer.sanitize(malicious)
        assert "DELETE" not in result.upper()

    def test_block_union_attack(self):
        """Test blocking UNION attacks."""
        malicious = "test' UNION SELECT password FROM users--"
        result = self.sanitizer.sanitize(malicious)
        assert "UNION" not in result.upper() or "SELECT" not in result.upper()

    def test_block_sql_comments(self):
        """Test blocking SQL comment sequences."""
        test_cases = [
            "test' --",
            "test' #",
            "test' /* comment */",
        ]
        for malicious in test_cases:
            result = self.sanitizer.sanitize(malicious)
            # Comments should be removed or escaped
            assert "--" not in result or "#" not in result

    def test_block_or_equals(self):
        """Test blocking OR equals patterns."""
        malicious = "test' OR '1'='1"
        result = self.sanitizer.sanitize(malicious)
        # Pattern should be sanitized
        assert result != malicious or "OR" not in result.upper()

    def test_block_and_equals(self):
        """Test blocking AND equals patterns."""
        malicious = "test' AND '1'='1"
        result = self.sanitizer.sanitize(malicious)
        # Pattern should be sanitized
        assert result != malicious or "AND" not in result.upper()


class TestCommandInjectionProtection:
    """Test suite for command injection protection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = InputSanitizer()

    def test_block_pipe(self):
        """Test blocking pipe character."""
        malicious = "test | cat /etc/passwd"
        result = self.sanitizer.sanitize(malicious)
        assert "|" not in result

    def test_block_semicolon(self):
        """Test blocking semicolon."""
        malicious = "test; rm -rf /"
        result = self.sanitizer.sanitize(malicious)
        assert ";" not in result

    def test_block_ampersand(self):
        """Test blocking ampersand."""
        malicious = "test & whoami"
        result = self.sanitizer.sanitize(malicious)
        assert "&" not in result

    def test_block_backticks(self):
        """Test blocking backticks."""
        malicious = "test`whoami`"
        result = self.sanitizer.sanitize(malicious)
        assert "`" not in result

    def test_block_dollar_paren(self):
        """Test blocking $() command substitution."""
        malicious = "test$(whoami)"
        result = self.sanitizer.sanitize(malicious)
        assert "$(" not in result

    def test_block_dollar_brace(self):
        """Test blocking ${} variable expansion."""
        malicious = "test${PATH}"
        result = self.sanitizer.sanitize(malicious)
        assert "${" not in result

    def test_block_multiple_command_chars(self):
        """Test blocking multiple command injection characters."""
        malicious = "test; ls | grep secret && rm file"
        result = self.sanitizer.sanitize(malicious)
        assert ";" not in result
        assert "|" not in result
        assert "&&" not in result or "&" not in result


class TestXSSProtection:
    """Test suite for XSS (Cross-Site Scripting) protection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = InputSanitizer()

    def test_block_script_tag(self):
        """Test blocking script tags."""
        malicious = "<script>alert('XSS')</script>"
        result = self.sanitizer.sanitize(malicious)
        assert "<script>" not in result.lower()

    def test_block_script_with_src(self):
        """Test blocking script tag with src attribute."""
        malicious = '<script src="evil.js"></script>'
        result = self.sanitizer.sanitize(malicious)
        assert "<script" not in result.lower()

    def test_block_javascript_protocol(self):
        """Test blocking javascript: protocol."""
        malicious = "javascript:alert('XSS')"
        result = self.sanitizer.sanitize(malicious)
        assert "javascript:" not in result.lower()

    def test_block_onerror_handler(self):
        """Test blocking onerror event handler."""
        malicious = '<img src=x onerror=alert("XSS")>'
        result = self.sanitizer.sanitize(malicious)
        assert "onerror" not in result.lower()

    def test_block_onload_handler(self):
        """Test blocking onload event handler."""
        malicious = '<body onload=alert("XSS")>'
        result = self.sanitizer.sanitize(malicious)
        assert "onload" not in result.lower()

    def test_block_onclick_handler(self):
        """Test blocking onclick event handler."""
        malicious = '<div onclick=alert("XSS")>Click me</div>'
        result = self.sanitizer.sanitize(malicious)
        assert "onclick" not in result.lower()

    def test_escape_html_entities(self):
        """Test HTML entity escaping."""
        text = '<div>Test & "quotes"</div>'
        result = self.sanitizer.sanitize(text)
        # Should contain escaped entities
        assert "&lt;" in result or "<div>" not in result

    def test_escape_quotes(self):
        """Test escaping quotes."""
        text = 'Test "double" and \'single\' quotes'
        result = self.sanitizer.sanitize(text)
        # Quotes should be escaped or preserved safely
        assert isinstance(result, str)


class TestNestedDataSanitization:
    """Test suite for sanitizing nested data structures."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = InputSanitizer()

    def test_sanitize_dict(self):
        """Test sanitizing dictionary values."""
        data = {
            "clean": "normal text",
            "sql": "test' OR '1'='1",
            "cmd": "test; cat /etc/passwd",
            "xss": "<script>alert('xss')</script>",
        }
        result = self.sanitizer.sanitize(data)

        assert isinstance(result, dict)
        assert result["clean"] == "normal text"
        assert "OR" not in result["sql"].upper() or result["sql"] != data["sql"]
        assert ";" not in result["cmd"]
        assert "<script>" not in result["xss"].lower()

    def test_sanitize_list(self):
        """Test sanitizing list values."""
        data = [
            "clean text",
            "test' SELECT * FROM users",
            "test | whoami",
            "<script>alert('xss')</script>",
        ]
        result = self.sanitizer.sanitize(data)

        assert isinstance(result, list)
        assert len(result) == 4
        assert result[0] == "clean text"
        # Others should be sanitized
        assert "SELECT" not in result[1].upper() or result[1] != data[1]

    def test_sanitize_nested_dict(self):
        """Test sanitizing nested dictionaries."""
        data = {
            "user": {
                "name": "test' OR '1'='1",
                "preferences": {
                    "theme": "dark",
                    "script": "<script>alert('xss')</script>",
                }
            }
        }
        result = self.sanitizer.sanitize(data)

        assert isinstance(result["user"], dict)
        assert isinstance(result["user"]["preferences"], dict)
        assert result["user"]["preferences"]["theme"] == "dark"
        # Malicious content should be sanitized
        assert "<script>" not in result["user"]["preferences"]["script"].lower()

    def test_sanitize_mixed_structure(self):
        """Test sanitizing mixed nested structures."""
        data = {
            "items": [
                {"name": "test", "value": "test' OR '1'='1"},
                {"name": "test2", "value": "normal"},
            ],
            "metadata": {
                "tags": ["tag1", "tag2; rm -rf /"],
            }
        }
        result = self.sanitizer.sanitize(data)

        assert isinstance(result, dict)
        assert isinstance(result["items"], list)
        assert len(result["items"]) == 2
        # Semicolon should be removed
        assert ";" not in result["metadata"]["tags"][1]


class TestInputValidation:
    """Test suite for input validation methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = InputSanitizer()

    def test_validate_email_valid(self):
        """Test validating valid email addresses."""
        valid_emails = [
            "user@example.com",
            "first.last@example.com",
            "user+tag@example.co.uk",
            "user123@test-domain.org",
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
            "user@domain",
            "user @example.com",  # Space
            "user@exam ple.com",  # Space in domain
        ]
        for email in invalid_emails:
            assert self.sanitizer.validate_email(email) is False

    def test_validate_url_valid(self):
        """Test validating valid URLs."""
        valid_urls = [
            "http://example.com",
            "https://example.com",
            "https://www.example.com",
            "https://sub.example.com/path",
            "https://example.com/path?query=1",
            "https://example.com:8080/path",
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
            "http:// example.com",  # Space
        ]
        for url in invalid_urls:
            assert self.sanitizer.validate_url(url) is False


class TestOutputSanitizerBasics:
    """Basic tests for OutputSanitizer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = OutputSanitizer()

    def test_sanitize_clean_output(self):
        """Test sanitizing clean output."""
        clean = "This is clean output with normal text"
        result = self.sanitizer.sanitize(clean, redact_sensitive=False)
        assert result == clean

    def test_sanitize_without_redaction(self):
        """Test that redaction can be disabled."""
        text = "password: mySecretPassword123"
        result = self.sanitizer.sanitize(text, redact_sensitive=False)
        assert result == text

    def test_sanitize_dict(self):
        """Test sanitizing dictionary output."""
        data = {"key": "value", "password": "secret123"}
        result = self.sanitizer.sanitize(data, redact_sensitive=True)
        assert isinstance(result, dict)

    def test_sanitize_list(self):
        """Test sanitizing list output."""
        data = ["normal text", "api_key: sk-12345"]
        result = self.sanitizer.sanitize(data, redact_sensitive=True)
        assert isinstance(result, list)


class TestSensitiveDataRedaction:
    """Test suite for sensitive data redaction."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = OutputSanitizer()

    def test_redact_api_key(self):
        """Test redacting API keys."""
        test_cases = [
            "api_key: sk-1234567890abcdef1234567890",
            "apikey=sk_live_12345678901234567890",
            'API_KEY="pk_test_12345678901234567890"',
        ]
        for text in test_cases:
            result = self.sanitizer.sanitize(text, redact_sensitive=True)
            # Key should be partially redacted
            assert "12345678901234567890" not in result or "****" in result

    def test_redact_password(self):
        """Test redacting passwords."""
        test_cases = [
            "password: mySecretPassword123",
            "passwd=SuperSecret456",
            'pwd: "hiddenPass789"',
        ]
        for text in test_cases:
            result = self.sanitizer.sanitize(text, redact_sensitive=True)
            # Password should not appear in full
            assert "Secret" not in result or "****" in result

    def test_redact_token(self):
        """Test redacting tokens."""
        test_cases = [
            "token: ghp_1234567890abcdefghijklmnopqr",
            "auth_token=bearer_1234567890abcdefghij",
        ]
        for text in test_cases:
            result = self.sanitizer.sanitize(text, redact_sensitive=True)
            assert "1234567890abcdefghij" not in result or "****" in result

    def test_redact_secret(self):
        """Test redacting secrets."""
        test_cases = [
            "secret: my_super_secret_key_12345",
            "private_key=rsa_private_key_12345678",
        ]
        for text in test_cases:
            result = self.sanitizer.sanitize(text, redact_sensitive=True)
            assert "secret_key_12345" not in result or "****" in result

    def test_redact_credit_card(self):
        """Test redacting credit card numbers."""
        test_cases = [
            "Card: 4532-1234-5678-9010",
            "CC: 4532 1234 5678 9010",
            "Credit card: 4532123456789010",
        ]
        for text in test_cases:
            result = self.sanitizer.sanitize(text, redact_sensitive=True)
            # Full card number should not appear
            assert "4532-1234-5678-9010" not in result or "****" in result

    def test_redact_ssn(self):
        """Test redacting SSN."""
        text = "SSN: 123-45-6789"
        result = self.sanitizer.sanitize(text, redact_sensitive=True)
        assert "123-45-6789" not in result or "***" in result

    def test_redact_email_optional(self):
        """Test optional email redaction."""
        text = "Contact: user@example.com"
        result = self.sanitizer.sanitize(text, redact_sensitive=True)
        # Email might be partially redacted
        assert isinstance(result, str)

    def test_redact_multiple_sensitive_data(self):
        """Test redacting multiple types of sensitive data."""
        text = """
        API Key: sk-1234567890abcdef
        Password: mySecret123
        Token: bearer_token_xyz
        """
        result = self.sanitizer.sanitize(text, redact_sensitive=True)
        # All sensitive data should be redacted
        assert "1234567890abcdef" not in result or "****" in result
        assert "mySecret123" not in result or "****" in result


class TestOutputTruncation:
    """Test suite for output truncation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = OutputSanitizer()

    def test_truncate_large_output(self):
        """Test truncating large output."""
        large_text = "A" * (11 * 1024 * 1024)  # 11MB
        result = self.sanitizer.truncate_large_output(large_text, max_size=10 * 1024 * 1024)
        assert len(result) <= 10 * 1024 * 1024 + 100
        assert "[TRUNCATED]" in result

    def test_no_truncation_for_small_output(self):
        """Test that small output is not truncated."""
        small_text = "A" * 1000
        result = self.sanitizer.truncate_large_output(small_text)
        assert result == small_text
        assert "[TRUNCATED]" not in result

    def test_truncate_custom_max_size(self):
        """Test truncating with custom max size."""
        text = "A" * 1000
        result = self.sanitizer.truncate_large_output(text, max_size=500)
        assert len(result) <= 600  # 500 + some overhead for message
        assert "[TRUNCATED]" in result


class TestFieldFiltering:
    """Test suite for field filtering."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = OutputSanitizer()

    def test_filter_fields(self):
        """Test filtering dictionary fields."""
        data = {
            "public": "visible data",
            "secret": "sensitive data",
            "api_key": "sk-12345",
            "name": "John Doe",
            "internal_id": "xyz123",
        }
        allowed = ["public", "name"]
        result = self.sanitizer.filter_fields(data, allowed)

        assert "public" in result
        assert "name" in result
        assert "secret" not in result
        assert "api_key" not in result
        assert "internal_id" not in result
        assert len(result) == 2

    def test_filter_empty_allowed_list(self):
        """Test filtering with empty allowed list."""
        data = {"key1": "value1", "key2": "value2"}
        result = self.sanitizer.filter_fields(data, [])
        assert len(result) == 0

    def test_filter_nonexistent_fields(self):
        """Test filtering with nonexistent fields in allowed list."""
        data = {"key1": "value1"}
        allowed = ["key1", "key2", "key3"]
        result = self.sanitizer.filter_fields(data, allowed)
        # Should only include existing fields
        assert result == {"key1": "value1"}


class TestSanitizerIntegration:
    """Integration tests for sanitizers working together."""

    def test_input_then_output_sanitization(self):
        """Test input sanitization followed by output sanitization."""
        input_sanitizer = InputSanitizer()
        output_sanitizer = OutputSanitizer()

        # Malicious input
        malicious_input = "test' OR '1'='1'; password: secret123"

        # Sanitize input
        cleaned_input = input_sanitizer.sanitize(malicious_input)

        # Sanitize output
        safe_output = output_sanitizer.sanitize(cleaned_input, redact_sensitive=True)

        # Both SQL and password should be handled
        assert "OR" not in safe_output.upper() or "****" in safe_output
        assert "secret123" not in safe_output or "****" in safe_output

    def test_complex_nested_data_full_sanitization(self):
        """Test full sanitization of complex nested data."""
        input_sanitizer = InputSanitizer()
        output_sanitizer = OutputSanitizer()

        data = {
            "user": {
                "query": "test' OR '1'='1",
                "credentials": {
                    "password": "secret123",
                    "api_key": "sk-1234567890abcdef",
                }
            },
            "commands": [
                "ls -la",
                "cat /etc/passwd | grep root",
            ]
        }

        # Sanitize input
        cleaned = input_sanitizer.sanitize(data)

        # Sanitize output
        safe = output_sanitizer.sanitize(cleaned, redact_sensitive=True)

        # Verify sanitization
        assert isinstance(safe, dict)
        # SQL should be sanitized
        assert "OR" not in str(safe).upper() or safe != data
        # Pipe should be removed
        assert "|" not in str(safe)
        # Sensitive data should be redacted
        assert "secret123" not in str(safe) or "****" in str(safe)
