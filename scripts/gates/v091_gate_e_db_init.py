#!/usr/bin/env python3
"""
v0.9.1 Gate E: Isolation Testing

Tests that validation works in isolated temporary directory without
depending on current working directory or system state.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.validate_intents import IntentValidator

EXAMPLES_DIR = Path("examples/intents")
SCHEMA_PATH = Path("agentos/schemas/execution/intent.schema.json")


def main():
    print("=" * 60)
    print("v0.9.1 Gate E: Isolation Testing")
    print("=" * 60)

    if not EXAMPLES_DIR.exists():
        print(f"❌ Examples directory not found: {EXAMPLES_DIR}")
        return False

    if not SCHEMA_PATH.exists():
        print(f"❌ Schema not found: {SCHEMA_PATH}")
        return False

    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        print(f"\n📁 Using temporary directory: {tmp_path}")

        # Copy schema
        tmp_schema_dir = tmp_path / "schemas"
        tmp_schema_dir.mkdir(parents=True)
        tmp_schema = tmp_schema_dir / "intent.schema.json"
        shutil.copy(SCHEMA_PATH, tmp_schema)
        print(f"  ✅ Copied schema to {tmp_schema}")

        # Copy examples
        tmp_examples_dir = tmp_path / "examples"
        tmp_examples_dir.mkdir(parents=True)

        json_files = list(EXAMPLES_DIR.glob("*.json"))
        for src_file in json_files:
            dst_file = tmp_examples_dir / src_file.name
            shutil.copy(src_file, dst_file)

        print(f"  ✅ Copied {len(json_files)} example(s) to {tmp_examples_dir}")

        # Initialize validator with temp schema
        try:
            validator = IntentValidator(tmp_schema)
            print(f"  ✅ Validator initialized with isolated schema")
        except Exception as e:
            print(f"  ❌ Failed to initialize validator: {e}")
            return False

        # Validate all examples in temp directory
        print(f"\n🔍 Validating intents in isolated environment...\n")

        all_valid = True
        valid_count = 0

        for intent_file in tmp_examples_dir.glob("*.json"):
            print(f"Validating {intent_file.name}...")

            try:
                with open(intent_file, "r", encoding="utf-8") as f:
                    intent = json.load(f)

                valid, results = validator.validate(intent)

                if valid:
                    print(f"  ✅ VALID")
                    valid_count += 1
                else:
                    print(f"  ❌ INVALID")
                    if not results["schema"]["valid"]:
                        print("    Schema errors detected")
                    if not results["red_lines"]["valid"]:
                        print("    Red line violations detected")
                    all_valid = False

            except Exception as e:
                print(f"  ❌ Error: {e}")
                all_valid = False

        print("\n" + "=" * 60)
        if all_valid:
            print(f"✅ Gate E: PASSED ({valid_count}/{len(json_files)} validated in isolation)")
            print("=" * 60)
            return True
        else:
            print("❌ Gate E: FAILED (validation failed in isolation)")
            print("=" * 60)
            return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
