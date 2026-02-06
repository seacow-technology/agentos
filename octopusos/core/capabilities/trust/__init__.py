"""
Trust Module v0

Provides Trust Tier determination and Trust Trajectory tracking.
Trust Tiers are calculated results, not manual configurations.

Core components:
- TrustTierEngine: Main tier determination engine
- TrustTier: Enum for tier levels (LOW, MEDIUM, HIGH)
- TierInfo: Data model for tier information
- TierHistory: Historical tier change tracking
- TrustTrajectoryEngine: Trust state evolution over time
- TrustState: Trust state enumeration (EARNING, STABLE, DEGRADING)

Trust Tier IS:
- Calculated from Risk Score (not configured)
- Traceable (all changes logged)
- Evolvable (same extension can have different tiers over time)

Trust Tier does NOT:
- Allow manual overrides
- Remain static forever
- Execute decisions (that's Policy Engine's job)

Trust Trajectory IS:
- Time-based trust evolution tracking
- Sequential state transitions only
- Audit trail with explanations
- Time inertia to prevent instant changes

Trust Trajectory does NOT:
- Allow state jumping (EARNING → STABLE → DEGRADING only)
- Allow instant recovery (DEGRADING → STABLE forbidden)
- Allow manual state overrides
"""

from .models import TrustTier, TierInfo
from .tier import TrustTierEngine
from .history import TierHistory
from .state import TrustState, TrustTransition, TrustTrajectoryInfo
from .trajectory import TrustTrajectoryEngine

__all__ = [
    "TrustTier",
    "TierInfo",
    "TrustTierEngine",
    "TierHistory",
    "TrustState",
    "TrustTransition",
    "TrustTrajectoryInfo",
    "TrustTrajectoryEngine",
]
