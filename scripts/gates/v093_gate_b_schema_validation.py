#!/usr/bin/env python3
"""
v0.9.3 Gate B: Schema Validation

Validates all evaluation examples against schemas.
"""

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("⚠️  jsonschema not installed, skipping schema validation")
    sys.exit(0)

REPO_ROOT = Path(__file__).parent.parent.parent
SCHEMAS_DIR = REPO_ROOT / "agentos" / "schemas" / "evaluator"
EXAMPLES_DIR = REPO_ROOT / "examples" / "intents" / "evaluations"

def main():
    print("=" * 70)
    print("v0.9.3 Gate B: Schema Validation")
    print("=" * 70)
    print()
    
    # Load schemas
    schemas = {}
    for schema_file in SCHEMAS_DIR.glob("*.schema.json"):
        with open(schema_file, encoding="utf-8") as f:
            schema_name = schema_file.stem.replace(".schema", "")
            schemas[schema_name] = json.load(f)
    
    print(f"Loaded {len(schemas)} schemas")
    
    # Validate evaluation examples
    eval_files = list(EXAMPLES_DIR.glob("eval_example_*.json"))
    
    for eval_file in eval_files:
        print(f"\nValidating {eval_file.name}...")
        
        with open(eval_file, encoding="utf-8") as f:
            data = json.load(f)
        
        schema_type = data.get("type", "")
        
        if schema_type == "intent_evaluation_result":
            schema = schemas.get("intent_evaluation_result")
            if schema:
                try:
                    jsonschema.validate(data, schema)
                    print(f"  ✓ Schema valid")
                except jsonschema.ValidationError as e:
                    print(f"  ✗ Schema invalid: {e.message}")
                    return False
        
        # Check lineage
        lineage = data.get("lineage", {})
        if not lineage.get("derived_from_intent_set"):
            print(f"  ✗ Missing lineage.derived_from_intent_set")
            return False
        print(f"  ✓ Lineage complete")
        
        # Check checksum exists
        if not data.get("checksum"):
            print(f"  ✗ Missing checksum")
            return False
        print(f"  ✓ Checksum present")
    
    print()
    print("=" * 70)
    print("✅ Gate B: PASSED")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
