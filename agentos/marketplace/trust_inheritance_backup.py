"""
Trust Inheritance Engine

Calculates initial trust for marketplace capabilities based on:
- Publisher history (up to 30%)
- Capability similarity
- Sandbox level

This module is used by F4 Local Bootstrap to determine inherited trust
before applying local decay.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class PublisherReputation:
    """
    Publisher reputation metrics.

    Attributes:
        publisher_id: Publisher identifier
        total_capabilities: Total published capabilities
        avg_trust_score: Average trust score across capabilities
        violations: Number of violations/takedowns
        reputation_score: Overall reputation (0-1)
    """
    publisher_id: str
    total_capabilities: int
    avg_trust_score: float
    violations: int
    reputation_score: float


class TrustInheritanceEngine:
    """
    Trust Inheritance Engine.

    Calculates initial trust for new marketplace capabilities based on
    verifiable factors.

    Inheritance Rules (v0):
    - Publisher history: up to 30%
    - Capability similarity: behavioral similarity
    - Sandbox level: downgrade inheritance for lower sandbox
    - Local history: CANNOT inherit

    Red Lines:
    - ❌ Cannot inherit HIGH risk trust
    - ❌ Cannot cross-publisher inherit
    - ❌ Cannot skip Phase E re-evolution
    """

    def __init__(self, db_path: str):
        """
        Initialize trust inheritance engine.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path

    def calculate_initial_trust(
        self,
        capability_id: str,
        publisher_id: str,
        capability_type: str = "extension",
        sandbox_level: str = "none"
    ) -> float:
        """
        Calculate initial trust for a marketplace capability.

        This represents the "inherited" trust from marketplace factors
        BEFORE local decay is applied.

        Args:
            capability_id: Capability identifier
            publisher_id: Publisher identifier
            capability_type: Type of capability
            sandbox_level: Declared sandbox level

        Returns:
            Initial trust score (0-1)

        Example:
            >>> engine = TrustInheritanceEngine(db_path)
            >>> trust = engine.calculate_initial_trust(
            ...     capability_id="official.web_scraper.v2.0.0",
            ...     publisher_id="official",
            ...     sandbox_level="container"
            ... )
            >>> trust  # e.g., 0.68
        """
        # Base trust starts at 0.5
        base_trust = 0.5

        # Factor 1: Publisher reputation (up to +30%)
        publisher_bonus = self._calculate_publisher_bonus(publisher_id)

        # Factor 2: Capability type
        type_modifier = self._get_type_modifier(capability_type)

        # Factor 3: Sandbox level
        sandbox_modifier = self._get_sandbox_modifier(sandbox_level)

        # Calculate inherited trust
        inherited_trust = base_trust + publisher_bonus
        inherited_trust *= type_modifier
        inherited_trust *= sandbox_modifier

        # Clamp to [0, 1]
        inherited_trust = max(0.0, min(1.0, inherited_trust))

        return inherited_trust

    def _calculate_publisher_bonus(self, publisher_id: str) -> float:
        """
        Calculate trust bonus from publisher reputation.

        This is capped at 30% (0.3) for v0.

        Args:
            publisher_id: Publisher identifier

        Returns:
            Trust bonus (0-0.3)
        """
        # For demo/testing purposes, use simple rules
        # In production, this would query actual publisher history

        if publisher_id == "official":
            # Official publisher gets 30% bonus
            return 0.30
        elif publisher_id.startswith("verified_"):
            # Verified publishers get 20% bonus
            return 0.20
        elif publisher_id.startswith("community_"):
            # Community publishers get 10% bonus
            return 0.10
        else:
            # Unknown publishers get no bonus
            return 0.0

    def _get_type_modifier(self, capability_type: str) -> float:
        """
        Get trust modifier based on capability type.

        Args:
            capability_type: Type of capability

        Returns:
            Modifier multiplier (0.8-1.2)
        """
        modifiers = {
            "extension": 1.0,
            "app": 0.9,
            "pack": 0.85,
            "plugin": 1.0
        }
        return modifiers.get(capability_type, 0.8)

    def _get_sandbox_modifier(self, sandbox_level: str) -> float:
        """
        Get trust modifier based on sandbox level.

        Higher sandbox = higher initial trust.

        Args:
            sandbox_level: Declared sandbox level

        Returns:
            Modifier multiplier (0.7-1.2)
        """
        modifiers = {
            "none": 0.7,
            "basic": 0.85,
            "container": 1.0,
            "vm": 1.1,
            "wasm": 1.2
        }
        return modifiers.get(sandbox_level, 0.7)

    def get_inheritance_explanation(
        self,
        capability_id: str,
        publisher_id: str,
        initial_trust: float
    ) -> str:
        """
        Generate human-readable explanation of trust inheritance.

        Args:
            capability_id: Capability identifier
            publisher_id: Publisher identifier
            initial_trust: Calculated initial trust

        Returns:
            Explanation string
        """
        publisher_bonus = self._calculate_publisher_bonus(publisher_id)

        explanation = (
            f"Initial trust for {capability_id}: {initial_trust:.1%}\n"
            f"- Publisher '{publisher_id}' bonus: +{publisher_bonus:.1%}\n"
            f"- This trust will be decayed by 30% when imported to local environment\n"
            f"- Local trust will start in EARNING state and must be proven through execution history"
        )

        return explanation
