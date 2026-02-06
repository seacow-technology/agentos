"""
OpenPlanVerifier - Business rule validation for OpenPlan (Layer 2)

VALIDATION LAYER: Business Rules (BR)
职责：业务语义自洽性检查

This module enforces business rules that go beyond structural validation:
- Mode-specific constraints (e.g., planning mode can't have diff)
- Pipeline transition rules
- Resource constraints
- Security policies

IMPORTANT: This is Layer 2 (Business Rules).
It does NOT cover Layer 3 (Dry Executor RED LINE):
    - ❌ DE3: Path fabrication detection
    - ❌ DE4: evidence_refs enforcement
    - ❌ DE5: requires_review enforcement
    - ❌ DE6: checksum/lineage enforcement

These are handled by DryExecutorValidator (Layer 3).

Architecture Decision:
    BR 和 DE 不对齐是设计选择，不是缺陷。
    见：docs/architecture/VALIDATION_LAYERS.md
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..schemas import OpenPlan, ProposedAction
# Avoid importing from ..mode to prevent circular dependency
# from ..mode import get_mode, Mode


@dataclass
class BusinessRuleViolation:
    """A business rule violation"""
    rule_id: str
    severity: str  # error, warning
    message: str
    step_id: Optional[str] = None
    action_index: Optional[int] = None


@dataclass
class BusinessValidationReport:
    """Report from business rule validation"""
    valid: bool
    violations: List[BusinessRuleViolation]
    warnings: List[BusinessRuleViolation]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "severity": v.severity,
                    "message": v.message,
                    "step_id": v.step_id,
                    "action_index": v.action_index
                }
                for v in self.violations
            ],
            "warnings": [
                {
                    "rule_id": w.rule_id,
                    "severity": w.severity,
                    "message": w.message,
                    "step_id": w.step_id,
                    "action_index": w.action_index
                }
                for w in self.warnings
            ]
        }


class OpenPlanVerifier:
    """
    Business rule verifier for OpenPlan
    
    Validates:
    1. Mode-specific constraints (planning can't have diff)
    2. Pipeline transition rules
    3. Action feasibility
    4. Security constraints
    
    Does NOT validate:
    - Structure (handled by StructuralValidator)
    - Action payload completeness (handled by action_validators)
    
    IMPORTANT: This is NOT a "semantic reasoner"
    
    Verifier's role is limited to:
    - Structural legality (does the plan have required fields?)
    - Mode/Gate safety (does planning mode have diff? → reject)
    - Executor capability (does the action kind exist? → check)
    
    Verifier MUST NOT:
    - Judge if the plan "makes sense"
    - Evaluate if steps are "in the right order"
    - Decide if this "looks like a valid task"
    
    These are LLM's job. Verifier只做机械校验,不做理解判断。
    """
    
    # Business rules registry
    RULES = {
        "BR001": "Planning mode steps cannot contain file create/update/delete operations",
        "BR002": "Implementation mode must have at least one file operation",
        "BR003": "Pipeline transitions must be valid",
        "BR004": "Commands must be in allowlist (if provided)",
        "BR005": "File operations must respect allowed_paths (if provided)",
        "BR006": "No circular agent delegation",
        "BR007": "Check operations must be feasible",
    }
    
    # Policy classification: which rules are "soft" (can be overridden with audit)
    SOFT_POLICIES = {
        "BR006",  # Circular delegation warning, not error
        "BR007",  # Feasibility check, not blocking
    }
    
    def __init__(
        self,
        allowlist_commands: Optional[List[str]] = None,
        allowed_paths: Optional[List[str]] = None,
        forbidden_paths: Optional[List[str]] = None
    ):
        """
        Initialize verifier
        
        Args:
            allowlist_commands: Allowed shell commands
            allowed_paths: Allowed file paths (glob patterns)
            forbidden_paths: Forbidden file paths (glob patterns)
        """
        self.allowlist_commands = allowlist_commands or []
        self.allowed_paths = allowed_paths or []
        self.forbidden_paths = forbidden_paths or []
    
    def verify(self, plan: OpenPlan) -> BusinessValidationReport:
        """
        Verify OpenPlan business rules
        
        Args:
            plan: OpenPlan to verify
            
        Returns:
            BusinessValidationReport with violations and warnings
        """
        violations = []
        warnings = []
        
        # Rule BR001: Planning mode constraints
        if "planning" in plan.mode_selection.pipeline:
            planning_violations = self._check_planning_mode_constraints(plan)
            violations.extend(planning_violations)
        
        # Rule BR002: Implementation mode requirements
        if "implementation" in plan.mode_selection.pipeline:
            impl_violations = self._check_implementation_mode_requirements(plan)
            violations.extend(impl_violations)
        
        # Rule BR003: Pipeline transitions
        pipeline_violations = self._check_pipeline_transitions(plan)
        violations.extend(pipeline_violations)
        
        # Rule BR004: Command allowlist
        if self.allowlist_commands:
            command_violations = self._check_command_allowlist(plan)
            violations.extend(command_violations)
        
        # Rule BR005: File path constraints
        if self.allowed_paths or self.forbidden_paths:
            path_violations = self._check_file_path_constraints(plan)
            violations.extend(path_violations)
        
        # Rule BR006: No circular delegation
        delegation_warnings = self._check_agent_delegation(plan)
        warnings.extend(delegation_warnings)
        
        # Rule BR007: Check feasibility
        check_warnings = self._check_operation_feasibility(plan)
        warnings.extend(check_warnings)
        
        # Separate errors from warnings
        errors = [v for v in violations if v.severity == "error"]
        
        return BusinessValidationReport(
            valid=len(errors) == 0,
            violations=errors,
            warnings=warnings
        )
    
    def _check_planning_mode_constraints(self, plan: OpenPlan) -> List[BusinessRuleViolation]:
        """BR001: Planning mode cannot have file modifications"""
        violations = []
        
        # Heuristic: If planning comes before implementation, first half is planning
        pipeline = plan.mode_selection.pipeline
        planning_idx = pipeline.index("planning") if "planning" in pipeline else -1
        impl_idx = pipeline.index("implementation") if "implementation" in pipeline else -1
        
        if planning_idx < 0:
            return violations
        
        # Determine which steps are in planning phase
        planning_steps = plan.steps
        if impl_idx > planning_idx:
            # Split steps: first half is planning, second half is implementation
            split_point = len(plan.steps) // 2
            planning_steps = plan.steps[:split_point]
        
        # Check planning steps for file modifications
        for step in planning_steps:
            for i, action in enumerate(step.proposed_actions):
                if action.kind == "file":
                    operation = action.payload.get("operation")
                    if operation in ["create", "update", "delete"]:
                        violations.append(BusinessRuleViolation(
                            rule_id="BR001",
                            severity="error",
                            message=f"Planning phase step '{step.id}' contains file {operation} operation. "
                                    f"Planning mode can only 'declare' files, not modify them.",
                            step_id=step.id,
                            action_index=i
                        ))
        
        return violations
    
    def _check_implementation_mode_requirements(self, plan: OpenPlan) -> List[BusinessRuleViolation]:
        """BR002: Implementation mode must have file operations"""
        violations = []
        
        if "implementation" not in plan.mode_selection.pipeline:
            return violations
        
        # Check if there's at least one file operation
        has_file_op = False
        for step in plan.steps:
            for action in step.proposed_actions:
                if action.kind == "file" and action.payload.get("operation") in ["create", "update"]:
                    has_file_op = True
                    break
            if has_file_op:
                break
        
        if not has_file_op:
            violations.append(BusinessRuleViolation(
                rule_id="BR002",
                severity="error",
                message="Implementation mode pipeline must include at least one file create/update operation. "
                        "This plan has no file modifications."
            ))
        
        return violations
    
    def _check_pipeline_transitions(self, plan: OpenPlan) -> List[BusinessRuleViolation]:
        """BR003: Validate pipeline transitions"""
        violations = []
        
        pipeline = plan.mode_selection.pipeline
        
        # Invalid transitions
        INVALID_TRANSITIONS = [
            ("implementation", "planning"),  # Can't plan after implementing
            ("release", "planning"),  # Can't plan after release
            ("release", "implementation"),  # Can't implement after release
        ]
        
        for i in range(len(pipeline) - 1):
            current = pipeline[i]
            next_mode = pipeline[i + 1]
            
            if (current, next_mode) in INVALID_TRANSITIONS:
                violations.append(BusinessRuleViolation(
                    rule_id="BR003",
                    severity="error",
                    message=f"Invalid pipeline transition: {current} → {next_mode}. "
                            f"This transition is not allowed."
                ))
        
        # Check for duplicates
        if len(pipeline) != len(set(pipeline)):
            violations.append(BusinessRuleViolation(
                rule_id="BR003",
                severity="warning",
                message=f"Pipeline contains duplicate modes: {pipeline}. "
                        f"Each mode should appear only once."
            ))
        
        return violations
    
    def _check_command_allowlist(self, plan: OpenPlan) -> List[BusinessRuleViolation]:
        """BR004: Commands must be in allowlist"""
        violations = []
        
        for step in plan.steps:
            for i, action in enumerate(step.proposed_actions):
                if action.kind == "command":
                    cmd = action.payload.get("cmd", "")
                    # Extract command name (first word)
                    cmd_name = cmd.split()[0] if cmd else ""
                    
                    if cmd_name and cmd_name not in self.allowlist_commands:
                        violations.append(BusinessRuleViolation(
                            rule_id="BR004",
                            severity="error",
                            message=f"Command '{cmd_name}' is not in allowlist. "
                                    f"Allowed commands: {', '.join(self.allowlist_commands)}",
                            step_id=step.id,
                            action_index=i
                        ))
        
        return violations
    
    def _check_file_path_constraints(self, plan: OpenPlan) -> List[BusinessRuleViolation]:
        """BR005: File operations must respect path constraints"""
        violations = []
        
        for step in plan.steps:
            for i, action in enumerate(step.proposed_actions):
                if action.kind == "file":
                    path = action.payload.get("path", "")
                    
                    # Check forbidden paths
                    for forbidden in self.forbidden_paths:
                        if self._path_matches_pattern(path, forbidden):
                            violations.append(BusinessRuleViolation(
                                rule_id="BR005",
                                severity="error",
                                message=f"File path '{path}' matches forbidden pattern '{forbidden}'",
                                step_id=step.id,
                                action_index=i
                            ))
                    
                    # Check allowed paths (if specified)
                    if self.allowed_paths:
                        allowed = False
                        for allowed_pattern in self.allowed_paths:
                            if self._path_matches_pattern(path, allowed_pattern):
                                allowed = True
                                break
                        
                        if not allowed:
                            violations.append(BusinessRuleViolation(
                                rule_id="BR005",
                                severity="error",
                                message=f"File path '{path}' does not match any allowed pattern. "
                                        f"Allowed: {', '.join(self.allowed_paths)}",
                                step_id=step.id,
                                action_index=i
                            ))
        
        return violations
    
    def _check_agent_delegation(self, plan: OpenPlan) -> List[BusinessRuleViolation]:
        """BR006: Check for circular agent delegation"""
        warnings = []
        
        # Count agent delegations
        agent_count = 0
        for step in plan.steps:
            for action in step.proposed_actions:
                if action.kind == "agent":
                    agent_count += 1
        
        if agent_count > 5:
            warnings.append(BusinessRuleViolation(
                rule_id="BR006",
                severity="warning",
                message=f"Plan has {agent_count} agent delegations. "
                        f"Consider consolidating to avoid excessive nesting."
            ))
        
        return warnings
    
    def _check_operation_feasibility(self, plan: OpenPlan) -> List[BusinessRuleViolation]:
        """BR007: Check if operations are feasible"""
        warnings = []
        
        # Check for operations that might not be feasible
        for step in plan.steps:
            for action in step.proposed_actions:
                if action.kind == "check":
                    check_type = action.payload.get("check_type")
                    target = action.payload.get("target")
                    
                    if not target:
                        warnings.append(BusinessRuleViolation(
                            rule_id="BR007",
                            severity="warning",
                            message=f"Check action in step '{step.id}' has no target specified",
                            step_id=step.id
                        ))
        
        return warnings
    
    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Simple glob pattern matching"""
        import fnmatch
        return fnmatch.fnmatch(path, pattern)


# Convenience function
def verify_open_plan(
    plan: OpenPlan,
    allowlist_commands: Optional[List[str]] = None,
    allowed_paths: Optional[List[str]] = None,
    forbidden_paths: Optional[List[str]] = None
) -> BusinessValidationReport:
    """
    Convenience function to verify OpenPlan business rules
    
    Args:
        plan: OpenPlan to verify
        allowlist_commands: Allowed commands
        allowed_paths: Allowed file paths
        forbidden_paths: Forbidden file paths
        
    Returns:
        BusinessValidationReport
    """
    verifier = OpenPlanVerifier(
        allowlist_commands=allowlist_commands,
        allowed_paths=allowed_paths,
        forbidden_paths=forbidden_paths
    )
    return verifier.verify(plan)
