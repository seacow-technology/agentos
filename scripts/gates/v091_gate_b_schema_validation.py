#!/usr/bin/env python3
"""
v0.9.1 Gate B: Schema Batch Validation

Validates all intent examples against intent.schema.json
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.validate_intents import IntentValidator

EXAMPLES_DIR = Path("examples/intents")
SCHEMA_PATH = Path("agentos/schemas/execution/intent.schema.json")


def main():
    print("=" * 60)
    print("v0.9.1 Gate B: Schema Batch Validation")
    print("=" * 60)

    if not EXAMPLES_DIR.exists():
        print(f"❌ Examples directory not found: {EXAMPLES_DIR}")
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

    # Find all JSON files
    json_files = sorted(EXAMPLES_DIR.glob("*.json"))

    if not json_files:
        print(f"❌ No JSON files found in {EXAMPLES_DIR}")
        return False

    print(f"Validating {len(json_files)} intent file(s)...\n")

    all_valid = True

    for file_path in json_files:
        print(f"Validating {file_path.name}...")

        try:
            import json
            with open(file_path, "r", encoding="utf-8") as f:
                intent = json.load(f)

            valid, results = validator.validate(intent)

            if valid:
                print(f"  ✅ VALID")
            else:
                print(f"  ❌ INVALID")

                if not results["schema"]["valid"]:
                    print("    Schema Errors:")
                    for err in results["schema"]["errors"]:
                        print(f"      {err}")

                if not results["checksum"]["valid"]:
                    print(f"    Checksum: {results['checksum']['message']}")

                if not results["red_lines"]["valid"]:
                    print("    Red Line Violations:")
                    for violation in results["red_lines"]["violations"]:
                        print(f"      {violation}")

                all_valid = False

        except Exception as e:
            print(f"  ❌ Error: {e}")
            all_valid = False

    print("\n" + "=" * 60)
    if all_valid:
        print("✅ Gate B: PASSED")
        print("=" * 60)
        return True
    else:
        print("❌ Gate B: FAILED")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
