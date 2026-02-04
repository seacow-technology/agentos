"""
Policy Rules

Defines individual policy rules that can be evaluated.
Each rule returns (decision, reason, rule_name).
"""

from typing import Tuple, Optional
from .models import PolicyDecision, PolicyContext


def rule_revoked_authorization(context: PolicyContext) -> Tuple[Optional[PolicyDecision], Optional[str], str]:
    """
    Rule 1: Revoked authorization → DENY

    Highest priority rule. If authorization is revoked, deny immediately.

    Returns:
        (decision, reason, rule_name) or (None, None, rule_name) if rule doesn't apply
    """
    rule_name = "REVOKED_AUTH"

    if context.auth_status == "revoked":
        return (
            PolicyDecision.DENY,
            "Authorization has been revoked",
            rule_name
        )

    return (None, None, rule_name)


def rule_sandbox_required(context: PolicyContext) -> Tuple[Optional[PolicyDecision], Optional[str], str]:
    """
    Rule 2: HIGH tier + Sandbox unavailable → DENY

    HIGH risk extensions MUST run in sandbox. If sandbox is not available, deny.

    Returns:
        (decision, reason, rule_name) or (None, None, rule_name) if rule doesn't apply
    """
    rule_name = "SANDBOX_REQUIRED"

    # Check if tier is HIGH (could be from TrustTier enum value)
    is_high_tier = (
        context.tier == "HIGH" or
        context.tier == "T3" or  # Cloud MCP highest risk
        "high" in context.tier.lower()
    )

    if is_high_tier and not context.sandbox_available:
        return (
            PolicyDecision.DENY,
            f"HIGH risk tier requires sandbox but sandbox is unavailable",
            rule_name
        )

    return (None, None, rule_name)


def rule_high_tier_approval(context: PolicyContext) -> Tuple[Optional[PolicyDecision], Optional[str], str]:
    """
    Rule 3: HIGH tier → REQUIRE_APPROVAL

    HIGH tier extensions require human approval before execution.

    Returns:
        (decision, reason, rule_name) or (None, None, rule_name) if rule doesn't apply
    """
    rule_name = "HIGH_TIER_APPROVAL"

    # Check if tier is HIGH
    is_high_tier = (
        context.tier == "HIGH" or
        context.tier == "T3" or
        "high" in context.tier.lower()
    )

    if is_high_tier and context.sandbox_available:
        # Sandbox is available, but still require approval
        return (
            PolicyDecision.REQUIRE_APPROVAL,
            f"HIGH risk tier ({context.tier}) requires human approval",
            rule_name
        )

    return (None, None, rule_name)


def rule_high_risk_score(context: PolicyContext, threshold: float = 70.0) -> Tuple[Optional[PolicyDecision], Optional[str], str]:
    """
    Rule 4: Risk score > threshold → REQUIRE_APPROVAL

    High risk scores require human approval.

    Args:
        context: Policy context
        threshold: Risk score threshold (default 70.0)

    Returns:
        (decision, reason, rule_name) or (None, None, rule_name) if rule doesn't apply
    """
    rule_name = "HIGH_RISK_SCORE"

    if context.risk_score > threshold:
        return (
            PolicyDecision.REQUIRE_APPROVAL,
            f"Risk score {context.risk_score:.1f} exceeds threshold {threshold}",
            rule_name
        )

    return (None, None, rule_name)


def rule_execution_limit(
    context: PolicyContext,
    daily_limit: int = 100
) -> Tuple[Optional[PolicyDecision], Optional[str], str]:
    """
    Rule 5: Daily execution limit → DENY

    Extensions have a daily execution limit to prevent abuse.

    Args:
        context: Policy context
        daily_limit: Maximum executions per day (default 100)

    Returns:
        (decision, reason, rule_name) or (None, None, rule_name) if rule doesn't apply
    """
    rule_name = "EXECUTION_LIMIT"

    if context.execution_count_today >= daily_limit:
        return (
            PolicyDecision.DENY,
            f"Daily execution limit reached: {context.execution_count_today}/{daily_limit}",
            rule_name
        )

    return (None, None, rule_name)


def rule_unauthorized(context: PolicyContext) -> Tuple[Optional[PolicyDecision], Optional[str], str]:
    """
    Rule 6: Not authorized → DENY

    If authorization check failed, deny execution.

    Returns:
        (decision, reason, rule_name) or (None, None, rule_name) if rule doesn't apply
    """
    rule_name = "UNAUTHORIZED"

    if not context.auth_allowed:
        return (
            PolicyDecision.DENY,
            f"Extension not authorized: {context.auth_status}",
            rule_name
        )

    return (None, None, rule_name)


def rule_trust_degrading_high_tier(context: PolicyContext) -> Tuple[Optional[PolicyDecision], Optional[str], str]:
    """
    Rule 7 (E5): DEGRADING trust + HIGH tier → DENY

    When trust is degrading for high-risk operations, block execution.
    This prevents failing extensions from causing damage.

    Returns:
        (decision, reason, rule_name) or (None, None, rule_name) if rule doesn't apply
    """
    rule_name = "TRUST_DEGRADING_HIGH_TIER"

    if context.trust_state == "DEGRADING":
        # Check if tier is HIGH or MEDIUM
        is_high_tier = (
            context.tier == "HIGH" or
            context.tier == "T3" or
            "high" in context.tier.lower()
        )

        if is_high_tier:
            return (
                PolicyDecision.DENY,
                f"Trust is degrading for HIGH tier extension - execution blocked",
                rule_name
            )

    return (None, None, rule_name)


def rule_trust_degrading_medium_tier(context: PolicyContext) -> Tuple[Optional[PolicyDecision], Optional[str], str]:
    """
    Rule 8 (E5): DEGRADING trust + MEDIUM tier → DENY

    When trust is degrading for medium-risk operations, also block.
    Trust must be restored before allowing execution.

    Returns:
        (decision, reason, rule_name) or (None, None, rule_name) if rule doesn't apply
    """
    rule_name = "TRUST_DEGRADING_MEDIUM_TIER"

    if context.trust_state == "DEGRADING":
        # Check if tier is MEDIUM
        is_medium_tier = (
            context.tier == "MEDIUM" or
            context.tier == "MED" or
            context.tier == "T2" or
            "medium" in context.tier.lower() or
            "med" in context.tier.lower()
        )

        if is_medium_tier:
            return (
                PolicyDecision.DENY,
                f"Trust is degrading for MEDIUM tier extension - execution blocked until trust restored",
                rule_name
            )

    return (None, None, rule_name)


def rule_trust_earning_medium_tier(context: PolicyContext) -> Tuple[Optional[PolicyDecision], Optional[str], str]:
    """
    Rule 9 (E5): EARNING trust + MEDIUM tier → REQUIRE_APPROVAL

    Extensions still earning trust require approval for medium-risk operations.
    This is cautious but not blocking.

    Returns:
        (decision, reason, rule_name) or (None, None, rule_name) if rule doesn't apply
    """
    rule_name = "TRUST_EARNING_MEDIUM_TIER"

    if context.trust_state == "EARNING":
        # Check if tier is MEDIUM
        is_medium_tier = (
            context.tier == "MEDIUM" or
            context.tier == "MED" or
            context.tier == "T2" or
            "medium" in context.tier.lower() or
            "med" in context.tier.lower()
        )

        if is_medium_tier:
            return (
                PolicyDecision.REQUIRE_APPROVAL,
                f"Extension is still earning trust - require approval for MEDIUM tier operation",
                rule_name
            )

    return (None, None, rule_name)


def rule_trust_stable_medium_tier(context: PolicyContext) -> Tuple[Optional[PolicyDecision], Optional[str], str]:
    """
    Rule 10 (E5): STABLE trust + MEDIUM tier + LOW risk → ALLOW

    Extensions with stable trust and low risk scores can execute without approval.
    This is the reward for building trust over time.

    Returns:
        (decision, reason, rule_name) or (None, None, rule_name) if rule doesn't apply
    """
    rule_name = "TRUST_STABLE_MEDIUM_TIER"

    if context.trust_state == "STABLE":
        # Check if tier is MEDIUM and risk is low
        is_medium_tier = (
            context.tier == "MEDIUM" or
            context.tier == "MED" or
            context.tier == "T2" or
            "medium" in context.tier.lower() or
            "med" in context.tier.lower()
        )

        # Risk score < 50 is considered low for MEDIUM tier
        if is_medium_tier and context.risk_score < 50.0:
            return (
                PolicyDecision.ALLOW,
                f"Trust is stable and risk is low - allow MEDIUM tier execution",
                rule_name
            )

    return (None, None, rule_name)


# List of all rules in priority order
ALL_RULES = [
    rule_revoked_authorization,  # Highest priority
    rule_unauthorized,
    rule_sandbox_required,
    # E5: Trust State rules (must come before general tier rules)
    rule_trust_degrading_high_tier,  # DEGRADING + HIGH → DENY
    rule_trust_degrading_medium_tier,  # DEGRADING + MEDIUM → DENY
    rule_trust_stable_medium_tier,  # STABLE + MEDIUM + LOW risk → ALLOW (early exit)
    rule_high_tier_approval,  # General HIGH tier rule
    rule_trust_earning_medium_tier,  # EARNING + MEDIUM → REQUIRE_APPROVAL
    rule_high_risk_score,
    rule_execution_limit,  # Lowest priority
]
