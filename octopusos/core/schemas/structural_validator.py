"""
Structural validator for OpenPlan

This module provides structural validation for OpenPlan objects.
It checks that the plan has the correct structure and types,
but does NOT check business rules (e.g., planning mode can't have diff).

Business rule validation is handled by OpenPlanVerifier.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .open_plan import OpenPlan, validate_open_plan, ValidationError
from .action_validators import validate_actions


@dataclass
class StructuralValidationReport:
    """Report from structural validation"""
    valid: bool
    errors: List[str]
    warnings: List[str]
    plan_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "plan_id": self.plan_id
        }


class StructuralValidator:
    """
    Structural validator for OpenPlan
    
    Validates:
    1. Required fields exist and are non-empty
    2. Types are correct
    3. Enums are valid
    4. Action payloads have required fields
    5. No structural anomalies
    
    Does NOT validate:
    - Business rules (planning mode can't have diff)
    - Execution feasibility
    - Resource constraints
    """
    
    def __init__(self, strict: bool = False):
        """
        Initialize validator
        
        Args:
            strict: If True, reject unknown fields in action payloads
        """
        self.strict = strict
    
    def validate(self, plan: OpenPlan) -> StructuralValidationReport:
        """
        Validate OpenPlan structure
        
        Args:
            plan: OpenPlan to validate
            
        Returns:
            StructuralValidationReport with validation results
        """
        errors = []
        warnings = []
        
        # 1. Basic structure validation
        try:
            validate_open_plan(plan)
        except ValidationError as e:
            errors.extend(e.errors)
        
        # 2. Action payload validation
        all_actions = []
        for step in plan.steps:
            for action in step.proposed_actions:
                all_actions.append(action.to_dict())
        
        if all_actions:
            from .action_validators import validate_actions as validate_action_list
            result = validate_action_list(all_actions, strict=self.strict)
            
            if not result.valid:
                errors.append(f"Action validation failed: {result.error}")
            
            if result.warnings:
                warnings.extend(result.warnings)
        
        # 3. Additional checks
        
        # Check for duplicate step IDs
        step_ids = [step.id for step in plan.steps]
        if len(step_ids) != len(set(step_ids)):
            duplicates = [sid for sid in step_ids if step_ids.count(sid) > 1]
            errors.append(f"Duplicate step IDs found: {set(duplicates)}")
        
        # Check pipeline consistency
        if plan.mode_selection.primary_mode not in plan.mode_selection.pipeline:
            warnings.append(
                f"Primary mode '{plan.mode_selection.primary_mode}' "
                f"not in pipeline {plan.mode_selection.pipeline}"
            )
        
        # Check for empty steps
        for i, step in enumerate(plan.steps):
            if not step.proposed_actions:
                errors.append(f"Step[{i}] '{step.id}' has no proposed actions")
        
        # Check confidence bounds
        confidence = plan.mode_selection.confidence
        if confidence < 0.0 or confidence > 1.0:
            errors.append(f"Confidence {confidence} out of range [0.0, 1.0]")
        elif confidence < 0.3:
            warnings.append(
                f"Low confidence ({confidence}) in mode selection - "
                "consider manual review or fallback to rule-based selector"
            )
        
        # 4. Generate report
        return StructuralValidationReport(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            plan_id=plan.metadata.get("plan_id")
        )
    
    def validate_from_dict(self, plan_dict: Dict[str, Any]) -> StructuralValidationReport:
        """
        Validate OpenPlan from dict
        
        Args:
            plan_dict: OpenPlan as dict
            
        Returns:
            StructuralValidationReport
        """
        try:
            plan = OpenPlan.from_dict(plan_dict)
            return self.validate(plan)
        except Exception as e:
            return StructuralValidationReport(
                valid=False,
                errors=[f"Failed to parse OpenPlan: {str(e)}"],
                warnings=[]
            )
    
    def validate_from_json(self, plan_json: str) -> StructuralValidationReport:
        """
        Validate OpenPlan from JSON string
        
        Args:
            plan_json: OpenPlan as JSON string
            
        Returns:
            StructuralValidationReport
        """
        try:
            plan = OpenPlan.from_json(plan_json)
            return self.validate(plan)
        except Exception as e:
            return StructuralValidationReport(
                valid=False,
                errors=[f"Failed to parse JSON: {str(e)}"],
                warnings=[]
            )


def validate_open_plan_structure(plan: OpenPlan, strict: bool = False) -> StructuralValidationReport:
    """
    Convenience function to validate OpenPlan structure
    
    Args:
        plan: OpenPlan to validate
        strict: If True, reject unknown fields in action payloads
        
    Returns:
        StructuralValidationReport
    """
    validator = StructuralValidator(strict=strict)
    return validator.validate(plan)
