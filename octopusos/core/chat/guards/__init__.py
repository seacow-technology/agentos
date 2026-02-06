"""Chat Guards - Security boundary for Chat ↔ CommunicationOS integration.

This module provides three essential guards:
1. PhaseGate - Prevents external operations during planning phase
2. AttributionGuard - Enforces proper attribution of external knowledge
3. ContentFence - Marks and isolates untrusted external content
"""

from .phase_gate import PhaseGate, PhaseGateError
from .attribution import AttributionGuard, AttributionViolation
from .content_fence import ContentFence

__all__ = [
    "PhaseGate",
    "PhaseGateError",
    "AttributionGuard",
    "AttributionViolation",
    "ContentFence",
]
