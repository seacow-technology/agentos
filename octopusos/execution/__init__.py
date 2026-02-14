"""Execution governance primitives (gates, risk tiers, capability metadata).

This package is intentionally small and UI/API-friendly:
- API layer uses it to enforce gates and attach risk metadata.
- UI layer relies on the stable gate protocol over HTTP (409 + detail).
"""

from .risk import RiskTier
from .capability import Capability, get_capability
from .gate import trust_gate, confirm_gate, policy_gate

__all__ = [
    "RiskTier",
    "Capability",
    "get_capability",
    "trust_gate",
    "confirm_gate",
    "policy_gate",
]

