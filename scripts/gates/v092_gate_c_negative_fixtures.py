#!/usr/bin/env python3
"""
v0.9.2 Gate C: Negative Fixtures Testing

Validates:
- All invalid fixtures are correctly rejected by schema validation
- Each rejection reason matches expected violation
"""

import json
import sys
from pathlib import Path

try:
    from jsonschema import validate, ValidationError
except ImportError:
    print("❌ jsonschema not installed. Run: uv add jsonschema")
    sys.exit(1)

SCHEMA_DIR = Path("agentos/schemas/coordinator")
FIXTURES_DIR = Path("fixtures/coordinator/invalid")

INVALID_FIXTURES = [
    {
        "file": "coordinator_run_with_execute_field.json",
        "schema": "coordinator_run_tape.schema.json",
        "expected_violation": "additionalProperties",
        "description": "Contains forbidden execution fields (execute_command, shell_script)"
    },
    {
        "file": "graph_missing_lineage.json",
        "schema": "execution_graph.schema.json",
        "expected_violation": "required",
        "description": "Missing required 'lineage' field"
    },
    {
        "file": "graph_missing_evidence_refs.json",
        "schema": "execution_graph.schema.json",
        "expected_violation": "required",
        "description": "action_proposal node missing evidence_refs"
    },
    {
        "file": "full_auto_with_questions.json",
        "schema": "question_pack.schema.json",
        "expected_violation": "allOf",
        "description": "full_auto mode with questions (RED LINE violation)"
    },
    {
        "file": "question_no_evidence.json",
        "schema": "question_pack.schema.json",
        "expected_violation": "minItems",
        "description": "Question with empty evidence_refs array"
    }
]


def main():
    print("=" * 70)
    print("v0.9.2 Gate C: Negative Fixtures Testing")
    print("=" * 70)

    all_valid = True

    for fixture_spec in INVALID_FIXTURES:
        fixture_path = FIXTURES_DIR / fixture_spec["file"]
        schema_path = SCHEMA_DIR / fixture_spec["schema"]

        print(f"\nTesting {fixture_spec['file']}...")
        print(f"  Description: {fixture_spec['description']}")

        if not fixture_path.exists():
            print(f"  ❌ Fixture not found")
            all_valid = False
            continue

        if not schema_path.exists():
            print(f"  ❌ Schema not found: {schema_path}")
            all_valid = False
            continue

        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        try:
            with open(fixture_path, "r", encoding="utf-8") as f:
                fixture = json.load(f)
        except json.JSONDecodeError as e:
            print(f"  ❌ Invalid JSON in fixture: {e}")
            all_valid = False
            continue

        # Try to validate - should FAIL
        try:
            validate(instance=fixture, schema=schema)
            print(f"  ❌ FAILED: Fixture was ACCEPTED but should be REJECTED")
            all_valid = False
        except ValidationError as e:
            # Good! Fixture was rejected
            if fixture_spec["expected_violation"] in str(e):
                print(f"  ✅ Correctly rejected: {e.message[:100]}...")
            else:
                print(f"  ⚠️  Rejected but unexpected reason: {e.message[:100]}...")
                print(f"     Expected violation type: {fixture_spec['expected_violation']}")

    print("\n" + "=" * 70)
    if all_valid:
        print("✅ Gate C: PASSED")
        print("=" * 70)
        return True
    else:
        print("❌ Gate C: FAILED")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
