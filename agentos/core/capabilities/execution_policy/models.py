"""
Policy Engine Models

Data models for Policy Engine decisions and contexts.
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List, Any


class PolicyDecision(Enum):
    """Policy decision result"""
    ALLOW = "allow"  # Allow execution
    DENY = "deny"  # Deny execution
    REQUIRE_APPROVAL = "require_approval"  # Require human approval


@dataclass
class PolicyEvaluationRequest:
    """Policy evaluation request"""
    extension_id: str
    action_id: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PolicyContext:
    """
    Policy evaluation context

    Contains all input information for policy evaluation.
    """
    extension_id: str
    action_id: str
    session_id: Optional[str]
    tier: str  # TrustTier value
    risk_score: float
    auth_allowed: bool
    auth_status: str
    sandbox_available: bool
    request_metadata: Optional[Dict[str, Any]]
    execution_count_today: int = 0
    trust_state: Optional[str] = None  # E5: Trust Evolution State (EARNING/STABLE/DEGRADING)


@dataclass
class PolicyDecisionResult:
    """
    Policy decision result

    Contains the final decision and all supporting information.
    """
    decision: PolicyDecision
    reason: str
    rules_applied: List[str]
    context: PolicyContext
    decided_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "rules_applied": self.rules_applied,
            "context": {
                "extension_id": self.context.extension_id,
                "action_id": self.context.action_id,
                "tier": self.context.tier,
                "risk_score": self.context.risk_score,
                "auth_allowed": self.context.auth_allowed,
                "auth_status": self.context.auth_status,
                "sandbox_available": self.context.sandbox_available,
                "execution_count_today": self.context.execution_count_today,
                "trust_state": self.context.trust_state
            },
            "decided_at": int(self.decided_at.timestamp() * 1000)
        }
