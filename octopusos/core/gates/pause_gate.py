"""Pause Gate: Enforces pause semantics and checkpoints

RED LINE: Pause can ONLY happen at open_plan checkpoint.
No other checkpoint is allowed in v1.

This module provides the central contract for pause/resume behavior.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class PauseState(str, Enum):
    """Pause state: Current pause status of a task"""
    
    NONE = "none"  # Not paused
    AWAITING_APPROVAL = "awaiting_approval"  # Paused, waiting for human approval


class PauseCheckpoint(str, Enum):
    """Pause checkpoint: Where a task can be paused
    
    RED LINE: In v1, ONLY open_plan is allowed.
    Any other checkpoint will cause gate failure.
    """
    
    OPEN_PLAN = "open_plan"  # After open_plan proposal, before any execution
    
    @classmethod
    def is_valid_v1(cls, checkpoint: str) -> bool:
        """Check if checkpoint is valid for v1
        
        RED LINE: Only open_plan is valid in v1.
        """
        return checkpoint == cls.OPEN_PLAN.value


@dataclass
class PauseMetadata:
    """Pause metadata: Stored in task.metadata"""
    
    pause_state: PauseState = PauseState.NONE
    pause_reason: Optional[str] = None
    pause_checkpoint: Optional[PauseCheckpoint] = None
    
    def to_dict(self) -> dict:
        """Convert to dict for storage"""
        result = {"pause_state": self.pause_state.value}
        if self.pause_reason:
            result["pause_reason"] = self.pause_reason
        if self.pause_checkpoint:
            result["pause_checkpoint"] = self.pause_checkpoint.value
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "PauseMetadata":
        """Create from dict"""
        pause_state = PauseState(data.get("pause_state", PauseState.NONE.value))
        pause_reason = data.get("pause_reason")
        pause_checkpoint_str = data.get("pause_checkpoint")
        pause_checkpoint = PauseCheckpoint(pause_checkpoint_str) if pause_checkpoint_str else None
        
        return cls(
            pause_state=pause_state,
            pause_reason=pause_reason,
            pause_checkpoint=pause_checkpoint
        )


class PauseGateViolation(Exception):
    """Raised when pause gate is violated"""
    pass


def enforce_pause_checkpoint(checkpoint: str) -> None:
    """Enforce pause checkpoint rule
    
    RED LINE: Only open_plan checkpoint is allowed in v1.
    Any other checkpoint will raise PauseGateViolation.
    
    Args:
        checkpoint: Checkpoint name to validate
        
    Raises:
        PauseGateViolation: If checkpoint is not allowed
    """
    if not PauseCheckpoint.is_valid_v1(checkpoint):
        raise PauseGateViolation(
            f"Pause checkpoint '{checkpoint}' is not allowed in v1. "
            f"Only '{PauseCheckpoint.OPEN_PLAN.value}' is permitted."
        )


def can_pause_at(checkpoint: str, run_mode: str) -> bool:
    """Check if pause is allowed at given checkpoint
    
    Args:
        checkpoint: Checkpoint to check
        run_mode: Run mode (interactive/assisted/autonomous)
        
    Returns:
        True if pause is allowed, False otherwise
        
    Raises:
        PauseGateViolation: If checkpoint is not valid for v1
    """
    # First, enforce checkpoint validity
    enforce_pause_checkpoint(checkpoint)
    
    # Then check run_mode
    if run_mode == "interactive":
        # Interactive mode: pause at all checkpoints (but only open_plan exists in v1)
        return True
    elif run_mode == "assisted":
        # Assisted mode: pause at open_plan
        return checkpoint == PauseCheckpoint.OPEN_PLAN.value
    else:  # autonomous
        # Autonomous mode: never pause
        return False


def create_pause_metadata(
    checkpoint: PauseCheckpoint,
    reason: str
) -> PauseMetadata:
    """Create pause metadata
    
    Args:
        checkpoint: Checkpoint where pause happens
        reason: Reason for pause
        
    Returns:
        PauseMetadata instance
        
    Raises:
        PauseGateViolation: If checkpoint is not valid
    """
    # Enforce checkpoint validity
    enforce_pause_checkpoint(checkpoint.value)
    
    return PauseMetadata(
        pause_state=PauseState.AWAITING_APPROVAL,
        pause_reason=reason,
        pause_checkpoint=checkpoint
    )
