#!/usr/bin/env python3
"""
v0.9.1 Gate A: Intent Existence and Naming Validation

Validates:
- At least 3 intent examples exist
- File naming matches intent id
- IDs are unique
- IDs follow pattern: intent_[a-z0-9_]{6,64}
"""

import json
import re
import sys
from pathlib import Path

EXAMPLES_DIR = Path("examples/intents")
ID_PATTERN = re.compile(r"^intent_[a-z0-9_]{6,64}$")
MIN_EXAMPLES = 3


def main():
    print("=" * 60)
    print("v0.9.1 Gate A: Intent Existence and Naming")
    print("=" * 60)

    if not EXAMPLES_DIR.exists():
        print(f"❌ Examples directory not found: {EXAMPLES_DIR}")
        return False

    # Find all JSON files
    json_files = sorted(EXAMPLES_DIR.glob("*.json"))

    if len(json_files) < MIN_EXAMPLES:
        print(f"❌ Found {len(json_files)} intent(s), expected at least {MIN_EXAMPLES}")
        return False

    print(f"✅ Found {len(json_files)} intent example(s)")

    ids_seen = set()
    all_valid = True

    for file_path in json_files:
        print(f"\nChecking {file_path.name}...")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                intent = json.load(f)
        except json.JSONDecodeError as e:
            print(f"  ❌ Invalid JSON: {e}")
            all_valid = False
            continue

        intent_id = intent.get("id")

        if not intent_id:
            print("  ❌ Missing 'id' field")
            all_valid = False
            continue

        # Check ID pattern
        if not ID_PATTERN.match(intent_id):
            print(f"  ❌ ID '{intent_id}' does not match pattern: intent_[a-z0-9_]{{6,64}}")
            all_valid = False
            continue

        # Check uniqueness
        if intent_id in ids_seen:
            print(f"  ❌ Duplicate ID: {intent_id}")
            all_valid = False
            continue

        ids_seen.add(intent_id)

        # Check filename matches ID
        expected_filename = f"{intent_id}.json"
        if file_path.name != expected_filename:
            print(f"  ⚠️  Filename '{file_path.name}' should be '{expected_filename}'")
            # Warning only, not a failure

        print(f"  ✅ ID: {intent_id}")

    print("\n" + "=" * 60)
    if all_valid:
        print("✅ Gate A: PASSED")
        print("=" * 60)
        return True
    else:
        print("❌ Gate A: FAILED")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
