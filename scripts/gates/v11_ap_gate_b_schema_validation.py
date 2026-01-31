#!/usr/bin/env python3
"""
v11 AP Gate B: Schema Validation

Validates all AnswerPack-related JSON schemas:
- Load and parse schemas without errors
- Validate schema structure using jsonschema metaschema
- Check $ref resolution
- Test against valid fixtures
"""

import sys
import json
from pathlib import Path
import jsonschema

# Assume script is in scripts/gates/
PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "agentos/schemas/execution"
EXIT_CODE = 0


def validate_schema_structure(schema_path: Path) -> bool:
    """Validate that a schema is well-formed."""
    global EXIT_CODE
    
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        
        # Validate against JSON Schema metaschema
        jsonschema.Draft202012Validator.check_schema(schema)
        
        print(f"  ✓ {schema_path.name}: Valid schema structure")
        return True
        
    except json.JSONDecodeError as e:
        print(f"  ✗ {schema_path.name}: JSON parse error - {e}")
        EXIT_CODE = 1
        return False
    except jsonschema.SchemaError as e:
        print(f"  ✗ {schema_path.name}: Invalid schema - {e}")
        EXIT_CODE = 1
        return False
    except Exception as e:
        print(f"  ✗ {schema_path.name}: Unexpected error - {e}")
        EXIT_CODE = 1
        return False


def test_schema_validation(schema_path: Path, valid_example: dict) -> bool:
    """Test schema against a valid example."""
    global EXIT_CODE
    
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        
        jsonschema.validate(valid_example, schema)
        print(f"  ✓ {schema_path.name}: Example validates correctly")
        return True
        
    except jsonschema.ValidationError as e:
        print(f"  ✗ {schema_path.name}: Valid example failed validation - {e.message}")
        EXIT_CODE = 1
        return False
    except Exception as e:
        print(f"  ✗ {schema_path.name}: Unexpected error - {e}")
        EXIT_CODE = 1
        return False


def main():
    print("=" * 60)
    print("v11 AP Gate B: Schema Validation")
    print("=" * 60)
    print()

    # 1. Validate schema structures
    print("[1] Schema Structure Validation")
    
    answer_pack_schema = SCHEMAS_DIR / "answer_pack.schema.json"
    blockers_schema = SCHEMAS_DIR / "blockers.schema.json"
    
    validate_schema_structure(answer_pack_schema)
    validate_schema_structure(blockers_schema)
    print()

    # 2. Test with minimal valid examples
    print("[2] Example Validation Tests")
    
    # Minimal valid AnswerPack
    valid_answer_pack = {
        "answer_pack_id": "apack_test123",
        "schema_version": "0.11.0",
        "question_pack_id": "qpack_test456",
        "intent_id": "intent_test789",
        "answers": [
            {
                "question_id": "q_test1",
                "answer_type": "text",
                "answer_text": "Test answer",
                "evidence_refs": ["test_evidence"],
                "provided_at": "2026-01-25T00:00:00Z",
                "provided_by": "human"
            }
        ],
        "provided_at": "2026-01-25T00:00:00Z",
        "lineage": {
            "nl_request_id": "nl_req_test_123456",
            "created_by": "test"
        },
        "checksum": "0" * 64
    }
    
    test_schema_validation(answer_pack_schema, valid_answer_pack)
    
    # Minimal valid Blockers
    valid_blockers = {
        "blocker_id": "blocker_test123",
        "schema_version": "0.11.0",
        "pipeline_run_id": "run_test456",
        "intent_id": "intent_test789",
        "reason": "question_pack_non_empty",
        "question_pack_ref": {
            "pack_id": "qpack_test456",
            "path": "01_intent/question_pack.json"
        },
        "blocked_at": "2026-01-25T00:00:00Z",
        "resolution_steps": [
            {
                "step_number": 1,
                "action": "Create answer pack",
                "command": "agentos answers create ..."
            }
        ],
        "lineage": {
            "nl_request_id": "nl_req_test_123456"
        }
    }
    
    test_schema_validation(blockers_schema, valid_blockers)
    print()

    # Summary
    print("=" * 60)
    if EXIT_CODE == 0:
        print("✓ AP GATE B PASSED: All schemas are valid")
    else:
        print("✗ AP GATE B FAILED: Some schemas have issues")
    print("=" * 60)

    return EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
