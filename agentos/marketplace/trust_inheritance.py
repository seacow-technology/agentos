"""
Trust Inheritance Engine (Phase F3)

This module implements the Trust Inheritance Engine, which calculates initial
trust levels for new capabilities entering the system from the marketplace.

Core Principle:
    Inheritance provides a STARTING POINT, not a CONCLUSION.
    All capabilities must still go through Phase E trust evolution.

Trust Inheritance Rules (v0 Fixed):
    1. Publisher Trust: Max 30% contribution from publisher history
    2. Category Similarity: Max 20% contribution from similar capabilities
    3. Sandbox Safety: Max 50% contribution from sandbox configuration
    4. Local History: 0% (cannot inherit local trust)

Red Lines (Absolute Prohibitions):
    ❌ Cannot inherit HIGH risk trust
    ❌ Cannot inherit across publishers
    ❌ Cannot skip Phase E (EARNING state)
    ❌ Initial state MUST be EARNING (never STABLE/DEGRADING)

Architecture:
    TrustInheritanceEngine
      ├─ calculate_initial_trust() - Main entry point
      ├─ get_publisher_trust() - Publisher reputation (30%)
      ├─ calculate_category_similarity() - Category match (20%)
      ├─ calculate_sandbox_safety() - Sandbox security (50%)
      └─ apply_inheritance() - Apply rules and return initial state

Example Flow:
    1. New capability arrives from marketplace
    2. Engine calculates inherited trust (0-100)
    3. Maps to initial tier (LOW/MEDIUM, never HIGH)
    4. Sets state to EARNING
    5. Capability enters Phase E for local evolution

Created: 2026-02-02
Author: Phase F3 Agent
Reference: Phase F Task Cards (plan1.md)
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class InitialTrustTier(Enum):
    """
    Initial trust tiers for marketplace capabilities.

    Note: HIGH is intentionally excluded - new capabilities
    cannot start with HIGH trust, regardless of inheritance.
    """
    LOW = "LOW"      # < 30% initial trust
    MEDIUM = "MEDIUM"  # 30-70% initial trust
    # HIGH is prohibited for initial trust


class TrustState(Enum):
    """Trust evolution states (from Phase E)"""
    EARNING = "EARNING"      # Building trust
    STABLE = "STABLE"        # Trust established
    DEGRADING = "DEGRADING"  # Trust declining


@dataclass
class InheritanceSource:
    """
    Breakdown of trust inheritance sources.

    Attributes:
        publisher_contribution: Trust from publisher (0-30)
        category_contribution: Trust from category similarity (0-20)
        sandbox_contribution: Trust from sandbox safety (0-50)
        total: Sum of all contributions (0-100)
    """
    publisher_contribution: float
    category_contribution: float
    sandbox_contribution: float

    @property
    def total(self) -> float:
        """Calculate total inherited trust"""
        return (
            self.publisher_contribution +
            self.category_contribution +
            self.sandbox_contribution
        )


@dataclass
class InitialTrustResult:
    """
    Result of initial trust calculation.

    Attributes:
        capability_id: Capability identifier
        initial_trust_score: Calculated initial trust (0-100)
        initial_tier: Mapped trust tier (LOW/MEDIUM)
        initial_state: Always EARNING for new capabilities
        inheritance_sources: Breakdown of trust sources
        explanation: Human-readable explanation
        calculated_at: Calculation timestamp
    """
    capability_id: str
    initial_trust_score: float
    initial_tier: InitialTrustTier
    initial_state: TrustState
    inheritance_sources: InheritanceSource
    explanation: str
    calculated_at: datetime

    def to_dict(self) -> Dict:
        """Convert result to dictionary"""
        return {
            "capability_id": self.capability_id,
            "initial_trust_score": round(self.initial_trust_score, 2),
            "initial_tier": self.initial_tier.value,
            "initial_state": self.initial_state.value,
            "inheritance_sources": {
                "publisher_contribution": round(
                    self.inheritance_sources.publisher_contribution, 2
                ),
                "category_contribution": round(
                    self.inheritance_sources.category_contribution, 2
                ),
                "sandbox_contribution": round(
                    self.inheritance_sources.sandbox_contribution, 2
                ),
                "total": round(self.inheritance_sources.total, 2)
            },
            "explanation": self.explanation,
            "calculated_at": int(self.calculated_at.timestamp() * 1000)
        }


class TrustInheritanceEngine:
    """
    Trust Inheritance Engine (Phase F3).

    Calculates initial trust levels for new marketplace capabilities
    based on publisher reputation, category similarity, and sandbox safety.

    Usage:
        engine = TrustInheritanceEngine()
        result = engine.calculate_initial_trust(
            capability_id="new_org.my_extension.v1.0.0",
            publisher_id="new_org",
            category="data_processing",
            sandbox_level="medium"
        )

        print(f"Initial Trust: {result.initial_trust_score}%")
        print(f"Initial Tier: {result.initial_tier.value}")
        print(f"Initial State: {result.initial_state.value}")
    """

    # Trust inheritance weight constants (v0 fixed)
    PUBLISHER_MAX_WEIGHT = 0.3   # Publisher trust: max 30%
    CATEGORY_MAX_WEIGHT = 0.2    # Category similarity: max 20%
    SANDBOX_MAX_WEIGHT = 0.5     # Sandbox safety: max 50%

    # Red line thresholds
    HIGH_RISK_THRESHOLD = 70.0   # Cannot inherit above this
    MEDIUM_TIER_THRESHOLD = 30.0 # Below this = LOW tier

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize Trust Inheritance Engine.

        Args:
            db_path: Optional database path for publisher trust lookup
        """
        self.db_path = db_path
        logger.info("Trust Inheritance Engine initialized")

    def calculate_initial_trust(
        self,
        capability_id: str,
        publisher_id: str,
        category: str,
        sandbox_level: str,
        capability_metadata: Optional[Dict] = None
    ) -> InitialTrustResult:
        """
        Calculate initial trust for a new marketplace capability.

        This is the main entry point for trust inheritance calculation.

        Args:
            capability_id: Full capability identifier
            publisher_id: Publisher/organization identifier
            category: Capability category (e.g., "data_processing", "web")
            sandbox_level: Declared sandbox level ("none", "low", "medium", "high")
            capability_metadata: Optional additional metadata

        Returns:
            InitialTrustResult with calculated trust and tier

        Raises:
            ValueError: If parameters are invalid
        """
        # Validate inputs
        if not capability_id or not publisher_id:
            raise ValueError("capability_id and publisher_id are required")

        if not category:
            raise ValueError("category is required")

        if sandbox_level not in ["none", "low", "medium", "high"]:
            raise ValueError(
                f"Invalid sandbox_level: {sandbox_level}. "
                "Must be one of: none, low, medium, high"
            )

        logger.info(
            f"Calculating initial trust for capability: {capability_id}, "
            f"publisher: {publisher_id}, category: {category}, "
            f"sandbox: {sandbox_level}"
        )

        # Calculate three inheritance sources
        publisher_trust = self.get_publisher_trust(publisher_id)
        category_similarity = self.calculate_category_similarity(
            category, capability_metadata
        )
        sandbox_safety = self.calculate_sandbox_safety(sandbox_level, category)

        # Create inheritance sources
        sources = InheritanceSource(
            publisher_contribution=publisher_trust,
            category_contribution=category_similarity,
            sandbox_contribution=sandbox_safety
        )

        # Apply inheritance rules
        result = self.apply_inheritance(
            capability_id=capability_id,
            sources=sources,
            category=category,
            sandbox_level=sandbox_level
        )

        logger.info(
            f"Initial trust calculated for {capability_id}: "
            f"{result.initial_trust_score:.2f}% ({result.initial_tier.value})"
        )

        return result

    def get_publisher_trust(self, publisher_id: str) -> float:
        """
        Get publisher trust contribution (max 30%).

        Calculates trust based on publisher's historical capability performance.
        New publishers with no history get 0% contribution.

        Args:
            publisher_id: Publisher identifier

        Returns:
            Publisher trust contribution (0-30)
        """
        # TODO: Query database for publisher trust
        # For now, return mock values based on publisher name

        # Known publishers (demo data)
        publisher_trust_map = {
            "official": 0.80,  # 80% publisher trust
            "smithery.ai": 0.75,
            "anthropic": 0.85,
            "community": 0.40,
        }

        # Get base trust (0-1)
        base_trust = publisher_trust_map.get(publisher_id.lower(), 0.0)

        # Apply 30% weight
        contribution = base_trust * self.PUBLISHER_MAX_WEIGHT * 100

        logger.debug(
            f"Publisher trust for '{publisher_id}': "
            f"{base_trust*100:.1f}% -> {contribution:.2f}% contribution"
        )

        return contribution

    def calculate_category_similarity(
        self,
        category: str,
        metadata: Optional[Dict] = None
    ) -> float:
        """
        Calculate category similarity contribution (max 20%).

        Measures how similar this capability is to existing capabilities
        in the same category. Higher similarity = more inherited trust.

        Args:
            category: Capability category
            metadata: Optional metadata for similarity calculation

        Returns:
            Category similarity contribution (0-20)
        """
        # TODO: Calculate actual similarity from database
        # For now, return mock values based on category

        # Category similarity scores (mock data)
        category_similarity_map = {
            "data_processing": 0.40,  # 40% similarity
            "web": 0.70,              # 70% similarity
            "filesystem": 0.60,
            "system": 0.0,            # System-level gets no similarity trust
            "network": 0.50,
        }

        # Get base similarity (0-1)
        base_similarity = category_similarity_map.get(category.lower(), 0.30)

        # Apply 20% weight
        contribution = base_similarity * self.CATEGORY_MAX_WEIGHT * 100

        logger.debug(
            f"Category similarity for '{category}': "
            f"{base_similarity*100:.1f}% -> {contribution:.2f}% contribution"
        )

        return contribution

    def calculate_sandbox_safety(
        self,
        sandbox_level: str,
        category: str
    ) -> float:
        """
        Calculate sandbox safety contribution (max 50%).

        Evaluates sandbox configuration and its appropriateness for the
        capability category. Strong sandboxing = more inherited trust.

        Red Line: HIGH risk categories require HIGH sandbox, otherwise
        contribution is reduced significantly.

        Args:
            sandbox_level: Declared sandbox level
            category: Capability category

        Returns:
            Sandbox safety contribution (0-50)
        """
        # Sandbox base scores
        sandbox_scores = {
            "none": 0.20,     # 20% safety (minimal)
            "low": 0.40,      # 40% safety
            "medium": 0.60,   # 60% safety
            "high": 0.80,     # 80% safety
        }

        base_safety = sandbox_scores.get(sandbox_level.lower(), 0.20)

        # High-risk categories require strong sandbox
        high_risk_categories = ["system", "network", "payment", "database_write"]

        if category in high_risk_categories:
            if sandbox_level in ["none", "low"]:
                # Penalty for insufficient sandbox on high-risk category
                base_safety *= 0.25  # Reduce to 25% of base
                logger.warning(
                    f"High-risk category '{category}' with insufficient "
                    f"sandbox '{sandbox_level}': trust reduced"
                )

        # Apply 50% weight
        contribution = base_safety * self.SANDBOX_MAX_WEIGHT * 100

        logger.debug(
            f"Sandbox safety for '{sandbox_level}' + '{category}': "
            f"{base_safety*100:.1f}% -> {contribution:.2f}% contribution"
        )

        return contribution

    def apply_inheritance(
        self,
        capability_id: str,
        sources: InheritanceSource,
        category: str,
        sandbox_level: str
    ) -> InitialTrustResult:
        """
        Apply inheritance rules and create final result.

        Enforces red lines:
        - Cannot exceed HIGH_RISK_THRESHOLD (70%)
        - Initial state must be EARNING
        - Initial tier cannot be HIGH

        Args:
            capability_id: Capability identifier
            sources: Calculated inheritance sources
            category: Capability category
            sandbox_level: Sandbox level

        Returns:
            InitialTrustResult with all fields populated
        """
        # Calculate total trust
        initial_trust = sources.total

        # Red Line 1: Cap at HIGH_RISK_THRESHOLD
        if initial_trust > self.HIGH_RISK_THRESHOLD:
            logger.warning(
                f"Initial trust {initial_trust:.2f}% exceeds threshold "
                f"{self.HIGH_RISK_THRESHOLD}%. Capping at threshold."
            )
            initial_trust = self.HIGH_RISK_THRESHOLD

        # Map to initial tier (LOW or MEDIUM only)
        if initial_trust < self.MEDIUM_TIER_THRESHOLD:
            initial_tier = InitialTrustTier.LOW
        else:
            initial_tier = InitialTrustTier.MEDIUM

        # Red Line 2: Initial state MUST be EARNING
        initial_state = TrustState.EARNING

        # Generate explanation
        explanation = self._generate_explanation(
            sources=sources,
            initial_trust=initial_trust,
            initial_tier=initial_tier,
            category=category,
            sandbox_level=sandbox_level
        )

        return InitialTrustResult(
            capability_id=capability_id,
            initial_trust_score=initial_trust,
            initial_tier=initial_tier,
            initial_state=initial_state,
            inheritance_sources=sources,
            explanation=explanation,
            calculated_at=datetime.now()
        )

    def _generate_explanation(
        self,
        sources: InheritanceSource,
        initial_trust: float,
        initial_tier: InitialTrustTier,
        category: str,
        sandbox_level: str
    ) -> str:
        """
        Generate human-readable explanation of trust calculation.

        Args:
            sources: Inheritance sources
            initial_trust: Calculated initial trust
            initial_tier: Mapped tier
            category: Capability category
            sandbox_level: Sandbox level

        Returns:
            Explanation string
        """
        parts = [
            f"Initial trust: {initial_trust:.1f}% ({initial_tier.value})",
            f"Sources: Publisher {sources.publisher_contribution:.1f}% + "
            f"Category {sources.category_contribution:.1f}% + "
            f"Sandbox {sources.sandbox_contribution:.1f}%",
            f"Category: {category}, Sandbox: {sandbox_level}",
            "State: EARNING (must prove trust locally)"
        ]

        return " | ".join(parts)
