"""
Trust Tier Data Models

Defines the data structures for trust tiers and their metadata.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Optional


class TrustTier(Enum):
    """
    Trust Tier enumeration.

    Tiers are determined by Risk Score:
    - LOW: 0-30 (read-only, idempotent, no external calls)
    - MEDIUM: 30-70 (writable but reversible)
    - HIGH: 70-100 (external calls, system-level, irreversible)
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @classmethod
    def from_risk_score(cls, risk_score: float) -> "TrustTier":
        """
        Map risk score to trust tier.

        Args:
            risk_score: Risk score value (0-100)

        Returns:
            TrustTier enum value
        """
        if risk_score < 30:
            return cls.LOW
        elif risk_score < 70:
            return cls.MEDIUM
        else:
            return cls.HIGH

    def get_score_range(self) -> str:
        """
        Get the score range for this tier.

        Returns:
            String representation of score range
        """
        if self == TrustTier.LOW:
            return "0-30"
        elif self == TrustTier.MEDIUM:
            return "30-70"
        else:
            return "70-100"

    def get_description(self) -> str:
        """
        Get human-readable description of tier characteristics.

        Returns:
            Tier description
        """
        descriptions = {
            TrustTier.LOW: "Read-only, idempotent, no external calls",
            TrustTier.MEDIUM: "Writable but reversible operations",
            TrustTier.HIGH: "External calls, system-level, irreversible"
        }
        return descriptions[self]


@dataclass
class TierInfo:
    """
    Trust Tier information with metadata and explanation.

    Attributes:
        tier: Trust tier level
        risk_score: Underlying risk score
        explanation: Human-readable explanation
        previous_tier: Previous tier (if changed)
        changed: Whether tier changed from previous
        calculated_at: Timestamp of calculation
    """
    tier: TrustTier
    risk_score: float
    explanation: str
    previous_tier: Optional[TrustTier]
    changed: bool
    calculated_at: datetime

    def to_dict(self) -> Dict:
        """
        Convert tier info to API-friendly dictionary.

        Returns:
            Dictionary with tier, risk_score, explanation, and metadata
        """
        return {
            "tier": self.tier.value,
            "risk_score": round(self.risk_score, 2),
            "explanation": self.explanation,
            "meta": {
                "previous_tier": self.previous_tier.value if self.previous_tier else None,
                "changed": self.changed,
                "calculated_at": int(self.calculated_at.timestamp() * 1000),
                "score_range": self.tier.get_score_range(),
                "description": self.tier.get_description()
            }
        }

    def requires_sandbox(self) -> bool:
        """
        Whether this tier requires mandatory sandboxing.

        Returns:
            True if HIGH tier (mandatory sandbox)
        """
        return self.tier == TrustTier.HIGH

    def allows_auto_execution(self) -> bool:
        """
        Whether this tier allows automatic execution.

        Returns:
            True if LOW or MEDIUM tier
        """
        return self.tier in [TrustTier.LOW, TrustTier.MEDIUM]

    def get_sandbox_recommendation(self) -> str:
        """
        Get sandbox recommendation for this tier.

        Returns:
            Sandbox recommendation string
        """
        recommendations = {
            TrustTier.LOW: "Optional",
            TrustTier.MEDIUM: "Recommended",
            TrustTier.HIGH: "Mandatory"
        }
        return recommendations[self.tier]


@dataclass
class TierChangeRecord:
    """
    Record of a tier change event.

    Attributes:
        record_id: Unique record identifier
        extension_id: Extension identifier
        action_id: Action identifier
        old_tier: Previous tier value
        new_tier: New tier value
        risk_score: Risk score that triggered the change
        reason: Human-readable reason
        created_at: Timestamp of change
    """
    record_id: str
    extension_id: str
    action_id: str
    old_tier: Optional[TrustTier]
    new_tier: TrustTier
    risk_score: float
    reason: str
    created_at: datetime

    def to_dict(self) -> Dict:
        """
        Convert change record to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "record_id": self.record_id,
            "extension_id": self.extension_id,
            "action_id": self.action_id,
            "old_tier": self.old_tier.value if self.old_tier else None,
            "new_tier": self.new_tier.value,
            "risk_score": round(self.risk_score, 2),
            "reason": self.reason,
            "created_at": int(self.created_at.timestamp() * 1000)
        }
