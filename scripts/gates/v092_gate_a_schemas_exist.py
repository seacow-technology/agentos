#!/usr/bin/env python3
"""
v0.9.2 Gate A: Coordinator Schema Existence and Structure Validation

Validates:
- 5 coordinator schema files exist
- Schema structure completeness (required fields)
- Schema IDs and versions correct
"""

import json
import sys
from pathlib import Path

SCHEMA_DIR = Path("agentos/schemas/coordinator")

EXPECTED_SCHEMAS = {
    "execution_graph.schema.json": {
        "id": "agentos://schemas/coordinator/execution_graph.schema.json",
        "version": "0.9.2",
        "required_fields": ["graph_id", "intent_id", "nodes", "edges", "swimlanes", "lineage", "checksum"]
    },
    "question_pack.schema.json": {
        "id": "agentos://schemas/coordinator/question_pack.schema.json",
        "version": "0.9.2",
        "required_fields": ["pack_id", "coordinator_run_id", "questions", "policy_constraints"]
    },
    "answer_pack.schema.json": {
        "id": "agentos://schemas/coordinator/answer_pack.schema.json",
        "version": "0.9.2",
        "required_fields": ["pack_id", "question_pack_id", "answers"]
    },
    "coordinator_run_tape.schema.json": {
        "id": "agentos://schemas/coordinator/coordinator_run_tape.schema.json",
        "version": "0.9.2",
        "required_fields": ["run_id", "intent_id", "coordinator_version", "states", "decisions"]
    },
    "coordinator_audit_log.schema.json": {
        "id": "agentos://schemas/coordinator/coordinator_audit_log.schema.json",
        "version": "0.9.2",
        "required_fields": ["log_id", "event_type", "coordinator_run_id", "timestamp"]
    }
}


def main():
    print("=" * 70)
    print("v0.9.2 Gate A: Coordinator Schema Existence and Structure")
    print("=" * 70)

    if not SCHEMA_DIR.exists():
        print(f"❌ Schema directory not found: {SCHEMA_DIR}")
        return False

    all_valid = True

    for schema_file, expected in EXPECTED_SCHEMAS.items():
        schema_path = SCHEMA_DIR / schema_file
        print(f"\nChecking {schema_file}...")

        if not schema_path.exists():
            print(f"  ❌ File not found")
            all_valid = False
            continue

        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
        except json.JSONDecodeError as e:
            print(f"  ❌ Invalid JSON: {e}")
            all_valid = False
            continue

        # Check $id
        if schema.get("$id") != expected["id"]:
            print(f"  ❌ Incorrect $id: {schema.get('$id')} != {expected['id']}")
            all_valid = False

        # Check schema_version in properties
        if "properties" in schema and "schema_version" in schema["properties"]:
            version_const = schema["properties"]["schema_version"].get("const")
            if version_const != expected["version"]:
                print(f"  ❌ Incorrect schema_version: {version_const} != {expected['version']}")
                all_valid = False

        # Check required fields
        if "required" in schema:
            missing_fields = set(expected["required_fields"]) - set(schema["required"])
            if missing_fields:
                print(f"  ❌ Missing required fields: {missing_fields}")
                all_valid = False

        # Check additionalProperties: false (red line)
        if schema.get("additionalProperties") is not False:
            print(f"  ⚠️  Warning: additionalProperties not set to false (frozen structure)")

        if all_valid:
            print(f"  ✅ Schema valid")

    print("\n" + "=" * 70)
    if all_valid:
        print("✅ Gate A: PASSED")
        print("=" * 70)
        return True
    else:
        print("❌ Gate A: FAILED")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
