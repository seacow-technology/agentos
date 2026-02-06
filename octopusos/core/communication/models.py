"""Data models for CommunicationOS.

This module defines the core data structures used throughout the
communication system, including requests, responses, policies, and audit records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any

from agentos.core.time import utc_now


class ConnectorType(str, Enum):
    """Types of external communication connectors."""

    WEB_SEARCH = "web_search"
    WEB_FETCH = "web_fetch"
    RSS = "rss"
    EMAIL_SMTP = "email_smtp"
    SLACK = "slack"
    CUSTOM = "custom"


class RequestStatus(str, Enum):
    """Status of a communication request."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    REQUIRE_ADMIN = "require_admin"  # Requires admin/human approval


class RiskLevel(str, Enum):
    """Risk level for communication operations."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TrustTier(str, Enum):
    """Information source trust level.

    CRITICAL PRINCIPLE: Search results are NOT truth - they are candidate sources.
    Higher tiers require verification and authoritative source validation.

    Trust hierarchy (lowest to highest):
    1. SEARCH_RESULT: Search engine results (candidates only, not facts)
    2. EXTERNAL_SOURCE: Fetched content (needs verification)
    3. PRIMARY_SOURCE: First-hand source (official sites, original docs)
    4. AUTHORITATIVE_SOURCE: Government, academia, certified organizations
    """

    SEARCH_RESULT = "search_result"        # Lowest: Search engine results (candidates)
    EXTERNAL_SOURCE = "external_source"    # Low: Fetched content (needs verification)
    PRIMARY_SOURCE = "primary_source"      # Medium: First-hand source (official sites, original docs)
    AUTHORITATIVE_SOURCE = "authoritative" # Highest: Government, academia, certified orgs


@dataclass
class CommunicationRequest:
    """Request to perform external communication.

    Attributes:
        id: Unique request identifier
        connector_type: Type of connector to use
        operation: Operation to perform (e.g., "search", "fetch", "send")
        params: Operation-specific parameters
        context: Additional context (task_id, session_id, etc.)
        status: Current request status
        risk_level: Assessed risk level
        approval_token: Optional token for approved requests
        execution_phase: Execution phase (planning/execution)
        created_at: Request creation timestamp
        updated_at: Last update timestamp
    """

    id: str
    connector_type: ConnectorType
    operation: str
    params: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)
    status: RequestStatus = RequestStatus.PENDING
    risk_level: RiskLevel = RiskLevel.MEDIUM
    approval_token: Optional[str] = None
    execution_phase: str = "execution"  # "planning" or "execution"
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary."""
        return {
            "id": self.id,
            "connector_type": self.connector_type.value,
            "operation": self.operation,
            "params": self.params,
            "context": self.context,
            "status": self.status.value,
            "risk_level": self.risk_level.value,
            "approval_token": self.approval_token,
            "execution_phase": self.execution_phase,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class CommunicationResponse:
    """Response from external communication.

    Attributes:
        request_id: ID of the originating request
        status: Response status
        data: Response data
        metadata: Additional response metadata
        evidence_id: ID of associated evidence record
        error: Error message if failed
        created_at: Response creation timestamp
    """

    request_id: str
    status: RequestStatus
    data: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    evidence_id: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary."""
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "data": self.data,
            "metadata": self.metadata,
            "evidence_id": self.evidence_id,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class CommunicationPolicy:
    """Policy for communication operations.

    Attributes:
        name: Policy name
        connector_type: Connector type this policy applies to
        allowed_operations: List of allowed operations
        blocked_domains: List of blocked domains
        allowed_domains: List of allowed domains (if specified, only these are allowed)
        require_approval: Whether requests require manual approval
        rate_limit_per_minute: Maximum requests per minute
        max_response_size_mb: Maximum response size in MB
        timeout_seconds: Request timeout in seconds
        sanitize_inputs: Whether to sanitize inputs
        sanitize_outputs: Whether to sanitize outputs
    """

    name: str
    connector_type: ConnectorType
    allowed_operations: List[str] = field(default_factory=list)
    blocked_domains: List[str] = field(default_factory=list)
    allowed_domains: List[str] = field(default_factory=list)
    require_approval: bool = False
    rate_limit_per_minute: int = 60
    max_response_size_mb: int = 10
    timeout_seconds: int = 30
    sanitize_inputs: bool = True
    sanitize_outputs: bool = True
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert policy to dictionary."""
        return {
            "name": self.name,
            "connector_type": self.connector_type.value,
            "allowed_operations": self.allowed_operations,
            "blocked_domains": self.blocked_domains,
            "allowed_domains": self.allowed_domains,
            "require_approval": self.require_approval,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "max_response_size_mb": self.max_response_size_mb,
            "timeout_seconds": self.timeout_seconds,
            "sanitize_inputs": self.sanitize_inputs,
            "sanitize_outputs": self.sanitize_outputs,
            "enabled": self.enabled,
        }


@dataclass
class EvidenceRecord:
    """Audit evidence for a communication operation.

    Attributes:
        id: Unique evidence identifier
        request_id: ID of the request
        connector_type: Type of connector used
        operation: Operation performed
        request_summary: Summary of request (sanitized)
        response_summary: Summary of response (sanitized)
        status: Operation status
        trust_tier: Trust level of the information source
        metadata: Additional metadata
        created_at: Evidence creation timestamp
    """

    id: str
    request_id: str
    connector_type: ConnectorType
    operation: str
    request_summary: Dict[str, Any]
    response_summary: Optional[Dict[str, Any]] = None
    status: RequestStatus = RequestStatus.SUCCESS
    trust_tier: TrustTier = TrustTier.EXTERNAL_SOURCE
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert evidence to dictionary."""
        return {
            "id": self.id,
            "request_id": self.request_id,
            "connector_type": self.connector_type.value,
            "operation": self.operation,
            "request_summary": self.request_summary,
            "response_summary": self.response_summary,
            "status": self.status.value,
            "trust_tier": self.trust_tier.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class PolicyVerdict:
    """Result of policy evaluation.

    Attributes:
        status: Verdict status (ALLOWED, DENIED, REQUIRE_ADMIN, etc.)
        reason_code: Machine-readable reason code
        hint: Human-readable explanation
        metadata: Additional verdict metadata
    """

    status: RequestStatus
    reason_code: str
    hint: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert verdict to dictionary."""
        return {
            "status": self.status.value,
            "reason_code": self.reason_code,
            "hint": self.hint,
            "metadata": self.metadata,
        }
