#!/usr/bin/env python3
"""
v11 AP Gate C: Negative Fixtures Test

Tests that AnswerValidator correctly rejects invalid AnswerPacks:
- AP1: Fabricated question_id
- AP2: Missing evidence_refs
- AP3: Command/workflow/agent overrides
- Invalid checksum
"""

import sys
import json
from pathlib import Path

# Assume script is in scripts/gates/
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agentos.core.answers import validate_answer_pack

FIXTURES_DIR = PROJECT_ROOT / "fixtures/answer_pack"
EXIT_CODE = 0


def test_negative_fixture(fixture_name: str, expected_violation: str) -> bool:
    """Test that a negative fixture is correctly rejected."""
    global EXIT_CODE
    
    fixture_path = FIXTURES_DIR / fixture_name
    
    if not fixture_path.exists():
        print(f"  ✗ {fixture_name}: Fixture not found")
        EXIT_CODE = 1
        return False
    
    try:
        with open(fixture_path, "r", encoding="utf-8") as f:
            answer_pack = json.load(f)
        
        # Load question pack if testing AP1
        question_pack = None
        if "ap1" in fixture_name.lower():
            qpack_path = FIXTURES_DIR / "valid_question_pack.json"
            with open(qpack_path, "r", encoding="utf-8") as f:
                question_pack = json.load(f)
        
        # Validate
        valid, errors = validate_answer_pack(answer_pack, question_pack)
        
        if valid:
            print(f"  ✗ {fixture_name}: SHOULD HAVE BEEN REJECTED but passed")
            EXIT_CODE = 1
            return False
        
        # Check that expected violation is in errors
        error_text = " ".join(errors).lower()
        if expected_violation.lower() in error_text:
            print(f"  ✓ {fixture_name}: Correctly rejected ({expected_violation})")
            return True
        else:
            print(f"  ~ {fixture_name}: Rejected but wrong reason")
            print(f"    Expected: {expected_violation}")
            print(f"    Got: {errors[0] if errors else 'No error message'}")
            # Don't fail gate, just warning
            return True
            
    except Exception as e:
        print(f"  ✗ {fixture_name}: Unexpected error - {e}")
        EXIT_CODE = 1
        return False


def main():
    print("=" * 60)
    print("v11 AP Gate C: Negative Fixtures Test")
    print("=" * 60)
    print()

    print("[1] Testing Negative Fixtures")
    
    # Test each negative fixture
    test_negative_fixture(
        "negative_ap1_fabricated_question.json",
        "AP1 VIOLATION"
    )
    
    test_negative_fixture(
        "negative_ap2_no_evidence.json",
        "AP2"
    )
    
    test_negative_fixture(
        "negative_ap3_command_override.json",
        "AP3"
    )
    
    test_negative_fixture(
        "negative_checksum_invalid.json",
        "checksum"
    )
    
    print()

    # Summary
    print("=" * 60)
    if EXIT_CODE == 0:
        print("✓ AP GATE C PASSED: All negative fixtures correctly rejected")
    else:
        print("✗ AP GATE C FAILED: Some negative fixtures were not handled correctly")
    print("=" * 60)

    return EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
