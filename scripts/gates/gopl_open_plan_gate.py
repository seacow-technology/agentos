#!/usr/bin/env python3
"""
GOPL Gate: Open Plan Structural Validation Gate

This gate ensures that all experimental_open_plan mode outputs
conform to the OpenPlan schema and constraints.

Gate ID: GOPL
Category: Structural Integrity
Enforcement: Hard (CI fails if gate fails)

Checks:
1. OpenPlan schema conformance
2. Action kind validity
3. Required fields presence
4. Type correctness
5. No diff/apply actions in planning phase
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agentos.core.schemas import (
    OpenPlan,
    validate_open_plan_structure,
    StructuralValidator
)


class GOPLGate:
    """Open Plan Gate - validates OpenPlan structure"""
    
    GATE_ID = "GOPL"
    GATE_NAME = "Open Plan Structural Validation"
    
    def __init__(self, strict: bool = False):
        self.strict = strict
        self.validator = StructuralValidator(strict=strict)
        self.violations: List[str] = []
    
    def check_file(self, file_path: Path) -> bool:
        """
        Check a single file for OpenPlan validity
        
        Args:
            file_path: Path to OpenPlan JSON file
            
        Returns:
            True if valid, False otherwise
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                plan_dict = json.load(f)
            
            # Check if this is an OpenPlan file
            if "mode_selection" not in plan_dict or "steps" not in plan_dict:
                # Not an OpenPlan file, skip
                return True
            
            # Check if mode is experimental_open_plan
            mode_selection = plan_dict.get("mode_selection", {})
            if "experimental_open_plan" not in mode_selection.get("pipeline", []):
                # Not using experimental_open_plan mode, skip
                return True
            
            # Validate structure
            report = self.validator.validate_from_dict(plan_dict)
            
            if not report.valid:
                for error in report.errors:
                    self.violations.append(f"{file_path}: {error}")
                return False
            
            # Check for diff/apply actions in planning phase
            # (this is a simplified business rule check)
            plan = OpenPlan.from_dict(plan_dict)
            
            if "planning" in plan.mode_selection.pipeline:
                planning_position = plan.mode_selection.pipeline.index("planning")
                impl_position = -1
                if "implementation" in plan.mode_selection.pipeline:
                    impl_position = plan.mode_selection.pipeline.index("implementation")
                
                # Check steps that would execute during planning phase
                for i, step in enumerate(plan.steps):
                    # Heuristic: steps in first half are planning phase
                    if impl_position >= 0 and i < len(plan.steps) / 2:
                        for action in step.proposed_actions:
                            if action.kind == "file" and action.payload.get("operation") in ["create", "update"]:
                                self.violations.append(
                                    f"{file_path}: Step '{step.id}' in planning phase "
                                    f"contains file modification action (kind={action.kind})"
                                )
                                return False
            
            return True
            
        except Exception as e:
            self.violations.append(f"{file_path}: Failed to parse - {str(e)}")
            return False
    
    def run(self, paths: List[Path]) -> bool:
        """
        Run gate on all files in paths
        
        Args:
            paths: List of paths to check (files or directories)
            
        Returns:
            True if all checks pass, False otherwise
        """
        files_to_check = []
        
        for path in paths:
            if path.is_file():
                if path.suffix == ".json":
                    files_to_check.append(path)
            elif path.is_dir():
                files_to_check.extend(path.rglob("*.json"))
        
        if not files_to_check:
            print(f"✓ {self.GATE_ID}: No OpenPlan files to check")
            return True
        
        print(f"Checking {len(files_to_check)} JSON file(s) for OpenPlan validity...")
        
        all_valid = True
        checked_count = 0
        
        for file_path in files_to_check:
            if not self.check_file(file_path):
                all_valid = False
            else:
                checked_count += 1
        
        if all_valid:
            print(f"✓ {self.GATE_ID}: All {checked_count} OpenPlan file(s) valid")
            return True
        else:
            print(f"\n❌ {self.GATE_ID}: Found {len(self.violations)} violation(s):\n")
            for violation in self.violations:
                print(f"  - {violation}")
            return False
    
    def print_report(self):
        """Print gate report"""
        print(f"\n{'='*60}")
        print(f"Gate: {self.GATE_NAME} ({self.GATE_ID})")
        print(f"{'='*60}")
        
        if self.violations:
            print(f"\nViolations: {len(self.violations)}")
            for violation in self.violations:
                print(f"  - {violation}")
        else:
            print("\n✓ No violations found")
        
        print(f"\n{'='*60}\n")


def main():
    """Main gate entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="GOPL Gate: Open Plan Structural Validation"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["runs", "tests/fixtures"],
        help="Paths to check (default: runs, tests/fixtures)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict mode (reject unknown action payload fields)"
    )
    
    args = parser.parse_args()
    
    # Convert paths to Path objects
    paths = [Path(p) for p in args.paths]
    
    # Filter out non-existent paths
    existing_paths = [p for p in paths if p.exists()]
    
    if not existing_paths:
        print(f"✓ GOPL: No paths exist to check, skipping")
        return 0
    
    gate = GOPLGate(strict=args.strict)
    success = gate.run(existing_paths)
    
    gate.print_report()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
