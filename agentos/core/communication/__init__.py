"""Communication module for external network interactions.

This module provides secure, auditable external communication capabilities
for AgentOS, including web search, web fetch, RSS feeds, email, and messaging.

Key components:
- CommunicationService: Main service orchestrator
- PolicyEngine: Security policy enforcement
- Connectors: External service integrations
- Evidence: Request/response tracking and audit
- Sanitizers: Input/output security filtering
"""

from agentos.core.communication.service import CommunicationService
from agentos.core.communication.policy import PolicyEngine, CommunicationPolicy
from agentos.core.communication.models import (
    CommunicationRequest,
    CommunicationResponse,
    ConnectorType,
    RequestStatus,
)
from agentos.core.communication.evidence import EvidenceLogger
from agentos.core.communication.rate_limit import RateLimiter

__all__ = [
    "CommunicationService",
    "PolicyEngine",
    "CommunicationPolicy",
    "CommunicationRequest",
    "CommunicationResponse",
    "ConnectorType",
    "RequestStatus",
    "EvidenceLogger",
    "RateLimiter",
]
