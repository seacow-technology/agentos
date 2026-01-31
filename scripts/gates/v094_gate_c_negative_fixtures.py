#!/usr/bin/env python3
"""
v0.9.4 Gate C: Negative Fixtures Test

Tests that invalid fixtures are correctly rejected:
1. missing_evidence_refs - Should be rejected (empty evidence_refs)
2. fabricated_command - Should be rejected (non-existent command_id)
3. full_auto_with_questions - Should be rejected (questions in full_auto mode)
4. output_has_execute_field - Should be rejected (execute field present)
"""

import json
import sys
from pathlib import Path

FIXTURES_DIR = Path("fixtures/intent_builder/invalid")

FIXTURES_TESTS = [
    {
        "file": "missing_evidence_refs.json",
        "expected_violation": "Empty evidence_refs array",
        "check": lambda data: len(data["selection_evidence"]["workflow_selections"][0]["evidence_refs"]) == 0
    },
    {
        "file": "fabricated_command.json",
        "expected_violation": "Fabricated command ID (cmd_nonexistent_fabricated_xyz)",
        "check": lambda data: any(
            cmd["command_id"].startswith("cmd_nonexistent") 
            for cmd in data["execution_intent"]["planned_commands"]
        )
    },
    {
        "file": "full_auto_with_questions.json",
        "expected_violation": "Questions present in full_auto mode",
        "check": lambda data: (
            data["builder_audit"]["policy_applied"] == "full_auto" and
            data["question_pack"] is not None and
            len(data["question_pack"]["questions"]) > 0
        )
    },
    {
        "file": "output_has_execute_field.json",
        "expected_violation": "Execute field present in command",
        "check": lambda data: any(
            "execute" in cmd or "shell_command" in cmd
            for cmd in data["execution_intent"]["planned_commands"]
        )
    }
]


def main():
    print("=" * 70)
    print("v0.9.4 Gate C: Negative Fixtures Test")
    print("=" * 70)
    
    all_valid = True
    
    for test in FIXTURES_TESTS:
        fixture_path = FIXTURES_DIR / test["file"]
        print(f"\n📄 Testing {test['file']}...")
        print(f"   Expected violation: {test['expected_violation']}")
        
        if not fixture_path.exists():
            print(f"   ❌ Fixture file NOT FOUND")
            all_valid = False
            continue
        
        try:
            with open(fixture_path, "r", encoding="utf-8") as f:
                fixture_data = json.load(f)
            
            # Run the check
            if test["check"](fixture_data):
                print(f"   ✅ Violation DETECTED (fixture is correctly invalid)")
            else:
                print(f"   ❌ Violation NOT DETECTED (fixture may be valid)")
                all_valid = False
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
            all_valid = False
    
    # Summary
    print("\n" + "=" * 70)
    if all_valid:
        print("✅ Gate C: PASSED - All fixtures correctly represent violations")
        print("=" * 70)
        return True
    else:
        print("❌ Gate C: FAILED - Some fixtures do not represent expected violations")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
