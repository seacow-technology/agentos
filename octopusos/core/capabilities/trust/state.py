"""
Trust State Models

Defines trust states for the Trust Trajectory system.
Trust states track the evolution of trust over time, not risk levels.

Trust states are different from Trust Tiers (LOW/MEDIUM/HIGH):
- Trust Tiers = Risk-based classification
- Trust States = Trust evolution status over time
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class TrustState(Enum):
    """
    Trust state enumeration for trajectory tracking.

    States represent the evolution of trust over time:
    - EARNING: Building trust through consistent good behavior
    - STABLE: Trust has been established and maintained
    - DEGRADING: Trust is being lost due to failures or policy violations

    Red Line: States must transition sequentially (no jumping)
    """
    EARNING = "EARNING"
    STABLE = "STABLE"
    DEGRADING = "DEGRADING"

    def can_transition_to(self, new_state: "TrustState") -> bool:
        """
        Check if transition to new state is allowed.

        Allowed transitions:
        - EARNING → STABLE (after consistent success)
        - STABLE → DEGRADING (after failures)
        - DEGRADING → EARNING (recovery path)

        Forbidden transitions:
        - DEGRADING → STABLE (must go through EARNING)
        - Any state → itself (no-op, not a real transition)

        Args:
            new_state: Target state

        Returns:
            True if transition is allowed
        """
        # No jumping allowed
        if self == TrustState.EARNING:
            return new_state == TrustState.STABLE
        elif self == TrustState.STABLE:
            return new_state == TrustState.DEGRADING
        elif self == TrustState.DEGRADING:
            return new_state == TrustState.EARNING

        return False

    def get_description(self) -> str:
        """
        Get human-readable description of state.

        Returns:
            State description
        """
        descriptions = {
            TrustState.EARNING: "Accumulating trust through consistent behavior",
            TrustState.STABLE: "Trust established and maintained",
            TrustState.DEGRADING: "Trust is being lost, recovery needed"
        }
        return descriptions[self]


@dataclass
class TrustTransition:
    """
    Record of a trust state transition.

    Attributes:
        transition_id: Unique transition identifier
        extension_id: Extension identifier
        action_id: Action identifier (or "*" for all)
        old_state: Previous trust state
        new_state: New trust state
        trigger_event: Event that triggered the transition
        explain: Human-readable explanation
        risk_context: Risk metrics at time of transition
        policy_context: Policy decisions influencing transition
        created_at: Timestamp of transition
    """
    transition_id: str
    extension_id: str
    action_id: str
    old_state: TrustState
    new_state: TrustState
    trigger_event: str
    explain: str
    risk_context: Dict
    policy_context: Dict
    created_at: datetime

    def to_dict(self) -> Dict:
        """
        Convert transition to API-friendly dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "transition_id": self.transition_id,
            "extension_id": self.extension_id,
            "action_id": self.action_id,
            "old_state": self.old_state.value,
            "new_state": self.new_state.value,
            "trigger_event": self.trigger_event,
            "explain": self.explain,
            "risk_context": self.risk_context,
            "policy_context": self.policy_context,
            "created_at": int(self.created_at.timestamp() * 1000)
        }


@dataclass
class TrustTrajectoryInfo:
    """
    Current trust trajectory state with context.

    Attributes:
        state: Current trust state
        extension_id: Extension identifier
        action_id: Action identifier
        consecutive_successes: Number of consecutive successful executions
        consecutive_failures: Number of consecutive failures
        policy_rejections: Number of recent policy rejections
        high_risk_events: Number of recent high-risk events
        time_in_state: Duration in current state (seconds)
        inertia_score: Time inertia score (0-1, higher = more stable)
        last_transition: Last transition record
        calculated_at: Timestamp of calculation
    """
    state: TrustState
    extension_id: str
    action_id: str
    consecutive_successes: int
    consecutive_failures: int
    policy_rejections: int
    high_risk_events: int
    time_in_state: float
    inertia_score: float
    last_transition: Optional[TrustTransition]
    calculated_at: datetime

    def to_dict(self) -> Dict:
        """
        Convert trajectory info to API-friendly dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "state": self.state.value,
            "state_description": self.state.get_description(),
            "extension_id": self.extension_id,
            "action_id": self.action_id,
            "metrics": {
                "consecutive_successes": self.consecutive_successes,
                "consecutive_failures": self.consecutive_failures,
                "policy_rejections": self.policy_rejections,
                "high_risk_events": self.high_risk_events,
                "time_in_state_hours": round(self.time_in_state / 3600, 2),
                "inertia_score": round(self.inertia_score, 3)
            },
            "last_transition": self.last_transition.to_dict() if self.last_transition else None,
            "calculated_at": int(self.calculated_at.timestamp() * 1000)
        }

    def requires_action(self) -> Optional[str]:
        """
        Determine if trajectory requires governance action.

        Returns:
            Action recommendation or None
        """
        if self.state == TrustState.DEGRADING:
            if self.consecutive_failures > 5:
                return "REVOKE"
            elif self.high_risk_events > 3:
                return "FREEZE"
            else:
                return "MONITOR"

        if self.state == TrustState.EARNING:
            if self.consecutive_successes >= 10 and self.policy_rejections == 0:
                return "PROMOTE"

        return None


@dataclass
class TrajectoryRule:
    """
    Rule for trust state transitions.

    Attributes:
        rule_id: Unique rule identifier
        from_state: Source state
        to_state: Target state
        condition: Condition description
        threshold_config: Threshold configuration
        priority: Rule priority (lower = higher priority)
    """
    rule_id: str
    from_state: TrustState
    to_state: TrustState
    condition: str
    threshold_config: Dict
    priority: int

    def evaluate(self, context: Dict) -> bool:
        """
        Evaluate if rule conditions are met.

        Args:
            context: Evaluation context with metrics

        Returns:
            True if rule conditions are satisfied
        """
        # Extract thresholds
        min_successes = self.threshold_config.get("min_consecutive_successes", 0)
        max_failures = self.threshold_config.get("max_consecutive_failures", float('inf'))
        max_policy_rejections = self.threshold_config.get("max_policy_rejections", float('inf'))
        max_high_risk = self.threshold_config.get("max_high_risk_events", float('inf'))
        min_time_in_state = self.threshold_config.get("min_time_in_state_hours", 0)

        # Check conditions
        successes = context.get("consecutive_successes", 0)
        failures = context.get("consecutive_failures", 0)
        policy_rejections = context.get("policy_rejections", 0)
        high_risk_events = context.get("high_risk_events", 0)
        time_in_state_hours = context.get("time_in_state_hours", 0)

        # For degradation rules (STABLE → DEGRADING), use OR logic
        # Any violation should trigger
        if self.from_state == TrustState.STABLE and self.to_state == TrustState.DEGRADING:
            return (
                failures > max_failures or
                policy_rejections > max_policy_rejections or
                high_risk_events > max_high_risk
            )

        # For other rules, use AND logic
        return (
            successes >= min_successes and
            failures <= max_failures and
            policy_rejections <= max_policy_rejections and
            time_in_state_hours >= min_time_in_state
        )
