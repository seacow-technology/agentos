"""
Governance Domain Models

Data models for the Governance Capability system (GC-001 to GC-006).

Design Philosophy:
- Policy is NOT hard-coded rules
- Policy is evolvable, versioned, auditable decision logic
- All governance decisions are recorded and traceable
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime


# ===================================================================
# Enums
# ===================================================================


class RiskLevel(str, Enum):
    """Risk level classification"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PolicyAction(str, Enum):
    """Policy evaluation decision"""
    ALLOW = "ALLOW"           # Operation permitted
    DENY = "DENY"             # Operation blocked
    ESCALATE = "ESCALATE"     # Requires human review
    WARN = "WARN"             # Allow but log warning


class ConditionType(str, Enum):
    """Policy condition evaluation types"""
    THRESHOLD = "threshold"           # Numeric threshold (>, <, ==)
    PATTERN = "pattern"               # Regex pattern matching
    EXPRESSION = "expression"         # Python expression evaluation
    TIME_WINDOW = "time_window"       # Time-based conditions
    TRUST_TIER = "trust_tier"         # Agent trust level
    HISTORICAL = "historical"         # Based on historical data


class ResourceType(str, Enum):
    """Resource quota types"""
    TOKENS = "tokens"             # LLM token usage
    API_CALLS = "api_calls"       # API call count
    STORAGE = "storage"           # Storage bytes
    COST_USD = "cost_usd"         # Dollar cost
    COMPUTE_TIME = "compute_time" # Compute milliseconds


class TrustTier(str, Enum):
    """Agent trust tier classification"""
    T0 = "T0"  # Untrusted (sandbox only)
    T1 = "T1"  # Limited trust (read-only)
    T2 = "T2"  # Basic trust (propose)
    T3 = "T3"  # High trust (write)
    T4 = "T4"  # Full trust (admin)


# ===================================================================
# Permission Check Models (GC-001)
# ===================================================================


class PermissionResult(BaseModel):
    """
    Result of permission check (GC-001).

    Returned by governance.permission.check capability.
    """
    allowed: bool = Field(
        description="Whether permission is granted"
    )
    reason: str = Field(
        description="Human-readable reason for decision"
    )
    conditions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Conditional permissions (time window, quota, etc)"
    )
    risk_score: Optional[float] = Field(
        default=None,
        description="Risk score that influenced decision (0.0-1.0)"
    )
    policy_ids: List[str] = Field(
        default_factory=list,
        description="Policy IDs that were evaluated"
    )
    checked_at_ms: int = Field(
        description="When check was performed (epoch ms)"
    )

    @property
    def has_conditions(self) -> bool:
        """Check if permission has conditional restrictions"""
        return self.conditions is not None and len(self.conditions) > 0


# ===================================================================
# Policy Models (GC-002, GC-006)
# ===================================================================


class PolicyRule(BaseModel):
    """
    Single rule within a policy.

    A rule consists of:
    - condition: Expression to evaluate (Python-like syntax)
    - action: What to do if condition is True
    - rationale: Why this rule exists (for audit)
    """
    condition: str = Field(
        description="Condition expression (e.g., 'estimated_cost > budget * 0.8')"
    )
    condition_type: ConditionType = Field(
        default=ConditionType.EXPRESSION,
        description="Type of condition evaluation"
    )
    action: PolicyAction = Field(
        description="Action to take if condition is True"
    )
    rationale: str = Field(
        description="Human-readable explanation of why this rule exists"
    )
    priority: int = Field(
        default=100,
        description="Rule priority (lower number = higher priority)"
    )

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """
        Evaluate rule condition against context.

        Args:
            context: Evaluation context (variables available in condition)

        Returns:
            True if condition is met, False otherwise
        """
        # Simple expression evaluation (production would use ast.parse for safety)
        try:
            # Create safe evaluation environment
            safe_globals = {
                "__builtins__": {},
                "abs": abs,
                "min": min,
                "max": max,
                "len": len,
            }
            return bool(eval(self.condition, safe_globals, context))
        except Exception as e:
            # If evaluation fails, default to False (safe fail)
            return False


class PolicyEvolutionRecord(BaseModel):
    """Record of policy evolution (for GC-006)"""
    version: str = Field(description="Version identifier (semver)")
    changes: str = Field(description="What changed in this version")
    reason: str = Field(description="Why the change was made")
    changed_by: str = Field(description="Who made the change")
    date: str = Field(description="When change was made (ISO8601)")


class Policy(BaseModel):
    """
    Policy definition (GC-002, GC-006).

    Policies are:
    - Versioned (semver)
    - Evolvable (can be updated via GC-006)
    - Auditable (all changes recorded)
    - Domain-scoped (apply to specific capability domains)
    """
    policy_id: str = Field(
        description="Unique policy identifier"
    )
    version: str = Field(
        description="Policy version (semver format: 1.0.0)"
    )
    domain: str = Field(
        description="Domain this policy applies to (or 'global')"
    )
    name: str = Field(
        description="Human-readable policy name"
    )
    description: str = Field(
        description="What this policy enforces"
    )
    rules: List[PolicyRule] = Field(
        description="List of policy rules (evaluated in priority order)"
    )
    active: bool = Field(
        default=True,
        description="Whether policy is currently active"
    )
    evolution_history: List[PolicyEvolutionRecord] = Field(
        default_factory=list,
        description="History of policy changes"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional policy metadata"
    )

    def evaluate(self, context: Dict[str, Any]) -> PolicyDecision:
        """
        Evaluate policy against context.

        Evaluates all rules in priority order and returns first matching action.

        Args:
            context: Evaluation context

        Returns:
            PolicyDecision with action and triggered rules
        """
        triggered_rules = []
        final_action = PolicyAction.ALLOW  # Default to allow

        # Sort rules by priority (lower = higher priority)
        sorted_rules = sorted(self.rules, key=lambda r: r.priority)

        for rule in sorted_rules:
            if rule.evaluate(context):
                triggered_rules.append({
                    "condition": rule.condition,
                    "action": rule.action.value,
                    "rationale": rule.rationale,
                })
                # First matching rule determines action
                if not triggered_rules:  # Only set if first match
                    final_action = rule.action
                    break  # Stop at first match

        return PolicyDecision(
            policy_id=self.policy_id,
            policy_version=self.version,
            decision=final_action,
            rules_triggered=triggered_rules,
            confidence=1.0 if triggered_rules else 0.5,  # High confidence if rule matched
            context=context,
        )


class PolicyDecision(BaseModel):
    """
    Result of policy evaluation (GC-002).

    Returned by governance.policy.evaluate capability.
    """
    policy_id: str = Field(
        description="Policy that was evaluated"
    )
    policy_version: str = Field(
        description="Version of policy used"
    )
    decision: PolicyAction = Field(
        description="Policy decision (ALLOW/DENY/ESCALATE/WARN)"
    )
    rules_triggered: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Rules that were triggered"
    )
    confidence: float = Field(
        description="Confidence in decision (0.0-1.0)"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Evaluation context (for audit)"
    )
    evaluated_at_ms: Optional[int] = Field(
        default=None,
        description="When evaluation occurred (epoch ms)"
    )

    @property
    def is_allowed(self) -> bool:
        """Check if decision allows operation"""
        return self.decision in (PolicyAction.ALLOW, PolicyAction.WARN)

    @property
    def requires_escalation(self) -> bool:
        """Check if decision requires human escalation"""
        return self.decision == PolicyAction.ESCALATE


# ===================================================================
# Risk Score Models (GC-003)
# ===================================================================


class RiskFactor(BaseModel):
    """Single factor contributing to risk score"""
    factor_name: str = Field(
        description="Name of risk factor"
    )
    weight: float = Field(
        description="Weight of this factor (0.0-1.0)"
    )
    value: float = Field(
        description="Actual value (0.0-1.0)"
    )
    contribution: float = Field(
        description="Contribution to total score (weight * value)"
    )
    explanation: str = Field(
        description="Human-readable explanation"
    )


class RiskScore(BaseModel):
    """
    Risk assessment result (GC-003).

    Returned by governance.risk.score capability.
    """
    score: float = Field(
        description="Overall risk score (0.0-1.0, where 1.0 = highest risk)"
    )
    level: RiskLevel = Field(
        description="Risk level classification"
    )
    factors: List[RiskFactor] = Field(
        description="Factors that contributed to score"
    )
    mitigation_required: bool = Field(
        description="Whether mitigation/approval is required"
    )
    recommended_actions: List[str] = Field(
        default_factory=list,
        description="Recommended risk mitigation actions"
    )
    assessed_at_ms: int = Field(
        description="When assessment was performed (epoch ms)"
    )

    @property
    def is_high_risk(self) -> bool:
        """Check if risk is HIGH or CRITICAL"""
        return self.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    @property
    def allows_proceed(self) -> bool:
        """Check if risk level allows proceeding without mitigation"""
        return self.level in (RiskLevel.LOW, RiskLevel.MEDIUM) and not self.mitigation_required


# ===================================================================
# Override Models (GC-004)
# ===================================================================


class OverrideToken(BaseModel):
    """
    Emergency override token (GC-004).

    Created by governance.override.admin capability.
    """
    override_id: str = Field(
        description="Unique override token identifier"
    )
    admin_id: str = Field(
        description="Admin who created override"
    )
    blocked_operation: str = Field(
        description="Description of blocked operation being overridden"
    )
    override_reason: str = Field(
        description="Reason for override (minimum 100 characters)"
    )
    expires_at_ms: int = Field(
        description="When override expires (epoch ms)"
    )
    used: bool = Field(
        default=False,
        description="Whether override has been used (single-use)"
    )
    used_at_ms: Optional[int] = Field(
        default=None,
        description="When override was used (epoch ms)"
    )
    created_at_ms: int = Field(
        description="When override was created (epoch ms)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional override metadata"
    )

    @property
    def is_valid(self) -> bool:
        """Check if override is valid (not used and not expired)"""
        from agentos.core.time import utc_now_ms
        now = utc_now_ms()
        return not self.used and now < self.expires_at_ms

    @property
    def is_expired(self) -> bool:
        """Check if override has expired"""
        from agentos.core.time import utc_now_ms
        return utc_now_ms() >= self.expires_at_ms


# ===================================================================
# Quota Models (GC-005)
# ===================================================================


class QuotaStatus(BaseModel):
    """
    Resource quota status (GC-005).

    Returned by governance.quota.check capability.
    """
    resource_type: ResourceType = Field(
        description="Type of resource"
    )
    agent_id: str = Field(
        description="Agent identifier"
    )
    current_usage: float = Field(
        description="Current usage amount"
    )
    limit: float = Field(
        description="Maximum allowed usage"
    )
    remaining: float = Field(
        description="Remaining quota (limit - current_usage)"
    )
    reset_at_ms: Optional[int] = Field(
        default=None,
        description="When quota resets (epoch ms, None = no reset)"
    )
    usage_percentage: float = Field(
        description="Usage as percentage of limit (0.0-100.0)"
    )
    exceeded: bool = Field(
        description="Whether quota has been exceeded"
    )
    checked_at_ms: int = Field(
        description="When check was performed (epoch ms)"
    )

    @property
    def is_near_limit(self, threshold: float = 0.8) -> bool:
        """Check if usage is near limit (default: 80%)"""
        return self.usage_percentage >= (threshold * 100)

    @property
    def allows_proceed(self) -> bool:
        """Check if quota allows operation to proceed"""
        return not self.exceeded


# ===================================================================
# Governance Context
# ===================================================================


class GovernanceContext(BaseModel):
    """
    Context for governance evaluation.

    Passed to all governance checks to provide decision context.
    """
    agent_id: str = Field(
        description="Agent requesting operation"
    )
    capability_id: str = Field(
        description="Capability being invoked"
    )
    operation: str = Field(
        description="Specific operation within capability"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Operation parameters"
    )
    trust_tier: TrustTier = Field(
        default=TrustTier.T0,
        description="Agent trust tier"
    )
    estimated_cost: Optional[float] = Field(
        default=None,
        description="Estimated cost in USD"
    )
    estimated_tokens: Optional[int] = Field(
        default=None,
        description="Estimated token usage"
    )
    side_effects: List[str] = Field(
        default_factory=list,
        description="Expected side effects"
    )
    project_id: Optional[str] = Field(
        default=None,
        description="Project context"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context"
    )
