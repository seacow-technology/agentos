"""Mode Gateway Protocol - Validates task transitions based on mode constraints.

This module defines the protocol for mode-based task transition validation.
Mode gateways can approve, reject, block, or defer transitions based on the
task's mode and current state.

Design Principles:
1. Protocol-based: Uses Python Protocol for type-safe duck typing
2. Verdict-based: Clear decision structure (APPROVED/REJECTED/BLOCKED/DEFERRED)
3. Fail-safe: System continues if mode gateway is unavailable
4. Auditable: All decisions include reasoning and metadata

Usage:
    from agentos.core.mode.gateway import ModeGatewayProtocol, ModeDecision
from agentos.core.time import utc_now_iso


    # Implement a custom gateway
    class CustomGateway(ModeGatewayProtocol):
        def validate_transition(
            self,
            task_id: str,
            mode_id: str,
            from_state: str,
            to_state: str,
            metadata: dict
        ) -> ModeDecision:
            # Custom validation logic
            return ModeDecision(
                verdict=ModeDecisionVerdict.APPROVED,
                reason="Custom validation passed"
            )
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, Dict, Any, Optional


class ModeDecisionVerdict(str, Enum):
    """Verdict for mode gateway transition validation.

    Attributes:
        APPROVED: Transition is approved, proceed
        REJECTED: Transition is rejected, raise error
        BLOCKED: Transition is blocked pending external approval
        DEFERRED: Transition is deferred, will be retried later
    """
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    DEFERRED = "deferred"


@dataclass
class ModeDecision:
    """Decision result from mode gateway validation.

    Represents the decision made by a mode gateway regarding a task
    transition. Includes the verdict, reasoning, and optional metadata.

    Attributes:
        verdict: The decision verdict (APPROVED/REJECTED/BLOCKED/DEFERRED)
        reason: Human-readable explanation for the decision
        metadata: Optional metadata about the decision
        timestamp: When the decision was made (ISO 8601 format)
        gateway_id: ID of the gateway that made the decision
    """
    verdict: ModeDecisionVerdict
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: utc_now_iso())
    gateway_id: str = "default"

    def is_approved(self) -> bool:
        """Check if the transition is approved."""
        return self.verdict == ModeDecisionVerdict.APPROVED

    def is_rejected(self) -> bool:
        """Check if the transition is rejected."""
        return self.verdict == ModeDecisionVerdict.REJECTED

    def is_blocked(self) -> bool:
        """Check if the transition is blocked."""
        return self.verdict == ModeDecisionVerdict.BLOCKED

    def is_deferred(self) -> bool:
        """Check if the transition is deferred."""
        return self.verdict == ModeDecisionVerdict.DEFERRED

    def to_dict(self) -> dict:
        """Convert decision to dictionary for serialization."""
        return {
            "verdict": self.verdict.value,
            "reason": self.reason,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "gateway_id": self.gateway_id,
        }


class ModeGatewayProtocol(Protocol):
    """Protocol for mode gateway implementations.

    Mode gateways validate task transitions based on mode constraints.
    Implementations can enforce mode-specific rules, perform external
    checks, or integrate with approval systems.

    Example:
        class ApprovalGateway(ModeGatewayProtocol):
            def validate_transition(
                self,
                task_id: str,
                mode_id: str,
                from_state: str,
                to_state: str,
                metadata: dict
            ) -> ModeDecision:
                # Check if transition requires approval
                if self._requires_approval(mode_id, to_state):
                    return ModeDecision(
                        verdict=ModeDecisionVerdict.BLOCKED,
                        reason="Awaiting human approval",
                        gateway_id="approval_gateway"
                    )
                return ModeDecision(
                    verdict=ModeDecisionVerdict.APPROVED,
                    reason="No approval required",
                    gateway_id="approval_gateway"
                )
    """

    def validate_transition(
        self,
        task_id: str,
        mode_id: str,
        from_state: str,
        to_state: str,
        metadata: dict
    ) -> ModeDecision:
        """Validate a task state transition based on mode constraints.

        Args:
            task_id: ID of the task attempting transition
            mode_id: Mode the task is operating in
            from_state: Current state of the task
            to_state: Target state of the transition
            metadata: Task metadata for context

        Returns:
            ModeDecision: Decision about the transition

        Note:
            Implementations should be fast (<10ms) and not block.
            For async operations, return DEFERRED and handle separately.
        """
        ...


# Convenience type alias for gateway instances
ModeGateway = ModeGatewayProtocol


__all__ = [
    "ModeDecisionVerdict",
    "ModeDecision",
    "ModeGatewayProtocol",
    "ModeGateway",
]
