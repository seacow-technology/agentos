"""
Trust Tier Engine

Determines Trust Tier based on Risk Score.
Trust Tiers are calculated results, not manual configurations.

Core principle: Tier = f(Risk Score)
- LOW: 0-30 (read-only, idempotent)
- MEDIUM: 30-70 (writable but reversible)
- HIGH: 70-100 (external calls, irreversible)
"""

from typing import Optional

from agentos.core.time.clock import utc_now
from agentos.core.capabilities.risk import RiskScorer, RiskScore
from .models import TrustTier, TierInfo
from .history import TierHistory


class TrustTierEngine:
    """
    Trust Tier determination engine.

    Responsibilities:
    1. Calculate Risk Score (via RiskScorer)
    2. Map Risk Score to Trust Tier
    3. Track tier changes over time
    4. Generate human-readable explanations
    """

    def __init__(self, db_path: str):
        """
        Initialize trust tier engine.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.risk_scorer = RiskScorer(db_path)
        self.tier_history = TierHistory(db_path)

    def get_tier(
        self,
        extension_id: str,
        action_id: str = "*"
    ) -> TierInfo:
        """
        Get Trust Tier for an extension/action.

        Steps:
        1. Calculate Risk Score (via D2 RiskScorer)
        2. Map Risk Score to Tier
        3. Check for tier changes
        4. Record changes if detected
        5. Generate explanation

        Args:
            extension_id: Extension identifier
            action_id: Action identifier (default "*" for all actions)

        Returns:
            TierInfo with tier, risk_score, explanation, and metadata
        """
        # 1. Calculate Risk Score
        risk = self.risk_scorer.calculate_risk(
            extension_id, action_id, window_days=30
        )

        # 2. Map Risk Score to Tier
        tier = self._map_tier(risk.score)

        # 3. Check for previous tier
        previous_tier = self.tier_history.get_current_tier(extension_id, action_id)
        tier_changed = previous_tier is not None and previous_tier != tier

        # 4. Record tier change if detected
        if tier_changed:
            reason = f"Risk score changed from {risk.score:.2f}"
            self.tier_history.record_change(
                extension_id=extension_id,
                action_id=action_id,
                old_tier=previous_tier,
                new_tier=tier,
                risk_score=risk.score,
                reason=reason
            )
        elif previous_tier is None:
            # First time calculation - record initial tier
            reason = f"Initial tier determination: {risk.score:.2f}"
            self.tier_history.record_change(
                extension_id=extension_id,
                action_id=action_id,
                old_tier=None,
                new_tier=tier,
                risk_score=risk.score,
                reason=reason
            )

        # 5. Generate explanation
        explanation = self._generate_explanation(
            tier=tier,
            risk=risk,
            previous_tier=previous_tier,
            tier_changed=tier_changed
        )

        # 6. Create TierInfo
        tier_info = TierInfo(
            tier=tier,
            risk_score=risk.score,
            explanation=explanation,
            previous_tier=previous_tier,
            changed=tier_changed,
            calculated_at=utc_now()
        )

        return tier_info

    def _map_tier(self, risk_score: float) -> TrustTier:
        """
        Map Risk Score to Trust Tier.

        Mapping rules (v0):
        - 0-30: LOW
        - 30-70: MEDIUM
        - 70-100: HIGH

        Args:
            risk_score: Risk score value (0-100)

        Returns:
            TrustTier enum value
        """
        return TrustTier.from_risk_score(risk_score)

    def _generate_explanation(
        self,
        tier: TrustTier,
        risk: RiskScore,
        previous_tier: Optional[TrustTier],
        tier_changed: bool
    ) -> str:
        """
        Generate human-readable tier determination explanation.

        Args:
            tier: Current tier
            risk: Risk score object
            previous_tier: Previous tier (if any)
            tier_changed: Whether tier changed

        Returns:
            Multi-line explanation string
        """
        lines = [
            f"Trust Tier: {tier.value}",
            f"Risk Score: {risk.score:.2f}/100",
            "",
            "Tier Determination:",
            f"- Score range for {tier.value}: {tier.get_score_range()}",
            f"- Characteristics: {tier.get_description()}",
            f"- Sandbox requirement: {TierInfo(tier, risk.score, '', None, False, utc_now()).get_sandbox_recommendation()}",
            "",
            "Risk Breakdown:",
        ]

        # Add risk dimensions
        for dim_name, dim_value in risk.dimensions.items():
            lines.append(f"  - {dim_name}: {dim_value:.4f}")

        lines.append("")
        lines.append(f"Analysis window: {risk.window_days} days")
        lines.append(f"Sample size: {risk.sample_size} executions")

        # Add tier change warning if applicable
        if tier_changed and previous_tier:
            lines.append("")
            lines.append(f"⚠️  Tier Changed: {previous_tier.value} → {tier.value}")
            lines.append(f"   This indicates a significant change in risk profile.")

        return "\n".join(lines)

    def get_tier_value_only(
        self,
        extension_id: str,
        action_id: str = "*"
    ) -> TrustTier:
        """
        Get only the tier value (convenience method for Policy Engine).

        This is a lightweight method for quick tier lookups.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier

        Returns:
            TrustTier enum value
        """
        tier_info = self.get_tier(extension_id, action_id)
        return tier_info.tier

    def requires_sandbox(
        self,
        extension_id: str,
        action_id: str = "*"
    ) -> bool:
        """
        Check if extension requires mandatory sandboxing.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier

        Returns:
            True if HIGH tier (mandatory sandbox)
        """
        tier = self.get_tier_value_only(extension_id, action_id)
        return tier == TrustTier.HIGH

    def allows_auto_execution(
        self,
        extension_id: str,
        action_id: str = "*"
    ) -> bool:
        """
        Check if extension allows automatic execution.

        Args:
            extension_id: Extension identifier
            action_id: Action identifier

        Returns:
            True if LOW or MEDIUM tier
        """
        tier = self.get_tier_value_only(extension_id, action_id)
        return tier in [TrustTier.LOW, TrustTier.MEDIUM]
