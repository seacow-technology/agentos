"""
OpenPlan Schema - Open-domain execution plan container

This schema represents the "open plan" concept where AI freely proposes
execution steps while the system enforces structural boundaries.

Design principle: Don't constrain content, only constrain the interface.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json
from datetime import datetime


@dataclass
class ModeSelection:
    """
    Mode selection result from AI understanding
    
    Attributes:
        primary_mode: Primary mode for this execution
        pipeline: Ordered list of modes to execute
        confidence: AI confidence in this selection (0.0-1.0)
        reason: Human-readable explanation for audit trail
    """
    primary_mode: str
    pipeline: List[str]
    confidence: float
    reason: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_mode": self.primary_mode,
            "pipeline": self.pipeline,
            "confidence": self.confidence,
            "reason": self.reason
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModeSelection:
        return cls(
            primary_mode=data["primary_mode"],
            pipeline=data["pipeline"],
            confidence=data["confidence"],
            reason=data["reason"]
        )


@dataclass
class ProposedAction:
    """
    A proposed action in the execution plan
    
    The 'kind' field defines the execution channel:
    - command: Execute shell command
    - file: File operation (create/update/delete)
    - api: API call
    - agent: Delegate to sub-agent
    - rule: Execution constraint
    - check: Verification action
    - note: Human-readable note
    
    The 'payload' is open-domain JSON with minimal required fields
    based on the 'kind'.
    """
    kind: str  # One of: command, file, api, agent, rule, check, note
    payload: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "payload": self.payload
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProposedAction:
        return cls(
            kind=data["kind"],
            payload=data["payload"]
        )


@dataclass
class PlanStep:
    """
    A single step in the execution plan
    
    Each step represents a logical unit of work with:
    - Clear intent (what to achieve)
    - Proposed actions (how to achieve it)
    - Success criteria (how to verify)
    - Risk assessment (what could go wrong)
    """
    id: str
    intent: str
    proposed_actions: List[ProposedAction]
    success_criteria: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "intent": self.intent,
            "proposed_actions": [a.to_dict() for a in self.proposed_actions],
            "success_criteria": self.success_criteria,
            "risks": self.risks
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PlanStep:
        return cls(
            id=data["id"],
            intent=data["intent"],
            proposed_actions=[ProposedAction.from_dict(a) for a in data["proposed_actions"]],
            success_criteria=data.get("success_criteria", []),
            risks=data.get("risks", [])
        )


@dataclass
class Artifact:
    """
    An artifact that will be produced during execution
    
    Artifacts are declared upfront for audit and verification purposes.
    """
    path: str
    role: str  # e.g., "output", "intermediate", "test"
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "role": self.role,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Artifact:
        return cls(
            path=data["path"],
            role=data["role"],
            notes=data.get("notes", "")
        )


@dataclass
class OpenPlan:
    """
    Open Plan - Open-domain execution plan container
    
    This is the unified container for all AI-generated execution plans.
    It provides structure without constraining content.
    
    Key design principles:
    1. No pre-defined step types - AI proposes freely
    2. Fixed execution channels (7 kinds) - system enforces
    3. Minimal required fields - maximum flexibility
    4. Full audit trail - confidence + reason tracked
    """
    goal: str
    mode_selection: ModeSelection
    steps: List[PlanStep]
    artifacts: List[Artifact] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "mode_selection": self.mode_selection.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
            "artifacts": [a.to_dict() for a in self.artifacts],
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OpenPlan:
        return cls(
            goal=data["goal"],
            mode_selection=ModeSelection.from_dict(data["mode_selection"]),
            steps=[PlanStep.from_dict(s) for s in data["steps"]],
            artifacts=[Artifact.from_dict(a) for a in data.get("artifacts", [])],
            metadata=data.get("metadata", {})
        )
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> OpenPlan:
        """Deserialize from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)


# Validation functions

class ValidationError(Exception):
    """Open Plan validation error"""
    def __init__(self, message: str, errors: List[str]):
        super().__init__(message)
        self.errors = errors


def validate_open_plan(plan: OpenPlan) -> None:
    """
    Validate OpenPlan structure (structural validation only)
    
    This performs minimal structural checks:
    - Required fields exist
    - Types are correct
    - Enums are valid
    
    Business rule validation (e.g., planning mode can't have diff)
    is done separately by OpenPlanVerifier.
    
    Args:
        plan: OpenPlan to validate
        
    Raises:
        ValidationError: If validation fails
    """
    errors = []
    
    # Validate goal
    if not plan.goal or not isinstance(plan.goal, str):
        errors.append("goal must be a non-empty string")
    
    # Validate mode_selection
    if not plan.mode_selection:
        errors.append("mode_selection is required")
    else:
        if not plan.mode_selection.primary_mode:
            errors.append("mode_selection.primary_mode is required")
        if not plan.mode_selection.pipeline:
            errors.append("mode_selection.pipeline must be non-empty")
        if not isinstance(plan.mode_selection.confidence, (int, float)):
            errors.append("mode_selection.confidence must be a number")
        elif not (0.0 <= plan.mode_selection.confidence <= 1.0):
            errors.append("mode_selection.confidence must be between 0.0 and 1.0")
        if not plan.mode_selection.reason:
            errors.append("mode_selection.reason is required")
    
    # Validate steps
    if not plan.steps:
        errors.append("steps must be non-empty")
    else:
        for i, step in enumerate(plan.steps):
            step_prefix = f"steps[{i}]"
            
            if not step.id:
                errors.append(f"{step_prefix}.id is required")
            if not step.intent:
                errors.append(f"{step_prefix}.intent is required")
            if not step.proposed_actions:
                errors.append(f"{step_prefix}.proposed_actions must be non-empty")
            
            # Validate actions
            for j, action in enumerate(step.proposed_actions):
                action_prefix = f"{step_prefix}.proposed_actions[{j}]"
                
                if not action.kind:
                    errors.append(f"{action_prefix}.kind is required")
                elif action.kind not in ["command", "file", "api", "agent", "rule", "check", "note"]:
                    errors.append(f"{action_prefix}.kind must be one of: command, file, api, agent, rule, check, note")
                
                if not isinstance(action.payload, dict):
                    errors.append(f"{action_prefix}.payload must be a dict")
    
    # Validate artifacts (optional, but if present must be valid)
    for i, artifact in enumerate(plan.artifacts):
        artifact_prefix = f"artifacts[{i}]"
        
        if not artifact.path:
            errors.append(f"{artifact_prefix}.path is required")
        if not artifact.role:
            errors.append(f"{artifact_prefix}.role is required")
    
    if errors:
        raise ValidationError(
            f"OpenPlan validation failed with {len(errors)} error(s)",
            errors
        )


# JSON Schema for external validation (can be used by gates)
OPEN_PLAN_JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["goal", "mode_selection", "steps"],
    "properties": {
        "goal": {
            "type": "string",
            "minLength": 1,
            "description": "User's original request restated"
        },
        "mode_selection": {
            "type": "object",
            "required": ["primary_mode", "pipeline", "confidence", "reason"],
            "properties": {
                "primary_mode": {
                    "type": "string",
                    "minLength": 1
                },
                "pipeline": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string"}
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0
                },
                "reason": {
                    "type": "string",
                    "minLength": 1
                }
            }
        },
        "steps": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "intent", "proposed_actions"],
                "properties": {
                    "id": {"type": "string"},
                    "intent": {"type": "string"},
                    "proposed_actions": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["kind", "payload"],
                            "properties": {
                                "kind": {
                                    "type": "string",
                                    "enum": ["command", "file", "api", "agent", "rule", "check", "note"]
                                },
                                "payload": {
                                    "type": "object"
                                }
                            }
                        }
                    },
                    "success_criteria": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "risks": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
        },
        "artifacts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["path", "role"],
                "properties": {
                    "path": {"type": "string"},
                    "role": {"type": "string"},
                    "notes": {"type": "string"}
                }
            }
        },
        "metadata": {
            "type": "object"
        }
    }
}
