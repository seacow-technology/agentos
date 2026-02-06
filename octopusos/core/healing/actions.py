"""Healing actions whitelist."""

from __future__ import annotations
from enum import Enum

class HealingActionType(Enum):
    """Allowed healing actions."""
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    REBUILD_CONTEXT = "rebuild_context"
    REPLAN_STEP = "replan_step"
    ROLLBACK_TO_COMMIT = "rollback_to_commit"
    SPLIT_COMMIT = "split_commit"
    ESCALATE_MODE = "escalate_mode"
    CREATE_BLOCKER = "create_blocker"

class HealingAction:
    """Base class for healing actions."""
    
    def __init__(self, action_type: HealingActionType, parameters: dict):
        self.action_type = action_type
        self.parameters = parameters
        self.risk_level = self._get_risk_level()
    
    def _get_risk_level(self) -> str:
        """Get risk level for this action."""
        risk_map = {
            HealingActionType.RETRY_WITH_BACKOFF: "low",
            HealingActionType.REBUILD_CONTEXT: "low",
            HealingActionType.REPLAN_STEP: "medium",
            HealingActionType.ROLLBACK_TO_COMMIT: "medium",
            HealingActionType.SPLIT_COMMIT: "low",
            HealingActionType.ESCALATE_MODE: "high",
            HealingActionType.CREATE_BLOCKER: "low",
        }
        return risk_map.get(self.action_type, "medium")
    
    def can_execute(self, execution_mode: str) -> bool:
        """Check if action can execute in given mode."""
        if execution_mode == "full_auto":
            return self.risk_level == "low"
        return True

HEALING_ACTIONS_WHITELIST = [action.value for action in HealingActionType]
