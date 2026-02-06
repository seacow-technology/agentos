"""Tests for policy engine and security policies.

This module tests policy evaluation, risk assessment,
and security controls.
"""

import pytest
from datetime import datetime, timezone

from agentos.core.communication.models import (
    CommunicationRequest,
    ConnectorType,
    RequestStatus,
    RiskLevel,
)
from agentos.core.communication.policy import PolicyEngine, CommunicationPolicy


class TestPolicyEngine:
    """Test suite for PolicyEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.policy_engine = PolicyEngine()

    def test_default_policies_loaded(self):
        """Test that default policies are loaded on initialization."""
        assert ConnectorType.WEB_SEARCH in self.policy_engine.policies
        assert ConnectorType.WEB_FETCH in self.policy_engine.policies
        assert ConnectorType.EMAIL_SMTP in self.policy_engine.policies

    def test_register_custom_policy(self):
        """Test registering a custom policy."""
        policy = CommunicationPolicy(
            name="test_policy",
            connector_type=ConnectorType.CUSTOM,
            allowed_operations=["test_op"],
        )
        self.policy_engine.register_policy(policy)
        assert ConnectorType.CUSTOM in self.policy_engine.policies

    def test_evaluate_allowed_request(self):
        """Test evaluating an allowed request."""
        request = CommunicationRequest(
            id="test-1",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test query"},
            status=RequestStatus.PENDING,  # Not requiring approval
        )
        verdict = self.policy_engine.evaluate_request(request)
        assert verdict.status == RequestStatus.APPROVED

    def test_evaluate_blocked_operation(self):
        """Test evaluating a blocked operation."""
        request = CommunicationRequest(
            id="test-2",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="invalid_operation",
            params={"query": "test"},
        )
        verdict = self.policy_engine.evaluate_request(request)
        assert verdict.status == RequestStatus.DENIED
        assert "not allowed" in verdict.hint.lower() or "not allowed" in verdict.reason_code.lower()

    def test_evaluate_blocked_domain(self):
        """Test evaluating a request to blocked domain."""
        request = CommunicationRequest(
            id="test-3",
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "http://localhost/test"},
        )
        verdict = self.policy_engine.evaluate_request(request)
        assert verdict.status == RequestStatus.DENIED
        assert "blocked" in verdict.hint.lower() or "localhost" in verdict.hint.lower()

    def test_ssrf_protection_localhost(self):
        """Test SSRF protection for localhost."""
        is_safe, reason = self.policy_engine._check_ssrf("http://localhost/api")
        assert is_safe is False
        assert "localhost" in reason.lower()

    def test_ssrf_protection_private_ip(self):
        """Test SSRF protection for private IPs."""
        test_ips = [
            "http://192.168.1.1/",
            "http://10.0.0.1/",
            "http://172.16.0.1/",
        ]
        for url in test_ips:
            is_safe, reason = self.policy_engine._check_ssrf(url)
            assert is_safe is False
            assert "private" in reason.lower() or "blocked" in reason.lower()

    def test_ssrf_protection_allowed_url(self):
        """Test SSRF protection allows valid URLs."""
        is_safe, reason = self.policy_engine._check_ssrf("https://example.com/api")
        assert is_safe is True

    def test_risk_assessment_email(self):
        """Test risk assessment for email operations."""
        request = CommunicationRequest(
            id="test-4",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={"to": "test@example.com", "subject": "Test", "body": "Test"},
        )
        risk = self.policy_engine.assess_risk(request)
        assert risk in [RiskLevel.MEDIUM, RiskLevel.HIGH]

    def test_risk_assessment_web_search(self):
        """Test risk assessment for web search."""
        request = CommunicationRequest(
            id="test-5",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test"},
        )
        risk = self.policy_engine.assess_risk(request)
        assert risk in [RiskLevel.LOW, RiskLevel.MEDIUM]

    def test_validate_params_web_search(self):
        """Test parameter validation for web search."""
        request = CommunicationRequest(
            id="test-6",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test"},
        )
        is_valid, reason = self.policy_engine.validate_params(request)
        assert is_valid is True

    def test_validate_params_missing_query(self):
        """Test parameter validation with missing query."""
        request = CommunicationRequest(
            id="test-7",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={},
        )
        is_valid, reason = self.policy_engine.validate_params(request)
        assert is_valid is False
        assert "query" in reason.lower() or "parameter" in reason.lower()

    def test_validate_params_email_missing_fields(self):
        """Test parameter validation for email with missing fields."""
        request = CommunicationRequest(
            id="test-8",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={"to": "test@example.com"},  # Missing subject and body
        )
        is_valid, reason = self.policy_engine.validate_params(request)
        assert is_valid is False

    def test_disabled_connector(self):
        """Test evaluation with disabled connector."""
        policy = self.policy_engine.get_policy(ConnectorType.WEB_SEARCH)
        policy.enabled = False

        request = CommunicationRequest(
            id="test-9",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test"},
        )
        verdict = self.policy_engine.evaluate_request(request)
        assert verdict.status == RequestStatus.DENIED
        assert "disabled" in verdict.hint.lower() or "disabled" in verdict.reason_code.lower()

        # Re-enable for other tests
        policy.enabled = True


class TestCommunicationPolicy:
    """Test suite for CommunicationPolicy model."""

    def test_policy_creation(self):
        """Test creating a policy."""
        policy = CommunicationPolicy(
            name="test_policy",
            connector_type=ConnectorType.WEB_FETCH,
            allowed_operations=["fetch"],
            rate_limit_per_minute=30,
        )
        assert policy.name == "test_policy"
        assert policy.connector_type == ConnectorType.WEB_FETCH
        assert "fetch" in policy.allowed_operations
        assert policy.rate_limit_per_minute == 30

    def test_policy_to_dict(self):
        """Test converting policy to dictionary."""
        policy = CommunicationPolicy(
            name="test_policy",
            connector_type=ConnectorType.RSS,
        )
        policy_dict = policy.to_dict()
        assert policy_dict["name"] == "test_policy"
        assert policy_dict["connector_type"] == "rss"
        assert isinstance(policy_dict["allowed_operations"], list)


class TestRateLimitPolicy:
    """Test suite for rate limit policy enforcement."""

    def setup_method(self):
        """Set up test fixtures."""
        self.policy_engine = PolicyEngine()

    def test_rate_limit_applied_to_policy(self):
        """Test that rate limits are properly configured in policies."""
        policy = self.policy_engine.get_policy(ConnectorType.WEB_SEARCH)
        assert policy.rate_limit_per_minute > 0
        assert policy.rate_limit_per_minute == 30

    def test_email_has_strict_rate_limit(self):
        """Test that email has stricter rate limits."""
        email_policy = self.policy_engine.get_policy(ConnectorType.EMAIL_SMTP)
        web_policy = self.policy_engine.get_policy(ConnectorType.WEB_SEARCH)
        assert email_policy.rate_limit_per_minute < web_policy.rate_limit_per_minute

    def test_custom_rate_limit_policy(self):
        """Test registering policy with custom rate limit."""
        policy = CommunicationPolicy(
            name="custom_limited",
            connector_type=ConnectorType.CUSTOM,
            allowed_operations=["test"],
            rate_limit_per_minute=5,
        )
        self.policy_engine.register_policy(policy)
        retrieved = self.policy_engine.get_policy(ConnectorType.CUSTOM)
        assert retrieved.rate_limit_per_minute == 5


class TestAllowlistPolicy:
    """Test suite for allowlist/blocklist domain policies."""

    def setup_method(self):
        """Set up test fixtures."""
        self.policy_engine = PolicyEngine()

    def test_allowed_domains_enforcement(self):
        """Test that only allowed domains are permitted."""
        policy = CommunicationPolicy(
            name="strict_allowlist",
            connector_type=ConnectorType.WEB_FETCH,
            allowed_operations=["fetch"],
            allowed_domains=["example.com", "safe-site.org"],
        )
        self.policy_engine.register_policy(policy)

        # Allowed domain
        request1 = CommunicationRequest(
            id="test-allow-1",
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "https://example.com/page"},
        )
        verdict1 = self.policy_engine.evaluate_request(request1)
        assert verdict1.status == RequestStatus.APPROVED

        # Blocked domain (not in allowlist)
        request2 = CommunicationRequest(
            id="test-allow-2",
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "https://not-allowed.com/page"},
        )
        verdict2 = self.policy_engine.evaluate_request(request2)
        assert verdict2.status == RequestStatus.DENIED
        assert "not in allowed list" in verdict2.hint.lower() or "allowed" in verdict2.reason_code.lower()

    def test_subdomain_allowlist(self):
        """Test that subdomains of allowed domains are permitted."""
        policy = CommunicationPolicy(
            name="subdomain_allowlist",
            connector_type=ConnectorType.WEB_FETCH,
            allowed_operations=["fetch"],
            allowed_domains=["example.com"],
        )
        self.policy_engine.register_policy(policy)

        request = CommunicationRequest(
            id="test-subdomain",
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "https://api.example.com/data"},
        )
        verdict = self.policy_engine.evaluate_request(request)
        assert verdict.status == RequestStatus.APPROVED

    def test_blocklist_priority(self):
        """Test that blocklist takes priority over allowlist."""
        policy = CommunicationPolicy(
            name="blocklist_test",
            connector_type=ConnectorType.WEB_FETCH,
            allowed_operations=["fetch"],
            blocked_domains=["blocked.com"],
        )
        self.policy_engine.register_policy(policy)

        request = CommunicationRequest(
            id="test-blocked",
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "https://blocked.com/page"},
        )
        verdict = self.policy_engine.evaluate_request(request)
        assert verdict.status == RequestStatus.DENIED
        assert "blocked" in verdict.hint.lower() or "blocked" in verdict.reason_code.lower()


class TestApprovalRequirement:
    """Test suite for manual approval requirements."""

    def setup_method(self):
        """Set up test fixtures."""
        self.policy_engine = PolicyEngine()

    def test_approval_required_blocks_unapproved(self):
        """Test that approval requirement blocks unapproved requests."""
        policy = self.policy_engine.get_policy(ConnectorType.EMAIL_SMTP)
        assert policy.require_approval is True

        request = CommunicationRequest(
            id="test-approval-1",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={"to": "test@example.com", "subject": "Test", "body": "Test"},
            status=RequestStatus.PENDING,
        )
        verdict = self.policy_engine.evaluate_request(request)
        assert verdict.status == RequestStatus.REQUIRE_ADMIN
        assert "approval" in verdict.hint.lower() or "approval" in verdict.reason_code.lower()

    def test_approved_request_passes(self):
        """Test that approved requests pass evaluation."""
        request = CommunicationRequest(
            id="test-approval-2",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={"to": "test@example.com", "subject": "Test", "body": "Test"},
            approval_token="admin-approval-12345",  # Approval token instead of status
        )
        verdict = self.policy_engine.evaluate_request(request)
        assert verdict.status == RequestStatus.APPROVED


class TestSSRFAdvanced:
    """Advanced SSRF protection tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.policy_engine = PolicyEngine()

    def test_ssrf_url_with_port(self):
        """Test SSRF protection with explicit ports."""
        test_cases = [
            "http://localhost:8080/",
            "http://127.0.0.1:3000/",
            "http://192.168.1.1:80/",
        ]
        for url in test_cases:
            is_safe, reason = self.policy_engine._check_ssrf(url)
            assert is_safe is False, f"Should block {url}"

    def test_ssrf_ipv6_link_local(self):
        """Test blocking IPv6 link-local addresses."""
        ipv6_urls = [
            "http://[fe80::1]/",
            "http://[fe80::abcd:ef01:2345:6789]/",
        ]
        for url in ipv6_urls:
            is_safe, reason = self.policy_engine._check_ssrf(url)
            assert is_safe is False, f"Should block {url}"

    def test_ssrf_file_protocol(self):
        """Test blocking file:// protocol."""
        file_urls = [
            "file:///etc/passwd",
            "file:///C:/Windows/System32/config/sam",
        ]
        for url in file_urls:
            is_safe, reason = self.policy_engine._check_ssrf(url)
            assert is_safe is False, f"Should block {url}"

    def test_ssrf_url_credentials(self):
        """Test SSRF protection with embedded credentials."""
        urls_with_creds = [
            "http://user:pass@localhost/",
            "http://admin:secret@127.0.0.1:8080/admin",
            "http://test@192.168.1.1/",
        ]
        for url in urls_with_creds:
            is_safe, reason = self.policy_engine._check_ssrf(url)
            assert is_safe is False, f"Should block {url} (localhost/private IP)"
