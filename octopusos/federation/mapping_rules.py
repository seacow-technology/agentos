"""
Trust Mapping Rules (Phase G3)

Defines fixed v0 rules for mapping remote trust to local trust.

Core Principle: Mapping is NOT copying - remote trust must be re-proven locally.

Mapping Rules (v0 Fixed):
    State Mapping:
        Remote STABLE  → Local EARNING (must re-prove)
        Remote EARNING → Local EARNING (maintain caution)
        Remote DEGRADING → Local EARNING (lower initial score)

    Tier Mapping (with ceiling):
        Remote HIGH    → Local MEDIUM max (no direct HIGH inheritance)
        Remote MEDIUM  → Local MEDIUM
        Remote LOW     → Local LOW

    Sandbox Constraint:
        Remote no sandbox → Local force LOW tier (security downgrade)
        Remote has sandbox → Local follow declared tier

Red Lines:
    ❌ No HIGH → HIGH direct mapping
    ❌ No skipping local Phase E evolution
    ❌ Remote cannot decide local Tier without validation
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class TrustState(Enum):
    """Trust states from Phase E"""
    EARNING = "EARNING"
    STABLE = "STABLE"
    DEGRADING = "DEGRADING"


class TrustTier(Enum):
    """Trust tiers from Phase D"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class MappingRule:
    """
    Base mapping rule definition.

    Attributes:
        rule_id: Unique rule identifier
        rule_type: Type of mapping (state/tier/sandbox)
        description: Human-readable rule explanation
        priority: Rule priority (lower = higher priority)
        active: Whether rule is active
    """
    rule_id: str
    rule_type: str
    description: str
    priority: int
    active: bool = True


class StateMapping:
    """
    Trust State Mapping Rules.

    All remote states map to local EARNING (must re-prove).
    Initial trust score varies based on remote state.
    """

    # Fixed v0 state mapping
    MAPPING_RULES = {
        TrustState.STABLE: {
            "local_state": TrustState.EARNING,
            "score_modifier": 1.0,  # No penalty
            "reason": "Remote STABLE requires local proof - starting at EARNING"
        },
        TrustState.EARNING: {
            "local_state": TrustState.EARNING,
            "score_modifier": 0.9,  # Slight penalty for not proven
            "reason": "Remote EARNING mapped to local EARNING with caution"
        },
        TrustState.DEGRADING: {
            "local_state": TrustState.EARNING,
            "score_modifier": 0.7,  # Significant penalty
            "reason": "Remote DEGRADING requires careful re-earning locally"
        }
    }

    @classmethod
    def map_state(
        cls,
        remote_state: TrustState,
        verification_score: float
    ) -> Dict:
        """
        Map remote trust state to local state.

        Args:
            remote_state: Remote trust state
            verification_score: Verification score from G2 (0-100)

        Returns:
            Mapping result with local_state, modified_score, and reason
        """
        if remote_state not in cls.MAPPING_RULES:
            raise ValueError(f"Unknown remote state: {remote_state}")

        rule = cls.MAPPING_RULES[remote_state]

        # Apply score modifier
        modified_score = verification_score * rule["score_modifier"]

        return {
            "local_state": rule["local_state"],  # Keep as enum for internal use
            "local_state_value": rule["local_state"].value,  # Add string value for serialization
            "initial_trust": min(modified_score, 100.0),
            "score_modifier": rule["score_modifier"],
            "reason": rule["reason"]
        }

    @classmethod
    def get_all_rules(cls) -> Dict[TrustState, Dict]:
        """Get all state mapping rules"""
        return cls.MAPPING_RULES.copy()


class TierMapping:
    """
    Trust Tier Mapping Rules.

    Red Line: HIGH tier cannot be directly inherited.
    All remote HIGH must be capped at local MEDIUM.
    """

    # Fixed v0 tier mapping (with ceiling)
    MAPPING_RULES = {
        TrustTier.HIGH: {
            "local_tier": TrustTier.MEDIUM,  # RED LINE: Cap at MEDIUM
            "max_trust": 70.0,  # Max 70% trust
            "reason": "HIGH tier cannot be directly inherited - capped at MEDIUM"
        },
        TrustTier.MEDIUM: {
            "local_tier": TrustTier.MEDIUM,
            "max_trust": 60.0,  # Conservative cap
            "reason": "MEDIUM tier mapped to local MEDIUM"
        },
        TrustTier.LOW: {
            "local_tier": TrustTier.LOW,
            "max_trust": 40.0,
            "reason": "LOW tier mapped to local LOW"
        }
    }

    @classmethod
    def map_tier(
        cls,
        remote_tier: TrustTier,
        initial_trust: float
    ) -> Dict:
        """
        Map remote trust tier to local tier with ceiling.

        Args:
            remote_tier: Remote trust tier
            initial_trust: Initial trust score

        Returns:
            Mapping result with local_tier, capped_trust, and reason
        """
        if remote_tier not in cls.MAPPING_RULES:
            raise ValueError(f"Unknown remote tier: {remote_tier}")

        rule = cls.MAPPING_RULES[remote_tier]

        # Apply trust cap
        capped_trust = min(initial_trust, rule["max_trust"])

        return {
            "local_tier": rule["local_tier"],  # Keep as enum for internal use
            "local_tier_value": rule["local_tier"].value,  # Add string value for serialization
            "capped_trust": capped_trust,
            "max_trust": rule["max_trust"],
            "reason": rule["reason"]
        }

    @classmethod
    def get_all_rules(cls) -> Dict[TrustTier, Dict]:
        """Get all tier mapping rules"""
        return cls.MAPPING_RULES.copy()


class SandboxConstraint:
    """
    Sandbox Constraint Rules.

    Red Line: No sandbox = forced downgrade to LOW tier.
    Local systems must enforce sandbox requirements.
    """

    # Sandbox requirement levels
    SANDBOX_LEVELS = ["none", "low", "medium", "high"]

    @classmethod
    def apply_constraint(
        cls,
        remote_has_sandbox: bool,
        remote_sandbox_level: str,
        proposed_tier: TrustTier,
        proposed_trust: float
    ) -> Dict:
        """
        Apply sandbox constraints to proposed mapping.

        Red Line: If remote has no sandbox, force downgrade to LOW tier.

        Args:
            remote_has_sandbox: Whether remote system has sandbox
            remote_sandbox_level: Remote sandbox level
            proposed_tier: Proposed local tier
            proposed_trust: Proposed trust score

        Returns:
            Constraint result with enforced_tier, adjusted_trust, reason
        """
        # Red Line: No sandbox = force LOW
        if not remote_has_sandbox:
            return {
                "enforced_tier": TrustTier.LOW,
                "enforced_tier_value": TrustTier.LOW.value,
                "adjusted_trust": min(proposed_trust * 0.6, 25.0),  # Heavy penalty
                "requires_local_sandbox": True,
                "sandbox_downgrade": True,
                "reason": (
                    "Remote system has no sandbox isolation - "
                    "downgraded to LOW tier and local sandbox required"
                )
            }

        # Validate sandbox level
        if remote_sandbox_level not in cls.SANDBOX_LEVELS:
            # Unknown sandbox level = treat as low
            return {
                "enforced_tier": TrustTier.LOW,
                "enforced_tier_value": TrustTier.LOW.value,
                "adjusted_trust": min(proposed_trust * 0.7, 30.0),
                "requires_local_sandbox": True,
                "sandbox_downgrade": True,
                "reason": (
                    f"Unknown sandbox level '{remote_sandbox_level}' - "
                    "downgraded to LOW tier as precaution"
                )
            }

        # Validate sandbox appropriateness
        if remote_sandbox_level == "none" or remote_sandbox_level == "low":
            if proposed_tier == TrustTier.HIGH or proposed_tier == TrustTier.MEDIUM:
                # Insufficient sandbox for proposed tier
                return {
                    "enforced_tier": TrustTier.LOW,
                    "enforced_tier_value": TrustTier.LOW.value,
                    "adjusted_trust": min(proposed_trust * 0.7, 35.0),
                    "requires_local_sandbox": True,
                    "sandbox_downgrade": True,
                    "reason": (
                        f"Insufficient sandbox '{remote_sandbox_level}' "
                        f"for {proposed_tier.value} tier - downgraded to LOW"
                    )
                }

        # Sandbox is adequate
        return {
            "enforced_tier": proposed_tier,
            "enforced_tier_value": proposed_tier.value,
            "adjusted_trust": proposed_trust,
            "requires_local_sandbox": proposed_tier == TrustTier.HIGH,
            "sandbox_downgrade": False,
            "reason": f"Sandbox level '{remote_sandbox_level}' is adequate"
        }

    @classmethod
    def validate_sandbox_level(cls, sandbox_level: str) -> bool:
        """
        Validate sandbox level string.

        Args:
            sandbox_level: Sandbox level to validate

        Returns:
            True if valid
        """
        return sandbox_level in cls.SANDBOX_LEVELS


# Mapping Rule Definitions (for documentation)
RULE_DEFINITIONS = {
    "state_mapping": {
        "rule_id": "G3-STATE-001",
        "description": "All remote states map to local EARNING",
        "rationale": "Remote trust must be re-proven locally",
        "red_lines": [
            "No direct STABLE inheritance",
            "Must enter Phase E evolution"
        ]
    },
    "tier_mapping": {
        "rule_id": "G3-TIER-001",
        "description": "HIGH tier capped at local MEDIUM",
        "rationale": "HIGH trust cannot be directly inherited",
        "red_lines": [
            "No HIGH → HIGH mapping",
            "Max local tier is MEDIUM for remote imports"
        ]
    },
    "sandbox_constraint": {
        "rule_id": "G3-SANDBOX-001",
        "description": "No sandbox = forced LOW tier",
        "rationale": "Security downgrade for unsandboxed systems",
        "red_lines": [
            "No execution without sandbox for HIGH tier",
            "Local sandbox enforcement is mandatory"
        ]
    }
}
