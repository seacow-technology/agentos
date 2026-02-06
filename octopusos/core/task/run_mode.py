"""Run Mode definitions for Task execution control"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional


class RunMode(str, Enum):
    """Run mode: Human-machine interaction policy"""
    
    INTERACTIVE = "interactive"  # Every stage requires human confirmation
    ASSISTED = "assisted"         # Auto by default, but can pause at key points
    AUTONOMOUS = "autonomous"     # Full auto execution
    
    @classmethod
    def default(cls) -> "RunMode":
        """Get default run mode"""
        return cls.ASSISTED
    
    def requires_approval_at(self, stage: str) -> bool:
        """Check if this run mode requires approval at given stage"""
        if self == RunMode.INTERACTIVE:
            # Interactive mode requires approval at all key stages
            return stage in ["planning", "execution", "rollback"]
        elif self == RunMode.ASSISTED:
            # Assisted mode only requires approval at planning stage
            return stage in ["planning"]
        else:
            # Autonomous mode never requires approval
            return False


@dataclass
class ModelPolicy:
    """Model policy: Model selection strategy for different stages"""
    
    default: str = "gpt-4.1"
    intent: Optional[str] = None
    planning: Optional[str] = None
    implementation: Optional[str] = None
    
    def get_model_for_stage(self, stage: str) -> str:
        """Get model for specific stage"""
        stage_model = getattr(self, stage, None)
        return stage_model if stage_model else self.default
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary"""
        return {
            "default": self.default,
            "intent": self.intent or self.default,
            "planning": self.planning or self.default,
            "implementation": self.implementation or self.default,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "ModelPolicy":
        """Create from dictionary"""
        return cls(
            default=data.get("default", "gpt-4.1"),
            intent=data.get("intent"),
            planning=data.get("planning"),
            implementation=data.get("implementation"),
        )
    
    @classmethod
    def default_policy(cls) -> "ModelPolicy":
        """Get default model policy"""
        return cls(
            default="gpt-4.1",
            intent="gpt-4.1-mini",  # Use cheaper model for intent
            planning="gpt-4.1",
            implementation="gpt-4.1",
        )


@dataclass
class TaskMetadata:
    """Type-safe wrapper for Task.metadata fields"""
    
    run_mode: RunMode = field(default_factory=RunMode.default)
    model_policy: ModelPolicy = field(default_factory=ModelPolicy.default_policy)
    nl_request: Optional[str] = None
    current_stage: Optional[str] = None
    
    # Other metadata fields (extensible)
    extra: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary (for Task.metadata)"""
        result = {
            "run_mode": self.run_mode.value,
            "model_policy": self.model_policy.to_dict(),
        }
        if self.nl_request:
            result["nl_request"] = self.nl_request
        if self.current_stage:
            result["current_stage"] = self.current_stage
        result.update(self.extra)
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> "TaskMetadata":
        """Create from dictionary (from Task.metadata)"""
        run_mode_str = data.get("run_mode", RunMode.default().value)
        run_mode = RunMode(run_mode_str)
        
        model_policy_data = data.get("model_policy", {})
        model_policy = ModelPolicy.from_dict(model_policy_data)
        
        # Extract known fields
        known_fields = {"run_mode", "model_policy", "nl_request", "current_stage"}
        extra = {k: v for k, v in data.items() if k not in known_fields}
        
        return cls(
            run_mode=run_mode,
            model_policy=model_policy,
            nl_request=data.get("nl_request"),
            current_stage=data.get("current_stage"),
            extra=extra,
        )
