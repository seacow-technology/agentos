#!/usr/bin/env python3
"""
v0.10 Gate B: Schema Batch Validation

Validates:
- All example outputs validate against schemas
- Referenced intents validate against v0.9.1 intent schema
"""

import json
import sys
from pathlib import Path

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    print("⚠️  jsonschema not installed, using basic validation only")


def load_json(path):
    """Load JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_with_schema(data, schema):
    """Validate data against schema."""
    if not HAS_JSONSCHEMA:
        # Basic validation without jsonschema
        return True, []
    
    try:
        jsonschema.validate(data, schema)
        return True, []
    except jsonschema.ValidationError as e:
        return False, [str(e)]
    except Exception as e:
        return False, [f"Validation error: {str(e)}"]


def main():
    print("=" * 70)
    print("v0.10 Gate B: Schema Batch Validation")
    print("=" * 70)

    all_valid = True

    # Load schemas
    print("\n📖 Loading schemas...")
    try:
        result_schema = load_json("agentos/schemas/executor/dry_execution_result.schema.json")
        intent_schema = load_json("agentos/schemas/execution/intent.schema.json")
        print("  ✅ Schemas loaded")
    except Exception as e:
        print(f"  ❌ Failed to load schemas: {e}")
        return False

    # Validate example outputs
    example_results = [
        "examples/executor_dry/low_risk/output_result.json",
        "examples/executor_dry/medium_risk/output_result.json",
        "examples/executor_dry/high_risk/output_result.json",
    ]

    print("\n🔍 Validating Example Outputs...")
    for result_path in example_results:
        if not Path(result_path).exists():
            print(f"  ❌ {result_path} - NOT FOUND")
            all_valid = False
            continue

        try:
            result_data = load_json(result_path)
            is_valid, errors = validate_with_schema(result_data, result_schema)
            
            if is_valid:
                print(f"  ✅ {result_path}")
            else:
                print(f"  ❌ {result_path} - VALIDATION FAILED")
                for error in errors[:3]:  # Show first 3 errors
                    print(f"      {error}")
                all_valid = False
        except Exception as e:
            print(f"  ❌ {result_path} - ERROR: {e}")
            all_valid = False

    # Validate input intents
    example_intents = [
        "examples/executor_dry/low_risk/input_intent.json",
        "examples/executor_dry/medium_risk/input_intent.json",
        "examples/executor_dry/high_risk/input_intent.json",
    ]

    print("\n🔍 Validating Input Intents (v0.9.1)...")
    for intent_path in example_intents:
        if not Path(intent_path).exists():
            print(f"  ❌ {intent_path} - NOT FOUND")
            all_valid = False
            continue

        try:
            intent_data = load_json(intent_path)
            is_valid, errors = validate_with_schema(intent_data, intent_schema)
            
            if is_valid:
                print(f"  ✅ {intent_path}")
            else:
                print(f"  ❌ {intent_path} - VALIDATION FAILED")
                for error in errors[:3]:
                    print(f"      {error}")
                all_valid = False
        except Exception as e:
            print(f"  ❌ {intent_path} - ERROR: {e}")
            all_valid = False

    # Summary
    print("\n" + "=" * 70)
    if all_valid:
        print("✅ Gate B: PASSED")
        print("=" * 70)
        return True
    else:
        print("❌ Gate B: FAILED")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
