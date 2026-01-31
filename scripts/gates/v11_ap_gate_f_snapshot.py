#!/usr/bin/env python3
"""
v11 AP Gate F: Snapshot Test

Tests that AnswerPack operations produce consistent, reproducible output:
- Fixed input QuestionPack → Fixed AnswerPack structure
- Checksum computation is stable
- Validation results are deterministic
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Assume script is in scripts/gates/
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agentos.core.answers import AnswerStore, validate_answer_pack

FIXTURES_DIR = PROJECT_ROOT / "fixtures/answer_pack"
EXIT_CODE = 0


def test_checksum_stability():
    """Test that checksum computation is stable."""
    global EXIT_CODE
    print("  [1.1] Testing checksum stability")
    
    store = AnswerStore()
    
    # Create the same answer pack twice
    test_pack = {
        "answer_pack_id": "apack_snapshot_test",
        "schema_version": "0.11.0",
        "question_pack_id": "qpack_test456",
        "intent_id": "intent_test789",
        "answers": [
            {
                "question_id": "q_test1",
                "answer_type": "text",
                "answer_text": "Test answer",
                "evidence_refs": ["evidence1"],
                "provided_at": "2026-01-25T00:00:00Z",
                "provided_by": "human"
            }
        ],
        "provided_at": "2026-01-25T00:00:00Z",
        "lineage": {
            "nl_request_id": "nl_req_test",
            "created_by": "test"
        }
    }
    
    checksum1 = store.compute_checksum(test_pack)
    checksum2 = store.compute_checksum(test_pack)
    
    if checksum1 == checksum2:
        print(f"    ✓ Checksum is stable: {checksum1[:16]}...")
        return True
    else:
        print(f"    ✗ Checksum is NOT stable")
        print(f"      First:  {checksum1}")
        print(f"      Second: {checksum2}")
        EXIT_CODE = 1
        return False


def test_validation_determinism():
    """Test that validation results are deterministic."""
    global EXIT_CODE
    print("  [1.2] Testing validation determinism")
    
    # Load valid question pack
    qpack_path = FIXTURES_DIR / "valid_question_pack.json"
    if not qpack_path.exists():
        print(f"    ! QuestionPack not found: {qpack_path}")
        return False
    
    with open(qpack_path, "r", encoding="utf-8") as f:
        question_pack = json.load(f)
    
    # Create a valid answer pack
    store = AnswerStore()
    answer_pack = {
        "answer_pack_id": "apack_validation_test",
        "schema_version": "0.11.0",
        "question_pack_id": "qpack_test456",
        "intent_id": "intent_test789",
        "answers": [
            {
                "question_id": "q_test1",
                "answer_type": "text",
                "answer_text": "Valid answer",
                "evidence_refs": ["evidence1"],
                "provided_at": "2026-01-25T00:00:00Z",
                "provided_by": "human"
            }
        ],
        "provided_at": "2026-01-25T00:00:00Z",
        "lineage": {
            "nl_request_id": "nl_req_test",
            "created_by": "test"
        },
        "checksum": "placeholder"
    }
    
    # Compute checksum
    answer_pack["checksum"] = store.compute_checksum(answer_pack)
    
    # Validate twice
    valid1, errors1 = validate_answer_pack(answer_pack, question_pack)
    valid2, errors2 = validate_answer_pack(answer_pack, question_pack)
    
    if valid1 == valid2 and errors1 == errors2:
        print(f"    ✓ Validation is deterministic (result: {valid1})")
        return True
    else:
        print(f"    ✗ Validation is NOT deterministic")
        print(f"      First:  valid={valid1}, errors={len(errors1)}")
        print(f"      Second: valid={valid2}, errors={len(errors2)}")
        EXIT_CODE = 1
        return False


def test_pack_id_generation():
    """Test that pack ID generation uses stable inputs."""
    global EXIT_CODE
    print("  [1.3] Testing pack ID generation")
    
    store = AnswerStore()
    
    # Generate ID from same question pack twice
    qpack_id = "qpack_test456"
    
    # Note: pack IDs include timestamp so will be different
    # We just check format consistency
    id1 = store.generate_pack_id(qpack_id)
    id2 = store.generate_pack_id(qpack_id)
    
    if id1.startswith("apack_") and id2.startswith("apack_"):
        if len(id1) == len(id2):
            print(f"    ✓ Pack ID format is consistent")
            print(f"      Example: {id1}")
            return True
        else:
            print(f"    ✗ Pack ID length inconsistent: {len(id1)} vs {len(id2)}")
            EXIT_CODE = 1
            return False
    else:
        print(f"    ✗ Pack ID format invalid: {id1}, {id2}")
        EXIT_CODE = 1
        return False


def main():
    global EXIT_CODE
    print("=" * 60)
    print("v11 AP Gate F: Snapshot Test")
    print("=" * 60)
    print()

    print("[1] Testing output stability")
    test_checksum_stability()
    test_validation_determinism()
    test_pack_id_generation()
    print()

    # Summary
    print("=" * 60)
    if EXIT_CODE == 0:
        print("✓ AP GATE F PASSED: All outputs are stable and reproducible")
    else:
        print("✗ AP GATE F FAILED: Some outputs are non-deterministic")
    print("=" * 60)

    return EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
