"""
Agent Authorization Models - AgentOS v3

Data models for Agent Capability Authorization system.

Design Philosophy:
- Immutable authorization results for audit trail
- Explicit escalation status tracking
- Rich context for all decisions
"""

from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field


class AgentTier(Enum):
    """
    Agent Trust Tiers - Progressive trust model

    Design:
    - Tier 0: Untrusted - No capabilities, complete isolation
    - Tier 1: Read-Only - Can observe state, no modifications
    - Tier 2: Propose - Can propose changes, requires approval
    - Tier 3: Trusted - Can execute local changes with audit
    """

    T0_UNTRUSTED = 0
    T1_READ_ONLY = 1
    T2_PROPOSE = 2
    T3_TRUSTED = 3

    @property
    def name_str(self) -> str:
        """Human-readable tier name"""
        names = {
            0: "Untrusted",
            1: "Read-Only",
            2: "Propose",
            3: "Trusted"
        }
        return names[self.value]

    @property
    def description(self) -> str:
        """Tier description"""
        descriptions = {
            0: "完全隔离，无基础权限",
            1: "只读访问，可观察状态",
            2: "可提议变更，需要审批",
            3: "可执行变更，完整审计"
        }
        return descriptions[self.value]

    @property
    def max_capabilities(self) -> int:
        """Maximum capabilities allowed at this tier"""
        limits = {
            0: 0,
            1: 5,
            2: 15,
            3: 50
        }
        return limits[self.value]

    @property
    def auto_grant_capabilities(self) -> List[str]:
        """Capabilities automatically granted at this tier"""
        auto_grants = {
            0: [],
            1: ["state.read", "evidence.query"],
            2: ["state.read", "evidence.query", "decision.propose"],
            3: ["state.read", "state.write", "action.execute.local"]
        }
        return auto_grants[self.value]


class EscalationStatus(Enum):
    """Status of escalation request"""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class EscalationPolicy(Enum):
    """Policy for handling missing capability grants"""

    DENY = "deny"                           # Immediately deny
    REQUEST_APPROVAL = "request_approval"   # Create escalation request
    TEMPORARY_GRANT = "temporary_grant"     # Grant for limited time
    LOG_ONLY = "log_only"                   # Log but allow (for monitoring)


@dataclass(frozen=True)
class AuthorizationResult:
    """
    Result of authorization check.

    Immutable for audit trail.

    Attributes:
        allowed: Whether operation is authorized
        reason: Human-readable reason for decision
        requires_approval: Whether approval is needed
        escalation_request_id: ID of created escalation request
        risk_score: Risk score (0.0-1.0)
        policy_violations: List of violated policies
        checked_at_ms: When check was performed (epoch ms)
        context: Additional context
    """

    allowed: bool
    reason: str
    requires_approval: bool = False
    escalation_request_id: Optional[str] = None
    risk_score: Optional[float] = None
    policy_violations: List[str] = field(default_factory=list)
    checked_at_ms: Optional[int] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "requires_approval": self.requires_approval,
            "escalation_request_id": self.escalation_request_id,
            "risk_score": self.risk_score,
            "policy_violations": self.policy_violations,
            "checked_at_ms": self.checked_at_ms,
            "context": self.context,
        }


@dataclass
class EscalationRequest:
    """
    Request for capability escalation.

    When an agent attempts to use a capability without grant,
    an escalation request can be created for admin approval.

    Attributes:
        request_id: Unique request identifier
        agent_id: Agent requesting capability
        requested_capability: Capability ID requested
        reason: Reason for request
        status: Current status
        requested_at_ms: When requested (epoch ms)
        reviewed_by: Admin who reviewed (if any)
        reviewed_at_ms: When reviewed (if any)
        deny_reason: Reason for denial (if denied)
        context: Additional context
    """

    request_id: str
    agent_id: str
    requested_capability: str
    reason: str
    status: EscalationStatus
    requested_at_ms: int
    reviewed_by: Optional[str] = None
    reviewed_at_ms: Optional[int] = None
    deny_reason: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "request_id": self.request_id,
            "agent_id": self.agent_id,
            "requested_capability": self.requested_capability,
            "reason": self.reason,
            "status": self.status.value,
            "requested_at_ms": self.requested_at_ms,
            "reviewed_by": self.reviewed_by,
            "reviewed_at_ms": self.reviewed_at_ms,
            "deny_reason": self.deny_reason,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EscalationRequest":
        """Create from dictionary"""
        return cls(
            request_id=data["request_id"],
            agent_id=data["agent_id"],
            requested_capability=data["requested_capability"],
            reason=data["reason"],
            status=EscalationStatus(data["status"]),
            requested_at_ms=data["requested_at_ms"],
            reviewed_by=data.get("reviewed_by"),
            reviewed_at_ms=data.get("reviewed_at_ms"),
            deny_reason=data.get("deny_reason"),
            context=data.get("context", {}),
        )


@dataclass
class AgentTierTransition:
    """
    Record of agent tier transition.

    Attributes:
        agent_id: Agent identifier
        from_tier: Previous tier
        to_tier: New tier
        changed_by: Who made the change
        reason: Reason for change
        changed_at_ms: When changed (epoch ms)
    """

    agent_id: str
    from_tier: AgentTier
    to_tier: AgentTier
    changed_by: str
    reason: str
    changed_at_ms: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_id": self.agent_id,
            "from_tier": self.from_tier.value,
            "to_tier": self.to_tier.value,
            "changed_by": self.changed_by,
            "reason": self.reason,
            "changed_at_ms": self.changed_at_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTierTransition":
        """Create from dictionary"""
        return cls(
            agent_id=data["agent_id"],
            from_tier=AgentTier(data["from_tier"]),
            to_tier=AgentTier(data["to_tier"]),
            changed_by=data["changed_by"],
            reason=data["reason"],
            changed_at_ms=data["changed_at_ms"],
        )
