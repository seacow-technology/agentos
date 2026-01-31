#!/usr/bin/env python3
"""
v0.9.2 Gate I: Question Governance Check

Validates:
- question_budget respects ExecutionPolicy
- All questions have evidence_refs (归因)
- blocking_level consistent with policy
"""

import json
import sys
from pathlib import Path

EXAMPLES_DIR = Path("examples/coordinator/outputs")
FIXTURES_DIR = Path("fixtures/coordinator/invalid")

VALID_PACKS = [
    "question_pack_high_risk_interactive.json"
]

INVALID_PACKS = [
    "full_auto_with_questions.json",
    "question_no_evidence.json"
]


def validate_question_pack(pack, pack_name):
    """Validate a question pack against governance rules"""
    errors = []
    
    policy = pack.get("policy_constraints", {})
    execution_mode = policy.get("execution_mode")
    question_budget = policy.get("question_budget", 0)
    questions = pack.get("questions", [])
    
    # Rule 1: full_auto => question_budget = 0
    if execution_mode == "full_auto" and len(questions) > 0:
        errors.append("full_auto mode must have zero questions")
    
    # Rule 2: budget_consumed <= question_budget
    budget_consumed = policy.get("budget_consumed", 0)
    if budget_consumed > question_budget:
        errors.append(f"Budget exceeded: {budget_consumed} > {question_budget}")
    
    # Rule 3: All questions must have evidence_refs
    for i, question in enumerate(questions):
        evidence_refs = question.get("evidence_refs", [])
        if not evidence_refs:
            errors.append(f"Question {i} ({question.get('question_id')}) has no evidence_refs")
    
    # Rule 4: semi_auto => only blocker questions
    if execution_mode == "semi_auto":
        for question in questions:
            if question.get("type") != "blocker":
                errors.append(f"semi_auto mode only allows blocker questions, found: {question.get('type')}")
    
    return errors


def main():
    print("=" * 70)
    print("v0.9.2 Gate I: Question Governance Check")
    print("=" * 70)

    all_valid = True

    # Check valid packs
    print("\nValidating valid question packs...")
    for pack_file in VALID_PACKS:
        pack_path = EXAMPLES_DIR / pack_file
        
        if not pack_path.exists():
            print(f"  ⚠️  {pack_file} not found")
            continue
        
        print(f"\nChecking {pack_file}...")
        with open(pack_path, "r", encoding="utf-8") as f:
            pack = json.load(f)
        
        errors = validate_question_pack(pack, pack_file)
        if errors:
            print(f"  ❌ Validation failed:")
            for error in errors:
                print(f"     - {error}")
            all_valid = False
        else:
            print(f"  ✅ All governance rules passed")

    # Check invalid packs (should have errors)
    print("\n\nValidating invalid question packs (should fail)...")
    for pack_file in INVALID_PACKS:
        pack_path = FIXTURES_DIR / pack_file
        
        if not pack_path.exists():
            print(f"  ⚠️  {pack_file} not found")
            continue
        
        print(f"\nChecking {pack_file}...")
        with open(pack_path, "r", encoding="utf-8") as f:
            pack = json.load(f)
        
        errors = validate_question_pack(pack, pack_file)
        if errors:
            print(f"  ✅ Correctly detected violations:")
            for error in errors:
                print(f"     - {error}")
        else:
            print(f"  ❌ Should have failed but passed")
            all_valid = False

    print("\n" + "=" * 70)
    if all_valid:
        print("✅ Gate I: PASSED")
        print("=" * 70)
        return True
    else:
        print("❌ Gate I: FAILED")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
