"""
Governance Domain - Capability-based Governance System

This domain implements 6 Governance Capabilities (GC-001 to GC-006):

1. governance.permission.check (GC-001) - Permission checking
2. governance.policy.evaluate (GC-002) - Policy evaluation
3. governance.risk.score (GC-003) - Risk assessment
4. governance.override.admin (GC-004) - Emergency override
5. governance.quota.check (GC-005) - Resource quota checking
6. governance.policy.evolve (GC-006) - Policy evolution

Design Philosophy:
- Policy ≠ Rule
- Policy = Evolvable, auditable decision layer
- Governance itself is a Capability, not if/else logic
"""

from .models import (
    PermissionResult,
    PolicyDecision,
    RiskScore,
    QuotaStatus,
    OverrideToken,
    Policy,
    PolicyRule,
    RiskFactor,
    ConditionType,
    PolicyAction,
    RiskLevel,
)
from .governance_engine import GovernanceEngine, get_governance_engine
from .policy_registry import PolicyRegistry, get_policy_registry
from .risk_calculator import RiskCalculator
from .override_manager import OverrideManager

__all__ = [
    # Models
    "PermissionResult",
    "PolicyDecision",
    "RiskScore",
    "QuotaStatus",
    "OverrideToken",
    "Policy",
    "PolicyRule",
    "RiskFactor",
    "ConditionType",
    "PolicyAction",
    "RiskLevel",
    # Engines
    "GovernanceEngine",
    "get_governance_engine",
    "PolicyRegistry",
    "get_policy_registry",
    "RiskCalculator",
    "OverrideManager",
]
