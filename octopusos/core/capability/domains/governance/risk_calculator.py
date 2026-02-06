"""
Risk Calculator - Multi-factor risk assessment

Implements GC-003: governance.risk.score

Design Philosophy:
- Risk is calculated from multiple weighted factors
- Output is normalized 0.0-1.0 score
- Risk level classification: LOW/MEDIUM/HIGH/CRITICAL
- Transparent: All factors and contributions are returned

Risk Factors:
1. Capability risk level (from capability definition)
2. Agent trust tier (T0-T4)
3. Side effects count and type
4. Historical failure rate
5. Estimated cost
6. Operation complexity
"""

import logging
from typing import Dict, List, Optional

from agentos.core.time import utc_now_ms
from agentos.core.capability.domains.governance.models import (
    RiskScore,
    RiskFactor,
    RiskLevel,
    GovernanceContext,
    TrustTier,
)
from agentos.core.capability.models import RiskLevel as CapabilityRiskLevel


logger = logging.getLogger(__name__)


class RiskCalculator:
    """
    Multi-factor risk calculator.

    Calculates risk scores for operations based on:
    - Capability inherent risk
    - Agent trust level
    - Operation characteristics
    - Historical data

    Risk Score Formula:
        score = Σ (factor_weight * factor_value)

    Output:
        - score: 0.0-1.0 (normalized)
        - level: LOW (<0.3), MEDIUM (0.3-0.6), HIGH (0.6-0.85), CRITICAL (>0.85)
    """

    # Factor weights (must sum to 1.0)
    WEIGHT_CAPABILITY_RISK = 0.30
    WEIGHT_TRUST_TIER = 0.25
    WEIGHT_SIDE_EFFECTS = 0.20
    WEIGHT_HISTORICAL = 0.15
    WEIGHT_COST = 0.10

    def __init__(self):
        """Initialize risk calculator"""
        logger.debug("RiskCalculator initialized")

    def calculate(
        self,
        capability_id: str,
        context: GovernanceContext,
    ) -> RiskScore:
        """
        Calculate risk score for operation.

        Args:
            capability_id: Capability being invoked
            context: Governance context

        Returns:
            RiskScore with level and factors
        """
        factors = []

        # Factor 1: Capability risk level
        capability_risk_value = self._calculate_capability_risk(capability_id)
        factors.append(
            RiskFactor(
                factor_name="capability_risk",
                weight=self.WEIGHT_CAPABILITY_RISK,
                value=capability_risk_value,
                contribution=self.WEIGHT_CAPABILITY_RISK * capability_risk_value,
                explanation=f"Capability {capability_id} inherent risk level",
            )
        )

        # Factor 2: Trust tier
        trust_tier_value = self._calculate_trust_tier_risk(context.trust_tier)
        factors.append(
            RiskFactor(
                factor_name="trust_tier",
                weight=self.WEIGHT_TRUST_TIER,
                value=trust_tier_value,
                contribution=self.WEIGHT_TRUST_TIER * trust_tier_value,
                explanation=f"Agent trust tier: {context.trust_tier.value}",
            )
        )

        # Factor 3: Side effects
        side_effects_value = self._calculate_side_effects_risk(context.side_effects)
        factors.append(
            RiskFactor(
                factor_name="side_effects",
                weight=self.WEIGHT_SIDE_EFFECTS,
                value=side_effects_value,
                contribution=self.WEIGHT_SIDE_EFFECTS * side_effects_value,
                explanation=f"{len(context.side_effects)} side effects expected",
            )
        )

        # Factor 4: Historical failure rate
        historical_value = self._calculate_historical_risk(
            agent_id=context.agent_id,
            capability_id=capability_id,
        )
        factors.append(
            RiskFactor(
                factor_name="historical",
                weight=self.WEIGHT_HISTORICAL,
                value=historical_value,
                contribution=self.WEIGHT_HISTORICAL * historical_value,
                explanation="Historical failure rate for this agent/capability",
            )
        )

        # Factor 5: Cost
        cost_value = self._calculate_cost_risk(
            estimated_cost=context.estimated_cost,
            estimated_tokens=context.estimated_tokens,
        )
        factors.append(
            RiskFactor(
                factor_name="cost",
                weight=self.WEIGHT_COST,
                value=cost_value,
                contribution=self.WEIGHT_COST * cost_value,
                explanation=f"Estimated cost: ${context.estimated_cost or 0:.4f}",
            )
        )

        # Calculate total score (0.0-1.0)
        total_score = sum(f.contribution for f in factors)
        total_score = max(0.0, min(1.0, total_score))  # Clamp to [0, 1]

        # Classify risk level
        risk_level = self._classify_risk_level(total_score)

        # Determine if mitigation is required
        mitigation_required = self._requires_mitigation(risk_level, total_score)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            risk_level=risk_level,
            factors=factors,
            context=context,
        )

        return RiskScore(
            score=total_score,
            level=risk_level,
            factors=factors,
            mitigation_required=mitigation_required,
            recommended_actions=recommendations,
            assessed_at_ms=utc_now_ms(),
        )

    def _calculate_capability_risk(self, capability_id: str) -> float:
        """
        Calculate risk value from capability definition.

        Returns:
            0.0-1.0 risk value
        """
        # Import here to avoid circular dependency
        from agentos.core.capability.registry import get_capability_registry

        registry = get_capability_registry()
        capability = registry.get_capability(capability_id)

        if capability is None:
            # Unknown capability = high risk
            return 0.8

        # Map capability risk level to 0.0-1.0
        risk_mapping = {
            CapabilityRiskLevel.LOW: 0.1,
            CapabilityRiskLevel.MEDIUM: 0.4,
            CapabilityRiskLevel.HIGH: 0.7,
            CapabilityRiskLevel.CRITICAL: 0.95,
        }

        return risk_mapping.get(capability.risk_level, 0.5)

    def _calculate_trust_tier_risk(self, trust_tier: TrustTier) -> float:
        """
        Calculate risk value from agent trust tier.

        Lower trust = higher risk

        Returns:
            0.0-1.0 risk value
        """
        trust_mapping = {
            TrustTier.T4: 0.0,   # Full trust = no risk
            TrustTier.T3: 0.2,   # High trust = low risk
            TrustTier.T2: 0.4,   # Basic trust = medium risk
            TrustTier.T1: 0.7,   # Limited trust = high risk
            TrustTier.T0: 1.0,   # Untrusted = maximum risk
        }

        return trust_mapping.get(trust_tier, 0.8)

    def _calculate_side_effects_risk(self, side_effects: List[str]) -> float:
        """
        Calculate risk value from side effects count and type.

        More side effects = higher risk
        Irreversible side effects = much higher risk

        Returns:
            0.0-1.0 risk value
        """
        if not side_effects:
            return 0.0

        # Base risk from count
        count_risk = min(0.5, len(side_effects) * 0.15)

        # Additional risk for dangerous side effects
        dangerous_effects = [
            "irreversible_action",
            "file_system_write",
            "database_write",
            "external_call",
        ]

        dangerous_count = sum(
            1 for effect in side_effects if any(d in effect.lower() for d in dangerous_effects)
        )

        dangerous_risk = min(0.5, dangerous_count * 0.2)

        return min(1.0, count_risk + dangerous_risk)

    def _calculate_historical_risk(
        self,
        agent_id: str,
        capability_id: str,
    ) -> float:
        """
        Calculate risk from historical failure rate.

        Query recent invocations and calculate failure rate.

        Returns:
            0.0-1.0 risk value
        """
        # This would query capability_invocations table for recent failures
        # For now, return baseline (no historical data)
        return 0.3  # Medium baseline

    def _calculate_cost_risk(
        self,
        estimated_cost: Optional[float],
        estimated_tokens: Optional[int],
    ) -> float:
        """
        Calculate risk from estimated cost.

        Higher cost = higher risk (expensive mistakes are worse)

        Returns:
            0.0-1.0 risk value
        """
        if estimated_cost is None and estimated_tokens is None:
            return 0.1  # Low risk if no cost

        # Cost-based risk
        cost_risk = 0.0
        if estimated_cost:
            # $0.01 = 0.1, $0.10 = 0.3, $1.00 = 0.6, $10+ = 1.0
            cost_risk = min(1.0, estimated_cost * 0.6)

        # Token-based risk
        token_risk = 0.0
        if estimated_tokens:
            # 1000 tokens = 0.2, 10000 = 0.5, 100000+ = 1.0
            token_risk = min(1.0, estimated_tokens / 100000)

        return max(cost_risk, token_risk)

    def _classify_risk_level(self, score: float) -> RiskLevel:
        """
        Classify risk score into level.

        Args:
            score: Risk score (0.0-1.0)

        Returns:
            RiskLevel enum
        """
        if score < 0.3:
            return RiskLevel.LOW
        elif score < 0.6:
            return RiskLevel.MEDIUM
        elif score < 0.85:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def _requires_mitigation(self, risk_level: RiskLevel, score: float) -> bool:
        """
        Determine if risk requires mitigation/approval.

        Args:
            risk_level: Risk level classification
            score: Numeric risk score

        Returns:
            True if mitigation is required
        """
        # HIGH and CRITICAL always require mitigation
        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return True

        # MEDIUM risk above 0.5 requires mitigation
        if risk_level == RiskLevel.MEDIUM and score > 0.5:
            return True

        return False

    def _generate_recommendations(
        self,
        risk_level: RiskLevel,
        factors: List[RiskFactor],
        context: GovernanceContext,
    ) -> List[str]:
        """
        Generate risk mitigation recommendations.

        Args:
            risk_level: Risk level classification
            factors: Risk factors
            context: Governance context

        Returns:
            List of recommended actions
        """
        recommendations = []

        if risk_level == RiskLevel.CRITICAL:
            recommendations.append("CRITICAL: Requires explicit admin approval")
            recommendations.append("Consider alternative lower-risk approaches")

        if risk_level == RiskLevel.HIGH:
            recommendations.append("Requires approval from authorized user")
            recommendations.append("Verify operation parameters carefully")

        # Factor-specific recommendations
        for factor in factors:
            if factor.factor_name == "trust_tier" and factor.value > 0.6:
                recommendations.append(
                    "Agent has low trust tier - consider increasing trust through verification"
                )

            if factor.factor_name == "side_effects" and factor.value > 0.5:
                recommendations.append(
                    "Operation has significant side effects - ensure rollback plan exists"
                )

            if factor.factor_name == "cost" and factor.value > 0.5:
                recommendations.append(
                    "High cost operation - verify budget and consider alternatives"
                )

        if not recommendations:
            recommendations.append("No specific mitigations required")

        return recommendations
