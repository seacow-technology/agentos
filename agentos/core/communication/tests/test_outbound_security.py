"""Tests for outbound security rules.

This module tests the hard security rules for outbound operations (email, Slack, SMS).
These rules are FROZEN and must not be bypassed.

Hard Rules:
1. No outbound in planning phase
2. LLM cannot trigger outbound without approval token
3. All outbound requires approval
"""

import pytest
from agentos.core.communication.models import (
    CommunicationRequest,
    ConnectorType,
    RequestStatus,
    RiskLevel,
)
from agentos.core.communication.policy import PolicyEngine


class TestOutboundSecurityRules:
    """Test suite for outbound security hard rules."""

    def setup_method(self):
        """Set up test fixtures."""
        self.policy_engine = PolicyEngine()

    # ======================================================================
    # Hard Rule 1: No Outbound in Planning Phase
    # ======================================================================

    def test_email_blocked_in_planning_phase(self):
        """Email operations must be blocked during planning phase."""
        request = CommunicationRequest(
            id="test-1",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={
                "to": "user@example.com",
                "subject": "Test Email",
                "body": "This is a test email",
            },
            execution_phase="planning",
        )

        verdict = self.policy_engine.evaluate_request(request, execution_phase="planning")

        assert verdict.status == RequestStatus.DENIED
        assert verdict.reason_code == "OUTBOUND_FORBIDDEN_IN_PLANNING"
        assert "planning phase" in verdict.hint.lower()

    def test_slack_blocked_in_planning_phase(self):
        """Slack operations must be blocked during planning phase."""
        request = CommunicationRequest(
            id="test-2",
            connector_type=ConnectorType.SLACK,
            operation="send_message",
            params={
                "channel": "#general",
                "text": "Test message",
            },
            execution_phase="planning",
        )

        verdict = self.policy_engine.evaluate_request(request, execution_phase="planning")

        assert verdict.status == RequestStatus.DENIED
        assert verdict.reason_code == "OUTBOUND_FORBIDDEN_IN_PLANNING"

    def test_inbound_allowed_in_planning_phase(self):
        """Inbound operations (search, fetch) should be allowed in planning phase."""
        request = CommunicationRequest(
            id="test-3",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test query"},
            execution_phase="planning",
        )

        verdict = self.policy_engine.evaluate_request(request, execution_phase="planning")

        # Should not be blocked by planning phase rule (may be blocked by other rules)
        assert verdict.reason_code != "OUTBOUND_FORBIDDEN_IN_PLANNING"

    # ======================================================================
    # Hard Rule 2: Outbound Requires Approval Token
    # ======================================================================

    def test_email_requires_approval_token(self):
        """Email without approval token must be blocked."""
        request = CommunicationRequest(
            id="test-4",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={
                "to": "user@example.com",
                "subject": "Test",
                "body": "Test body",
            },
            approval_token=None,  # No approval token
            execution_phase="execution",
        )

        verdict = self.policy_engine.evaluate_request(request, execution_phase="execution")

        assert verdict.status == RequestStatus.REQUIRE_ADMIN
        assert verdict.reason_code == "OUTBOUND_REQUIRES_APPROVAL"
        assert "approval" in verdict.hint.lower()

    def test_slack_requires_approval_token(self):
        """Slack without approval token must be blocked."""
        request = CommunicationRequest(
            id="test-5",
            connector_type=ConnectorType.SLACK,
            operation="send_message",
            params={
                "channel": "#general",
                "text": "Test message",
            },
            approval_token=None,  # No approval token
            execution_phase="execution",
        )

        verdict = self.policy_engine.evaluate_request(request, execution_phase="execution")

        assert verdict.status == RequestStatus.REQUIRE_ADMIN
        assert verdict.reason_code == "OUTBOUND_REQUIRES_APPROVAL"

    def test_email_with_approval_token_passes_outbound_checks(self):
        """Email with valid approval token should pass outbound security checks."""
        request = CommunicationRequest(
            id="test-6",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={
                "to": "user@example.com",
                "subject": "Test",
                "body": "Test body",
            },
            approval_token="user-123-abc",  # Valid approval token
            execution_phase="execution",
        )

        verdict = self.policy_engine.evaluate_request(request, execution_phase="execution")

        # Should pass outbound checks (may still require approval due to policy)
        assert verdict.reason_code != "OUTBOUND_REQUIRES_APPROVAL"
        assert verdict.reason_code != "OUTBOUND_FORBIDDEN_IN_PLANNING"

    def test_slack_with_approval_token_passes_outbound_checks(self):
        """Slack with valid approval token should pass outbound security checks."""
        request = CommunicationRequest(
            id="test-7",
            connector_type=ConnectorType.SLACK,
            operation="send_message",
            params={
                "channel": "#general",
                "text": "Test message",
            },
            approval_token="user-456-def",  # Valid approval token
            execution_phase="execution",
        )

        verdict = self.policy_engine.evaluate_request(request, execution_phase="execution")

        # Should pass outbound checks (may still require approval due to policy)
        assert verdict.reason_code != "OUTBOUND_REQUIRES_APPROVAL"
        assert verdict.reason_code != "OUTBOUND_FORBIDDEN_IN_PLANNING"

    # ======================================================================
    # Hard Rule 3: LLM Cannot Trigger Outbound Alone
    # ======================================================================

    def test_llm_cannot_trigger_email(self):
        """LLM-generated email request (no approval token) must be blocked."""
        # Simulate LLM generating an email request
        llm_request = CommunicationRequest(
            id="test-8",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={
                "to": "customer@example.com",
                "subject": "Automated Response",
                "body": "This is an automated response generated by the LLM.",
            },
            approval_token=None,  # LLM has no approval token
            execution_phase="execution",
        )

        verdict = self.policy_engine.evaluate_request(llm_request, execution_phase="execution")

        assert verdict.status == RequestStatus.REQUIRE_ADMIN
        assert verdict.reason_code == "OUTBOUND_REQUIRES_APPROVAL"

    def test_llm_cannot_trigger_slack(self):
        """LLM-generated Slack request (no approval token) must be blocked."""
        # Simulate LLM generating a Slack message
        llm_request = CommunicationRequest(
            id="test-9",
            connector_type=ConnectorType.SLACK,
            operation="send_message",
            params={
                "channel": "#alerts",
                "text": "System alert generated by LLM",
            },
            approval_token=None,  # LLM has no approval token
            execution_phase="execution",
        )

        verdict = self.policy_engine.evaluate_request(llm_request, execution_phase="execution")

        assert verdict.status == RequestStatus.REQUIRE_ADMIN
        assert verdict.reason_code == "OUTBOUND_REQUIRES_APPROVAL"

    def test_prompt_injection_attempt_blocked(self):
        """Prompt injection attempting to send malicious email must be blocked."""
        # Attacker tries to manipulate LLM to send email
        malicious_request = CommunicationRequest(
            id="test-10",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={
                "to": "attacker@evil.com",
                "subject": "Urgent: Wire Transfer Required",
                "body": "Please send $50,000 to account XYZ immediately.",
            },
            approval_token=None,  # Attacker has no legitimate approval
            execution_phase="execution",
        )

        verdict = self.policy_engine.evaluate_request(
            malicious_request, execution_phase="execution"
        )

        assert verdict.status == RequestStatus.REQUIRE_ADMIN
        assert verdict.reason_code == "OUTBOUND_REQUIRES_APPROVAL"

    # ======================================================================
    # Inbound Operations (Control Tests)
    # ======================================================================

    def test_web_search_no_approval_required(self):
        """Web search (inbound) should not require approval token."""
        request = CommunicationRequest(
            id="test-11",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test query"},
            approval_token=None,  # Inbound doesn't need approval
            execution_phase="execution",
        )

        verdict = self.policy_engine.evaluate_request(request, execution_phase="execution")

        # Should not be blocked by outbound rules
        assert verdict.reason_code != "OUTBOUND_REQUIRES_APPROVAL"
        assert verdict.reason_code != "OUTBOUND_FORBIDDEN_IN_PLANNING"

    def test_web_fetch_no_approval_required(self):
        """Web fetch (inbound) should not require approval token."""
        request = CommunicationRequest(
            id="test-12",
            connector_type=ConnectorType.WEB_FETCH,
            operation="fetch",
            params={"url": "https://example.com"},
            approval_token=None,  # Inbound doesn't need approval
            execution_phase="execution",
        )

        verdict = self.policy_engine.evaluate_request(request, execution_phase="execution")

        # Should not be blocked by outbound rules (may be blocked by SSRF checks)
        assert verdict.reason_code != "OUTBOUND_REQUIRES_APPROVAL"
        assert verdict.reason_code != "OUTBOUND_FORBIDDEN_IN_PLANNING"

    # ======================================================================
    # Edge Cases
    # ======================================================================

    def test_outbound_in_execution_phase_with_approval_allowed(self):
        """Outbound in execution phase with approval token should be allowed."""
        request = CommunicationRequest(
            id="test-13",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={
                "to": "user@example.com",
                "subject": "Test",
                "body": "Test body",
            },
            approval_token="user-789-ghi",
            execution_phase="execution",
        )

        verdict = self.policy_engine.evaluate_request(request, execution_phase="execution")

        # Should pass outbound hard rules (may still require approval due to policy)
        assert verdict.reason_code != "OUTBOUND_REQUIRES_APPROVAL"
        assert verdict.reason_code != "OUTBOUND_FORBIDDEN_IN_PLANNING"

    def test_empty_approval_token_treated_as_none(self):
        """Empty string approval token should be treated as missing."""
        request = CommunicationRequest(
            id="test-14",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={
                "to": "user@example.com",
                "subject": "Test",
                "body": "Test body",
            },
            approval_token="",  # Empty string
            execution_phase="execution",
        )

        verdict = self.policy_engine.evaluate_request(request, execution_phase="execution")

        # Empty string should be treated as no approval
        assert verdict.status == RequestStatus.REQUIRE_ADMIN
        assert verdict.reason_code == "OUTBOUND_REQUIRES_APPROVAL"

    def test_risk_assessment_higher_for_outbound(self):
        """Outbound operations should have higher risk scores."""
        email_request = CommunicationRequest(
            id="test-15",
            connector_type=ConnectorType.EMAIL_SMTP,
            operation="send",
            params={"to": "user@example.com", "subject": "Test", "body": "Test"},
        )

        search_request = CommunicationRequest(
            id="test-16",
            connector_type=ConnectorType.WEB_SEARCH,
            operation="search",
            params={"query": "test query"},
        )

        email_risk = self.policy_engine.assess_risk(email_request)
        search_risk = self.policy_engine.assess_risk(search_request)

        # Email (outbound) should have higher risk than search (inbound)
        risk_levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert risk_levels.index(email_risk) >= risk_levels.index(search_risk)


class TestOutboundConnectorIdentification:
    """Test that outbound connectors are correctly identified."""

    def setup_method(self):
        """Set up test fixtures."""
        self.policy_engine = PolicyEngine()

    def test_email_identified_as_outbound(self):
        """EMAIL_SMTP should be identified as outbound."""
        assert self.policy_engine._is_outbound(ConnectorType.EMAIL_SMTP) is True

    def test_slack_identified_as_outbound(self):
        """SLACK should be identified as outbound."""
        assert self.policy_engine._is_outbound(ConnectorType.SLACK) is True

    def test_web_search_not_outbound(self):
        """WEB_SEARCH should not be identified as outbound."""
        assert self.policy_engine._is_outbound(ConnectorType.WEB_SEARCH) is False

    def test_web_fetch_not_outbound(self):
        """WEB_FETCH should not be identified as outbound."""
        assert self.policy_engine._is_outbound(ConnectorType.WEB_FETCH) is False

    def test_rss_not_outbound(self):
        """RSS should not be identified as outbound."""
        assert self.policy_engine._is_outbound(ConnectorType.RSS) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
