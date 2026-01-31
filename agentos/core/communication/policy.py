"""Policy engine for communication security and governance.

This module implements policy-based access control for external communications,
including domain filtering, operation validation, and risk assessment.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

from agentos.core.communication.models import (
    CommunicationRequest,
    CommunicationPolicy,
    ConnectorType,
    RiskLevel,
    RequestStatus,
    PolicyVerdict,
)

logger = logging.getLogger(__name__)


class PolicyEngine:
    """Engine for evaluating communication policies.

    The PolicyEngine validates requests against configured policies,
    performs risk assessment, and determines whether operations should
    be allowed, denied, or require approval.
    """

    def __init__(self):
        """Initialize the policy engine."""
        self.policies: Dict[ConnectorType, CommunicationPolicy] = {}
        self._load_default_policies()

    def _load_default_policies(self) -> None:
        """Load default security policies."""
        # Default policy for web search
        self.policies[ConnectorType.WEB_SEARCH] = CommunicationPolicy(
            name="default_web_search",
            connector_type=ConnectorType.WEB_SEARCH,
            allowed_operations=["search"],
            blocked_domains=["localhost", "127.0.0.1", "0.0.0.0"],
            rate_limit_per_minute=30,
            max_response_size_mb=5,
            timeout_seconds=30,
        )

        # Default policy for web fetch
        self.policies[ConnectorType.WEB_FETCH] = CommunicationPolicy(
            name="default_web_fetch",
            connector_type=ConnectorType.WEB_FETCH,
            allowed_operations=["fetch", "download"],
            blocked_domains=["localhost", "127.0.0.1", "0.0.0.0"],
            rate_limit_per_minute=20,
            max_response_size_mb=10,
            timeout_seconds=60,
        )

        # Default policy for RSS
        self.policies[ConnectorType.RSS] = CommunicationPolicy(
            name="default_rss",
            connector_type=ConnectorType.RSS,
            allowed_operations=["fetch_feed"],
            rate_limit_per_minute=10,
            max_response_size_mb=5,
            timeout_seconds=30,
        )

        # Default policy for email (more restrictive)
        self.policies[ConnectorType.EMAIL_SMTP] = CommunicationPolicy(
            name="default_email",
            connector_type=ConnectorType.EMAIL_SMTP,
            allowed_operations=["send"],
            require_approval=True,
            rate_limit_per_minute=5,
            timeout_seconds=30,
        )

        # Default policy for Slack
        self.policies[ConnectorType.SLACK] = CommunicationPolicy(
            name="default_slack",
            connector_type=ConnectorType.SLACK,
            allowed_operations=["send_message", "upload_file"],
            require_approval=False,
            rate_limit_per_minute=10,
            timeout_seconds=30,
        )

    def register_policy(self, policy: CommunicationPolicy) -> None:
        """Register a custom policy.

        Args:
            policy: Policy to register
        """
        self.policies[policy.connector_type] = policy
        logger.info(f"Registered policy: {policy.name} for {policy.connector_type}")

    def get_policy(self, connector_type: ConnectorType) -> Optional[CommunicationPolicy]:
        """Get policy for a connector type.

        Args:
            connector_type: Type of connector

        Returns:
            Policy if found, None otherwise
        """
        return self.policies.get(connector_type)

    def evaluate_request(
        self,
        request: CommunicationRequest,
        execution_phase: str = "execution"
    ) -> PolicyVerdict:
        """Evaluate a communication request against policies.

        Args:
            request: Request to evaluate
            execution_phase: Execution phase ("planning" or "execution")

        Returns:
            PolicyVerdict with status, reason_code, and hint
        """
        # Hard Rule 1: No Outbound in Planning Phase
        if execution_phase == "planning" and self._is_outbound(request.connector_type):
            return PolicyVerdict(
                status=RequestStatus.DENIED,
                reason_code="OUTBOUND_FORBIDDEN_IN_PLANNING",
                hint="Outbound operations are not allowed during planning phase"
            )

        # Hard Rule 2: Outbound requires approval token
        if self._is_outbound(request.connector_type) and not request.approval_token:
            return PolicyVerdict(
                status=RequestStatus.REQUIRE_ADMIN,
                reason_code="OUTBOUND_REQUIRES_APPROVAL",
                hint="Outbound operation requires explicit human approval"
            )

        policy = self.get_policy(request.connector_type)
        if not policy:
            return PolicyVerdict(
                status=RequestStatus.DENIED,
                reason_code="NO_POLICY",
                hint=f"No policy found for connector type: {request.connector_type}"
            )

        if not policy.enabled:
            return PolicyVerdict(
                status=RequestStatus.DENIED,
                reason_code="CONNECTOR_DISABLED",
                hint=f"Connector {request.connector_type} is disabled"
            )

        # Check if operation is allowed
        if policy.allowed_operations and request.operation not in policy.allowed_operations:
            return PolicyVerdict(
                status=RequestStatus.DENIED,
                reason_code="OPERATION_NOT_ALLOWED",
                hint=f"Operation '{request.operation}' not allowed for {request.connector_type}"
            )

        # Check domain restrictions if URL is present
        url = request.params.get("url")
        if url:
            is_allowed, reason = self._check_domain_policy(url, policy)
            if not is_allowed:
                return PolicyVerdict(
                    status=RequestStatus.DENIED,
                    reason_code="DOMAIN_BLOCKED",
                    hint=reason
                )

            # Perform SSRF checks for URLs
            is_safe, reason = self._check_ssrf(url)
            if not is_safe:
                return PolicyVerdict(
                    status=RequestStatus.DENIED,
                    reason_code="SSRF_DETECTED",
                    hint=f"SSRF protection: {reason}"
                )

        # Check if approval is required
        # Note: approval_token supersedes status check (for backward compatibility)
        if policy.require_approval:
            # Check if request has approval (either via token or status)
            has_approval = (
                request.approval_token is not None and request.approval_token != ""
            ) or request.status == RequestStatus.APPROVED

            if not has_approval:
                return PolicyVerdict(
                    status=RequestStatus.REQUIRE_ADMIN,
                    reason_code="APPROVAL_REQUIRED",
                    hint="Request requires manual approval"
                )

        return PolicyVerdict(
            status=RequestStatus.APPROVED,
            reason_code="REQUEST_APPROVED",
            hint="Request approved"
        )

    def _is_outbound(self, connector_type: ConnectorType) -> bool:
        """Check if connector type is outbound (sending data externally).

        Outbound operations have higher risk than inbound:
        - Inbound risk: Data leakage, injection, SSRF
        - Outbound risk: Spam, reputation damage, credential leak, compliance violation

        Args:
            connector_type: Type of connector

        Returns:
            True if connector is outbound (email, SMS, Slack, social media)
        """
        outbound_types = [
            ConnectorType.EMAIL_SMTP,
            ConnectorType.SLACK,
            # Add more outbound types as needed (SMS, Twitter, etc.)
        ]
        return connector_type in outbound_types

    def _check_domain_policy(self, url: str, policy: CommunicationPolicy) -> tuple[bool, str]:
        """Check if URL is allowed by domain policy.

        Args:
            url: URL to check
            policy: Policy to check against

        Returns:
            Tuple of (is_allowed, reason)
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Check blocked domains
            for blocked in policy.blocked_domains:
                if domain == blocked.lower() or domain.endswith(f".{blocked.lower()}"):
                    return False, f"Domain {domain} is blocked"

            # Check allowed domains (if specified, only these are allowed)
            if policy.allowed_domains:
                allowed = False
                for allowed_domain in policy.allowed_domains:
                    if domain == allowed_domain.lower() or domain.endswith(f".{allowed_domain.lower()}"):
                        allowed = True
                        break
                if not allowed:
                    return False, f"Domain {domain} is not in allowed list"

            return True, "Domain check passed"
        except Exception as e:
            return False, f"Invalid URL format: {str(e)}"

    def _check_ssrf(self, url: str) -> tuple[bool, str]:
        """Check for SSRF vulnerabilities.

        Args:
            url: URL to check

        Returns:
            Tuple of (is_safe, reason)
        """
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()

            # Remove credentials FIRST if present (user:pass@host)
            if '@' in host:
                host = host.split('@')[1]

            # Handle IPv6 addresses in brackets [::1] or [::1]:port
            if host.startswith('['):
                # Extract IPv6 address from brackets
                if ']:' in host:
                    host_without_port = host.split(']:')[0] + ']'
                else:
                    host_without_port = host.split(']')[0] + ']'
            else:
                # Remove port from host for pattern matching (but not for IPv6)
                host_without_port = host.split(':')[0] if ':' in host and not host.startswith('[') else host

            # Block localhost variations
            localhost_patterns = [
                r"^localhost$",
                r"^127\.",
                r"^0\.0\.0\.0$",
                r"^\[?::1\]?$",
                r"^\[?::\]?$",
                r"^0:0:0:0:0:0:0:1$",
            ]

            for pattern in localhost_patterns:
                if re.match(pattern, host_without_port):
                    return False, f"Localhost access blocked: {host}"

            # Block private IP ranges
            private_ip_patterns = [
                r"^10\.",
                r"^172\.(1[6-9]|2[0-9]|3[0-1])\.",
                r"^192\.168\.",
                r"^169\.254\.",  # Link-local
                r"^fd[0-9a-f]{2}:",  # IPv6 ULA
                r"^\[?fe80:",  # IPv6 link-local
            ]

            for pattern in private_ip_patterns:
                if re.match(pattern, host_without_port):
                    return False, f"Private IP access blocked: {host}"

            # Block suspicious schemes
            if parsed.scheme not in ["http", "https", "ftp", "ftps"]:
                return False, f"Suspicious URL scheme: {parsed.scheme}"

            return True, "SSRF check passed"
        except Exception as e:
            return False, f"SSRF check failed: {str(e)}"

    def assess_risk(self, request: CommunicationRequest) -> RiskLevel:
        """Assess risk level of a request.

        Args:
            request: Request to assess

        Returns:
            Risk level
        """
        risk_score = 0

        # Higher risk for email and messaging
        if request.connector_type in [ConnectorType.EMAIL_SMTP, ConnectorType.SLACK]:
            risk_score += 2

        # Check for sensitive operations
        sensitive_operations = ["send", "upload", "post", "delete"]
        if any(op in request.operation.lower() for op in sensitive_operations):
            risk_score += 1

        # Check for file operations
        if "file" in str(request.params).lower() or "upload" in request.operation.lower():
            risk_score += 1

        # Map score to risk level
        if risk_score <= 1:
            return RiskLevel.LOW
        elif risk_score <= 2:
            return RiskLevel.MEDIUM
        elif risk_score <= 3:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def validate_params(self, request: CommunicationRequest) -> tuple[bool, str]:
        """Validate request parameters.

        Args:
            request: Request to validate

        Returns:
            Tuple of (is_valid, reason)
        """
        # Connector-specific validation - check required params even if empty dict
        if request.connector_type == ConnectorType.WEB_SEARCH:
            if not request.params or "query" not in request.params:
                return False, "Web search requires 'query' parameter"

        elif request.connector_type == ConnectorType.WEB_FETCH:
            if not request.params or "url" not in request.params:
                return False, "Web fetch requires 'url' parameter"

        elif request.connector_type == ConnectorType.EMAIL_SMTP:
            required = ["to", "subject", "body"]
            missing = [p for p in required if p not in request.params]
            if missing:
                return False, f"Email requires parameters: {', '.join(missing)}"

        return True, "Parameters valid"
