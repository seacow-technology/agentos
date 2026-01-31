#!/usr/bin/env python3
"""
v0.9.1 Gate C: Negative Fixtures Validation

Tests that invalid fixtures are correctly rejected by the validator.
Must reject all 4 invalid fixtures.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.validate_intents import IntentValidator

FIXTURES_DIR = Path("fixtures/intents/invalid")
SCHEMA_PATH = Path("agentos/schemas/execution/intent.schema.json")
EXPECTED_FIXTURES = {
    "intent_has_execute_field.json": "I1 violation (has execute field)",
    "intent_full_auto_with_questions.json": "I2 violation (full_auto with questions)",
    "intent_missing_constraints.json": "I5 violation (wrong constraints)",
    "intent_high_risk_full_auto.json": "I3 violation (high risk + full_auto)",
}


def main():
    print("=" * 60)
    print("v0.9.1 Gate C: Negative Fixtures Validation")
    print("=" * 60)

    if not FIXTURES_DIR.exists():
        print(f"❌ Fixtures directory not found: {FIXTURES_DIR}")
        return False

    if not SCHEMA_PATH.exists():
        print(f"❌ Schema not found: {SCHEMA_PATH}")
        return False

    # Initialize validator
    try:
        validator = IntentValidator(SCHEMA_PATH)
    except Exception as e:
        print(f"❌ Failed to initialize validator: {e}")
        return False

    print(f"Testing {len(EXPECTED_FIXTURES)} negative fixture(s)...\n")

    all_rejected = True

    for filename, expected_reason in EXPECTED_FIXTURES.items():
        file_path = FIXTURES_DIR / filename

        if not file_path.exists():
            print(f"❌ {filename}: Missing fixture file")
            all_rejected = False
            continue

        print(f"Testing {filename} ({expected_reason})...")

        try:
            import json
            with open(file_path, "r", encoding="utf-8") as f:
                intent = json.load(f)

            valid, results = validator.validate(intent)

            if valid:
                print(f"  ❌ FAILED: Fixture should be rejected but was accepted")
                all_rejected = False
            else:
                print(f"  ✅ PASSED: Correctly rejected")

                # Show why it was rejected
                violations = []
                if not results["schema"]["valid"]:
                    violations.append("Schema errors")
                if not results["red_lines"]["valid"]:
                    violations.extend(results["red_lines"]["violations"])

                print(f"     Reasons: {', '.join(violations[:2])}")

        except Exception as e:
            print(f"  ❌ Error: {e}")
            all_rejected = False

    print("\n" + "=" * 60)
    if all_rejected:
        print("✅ Gate C: PASSED (all invalid fixtures rejected)")
        print("=" * 60)
        return True
    else:
        print("❌ Gate C: FAILED (some fixtures not rejected)")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
