#!/usr/bin/env python3
"""
v0.9.2 Gate B: Schema Batch Validation

Validates:
- All example outputs conform to their schemas
- Lineage完整 (关联到 intent + registry versions)
- Checksums present
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
EXAMPLES_DIR = Path("examples/coordinator/outputs")

VALIDATIONS = [
    {
        "schema": "execution_graph.schema.json",
        "examples": [
            "execution_graph_low_risk.json",
            "execution_graph_high_risk_interactive.json",
            "execution_graph_full_auto_readonly.json"
        ]
    },
    {
        "schema": "question_pack.schema.json",
        "examples": [
            "question_pack_high_risk_interactive.json"
        ]
    },
    {
        "schema": "coordinator_run_tape.schema.json",
        "examples": [
            "coordinator_run_tape_low_risk.json",
            "coordinator_run_tape_high_risk_interactive.json",
            "coordinator_run_tape_full_auto_readonly.json"
        ]
    }
]


def main():
    print("=" * 70)
    print("v0.9.2 Gate B: Schema Batch Validation")
    print("=" * 70)

    all_valid = True

    for validation in VALIDATIONS:
        schema_path = SCHEMA_DIR / validation["schema"]
        
        if not schema_path.exists():
            print(f"\n❌ Schema not found: {schema_path}")
            all_valid = False
            continue

        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        for example_file in validation["examples"]:
            example_path = EXAMPLES_DIR / example_file
            print(f"\nValidating {example_file} against {validation['schema']}...")

            if not example_path.exists():
                print(f"  ❌ Example not found")
                all_valid = False
                continue

            try:
                with open(example_path, "r", encoding="utf-8") as f:
                    example = json.load(f)
            except json.JSONDecodeError as e:
                print(f"  ❌ Invalid JSON: {e}")
                all_valid = False
                continue

            # Schema validation
            try:
                validate(instance=example, schema=schema)
                print(f"  ✅ Schema validation passed")
            except ValidationError as e:
                print(f"  ❌ Schema validation failed: {e.message}")
                all_valid = False
                continue

            # Lineage check (for execution_graph)
            if "lineage" in example:
                lineage = example["lineage"]
                if "derived_from_intent" not in lineage:
                    print(f"  ❌ Missing derived_from_intent in lineage")
                    all_valid = False
                if "registry_versions" not in lineage:
                    print(f"  ❌ Missing registry_versions in lineage")
                    all_valid = False
                else:
                    print(f"  ✅ Lineage complete")

            # Checksum check
            if "checksum" in example:
                checksum = example["checksum"]
                if not checksum or len(checksum) != 64:
                    print(f"  ❌ Invalid checksum (must be 64-char SHA-256)")
                    all_valid = False
                else:
                    print(f"  ✅ Checksum present")

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
