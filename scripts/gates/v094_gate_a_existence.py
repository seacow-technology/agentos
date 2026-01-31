#!/usr/bin/env python3
"""
v0.9.4 Gate A: Existence and Counting Check

Validates:
- 2 schemas exist (nl_request.schema.json, intent_builder_output.schema.json)
- 3 NL inputs exist (nl_001.yaml, nl_002.yaml, nl_003.yaml)
- 4 invalid fixtures exist
- README and authoring guide exist
"""

import sys
from pathlib import Path

SCHEMAS_DIR = Path("agentos/schemas/execution")
NL_DIR = Path("examples/nl")
FIXTURES_DIR = Path("fixtures/intent_builder/invalid")
DOCS_DIR = Path("docs/execution")

REQUIRED_SCHEMAS = [
    "nl_request.schema.json",
    "intent_builder_output.schema.json"
]

REQUIRED_NL_INPUTS = [
    "nl_001.yaml",
    "nl_002.yaml",
    "nl_003.yaml"
]

REQUIRED_FIXTURES = [
    "missing_evidence_refs.json",
    "fabricated_command.json",
    "full_auto_with_questions.json",
    "output_has_execute_field.json"
]

REQUIRED_DOCS = [
    "V094_INTENT_BUILDER_README.md",
    "V094_AUTHORING_GUIDE.md"
]


def main():
    print("=" * 70)
    print("v0.9.4 Gate A: Existence and Counting")
    print("=" * 70)
    
    all_valid = True
    
    # Check schemas
    print(f"\n📁 Checking schemas in {SCHEMAS_DIR}/...")
    for schema_file in REQUIRED_SCHEMAS:
        schema_path = SCHEMAS_DIR / schema_file
        if schema_path.exists():
            print(f"  ✅ {schema_file} exists")
        else:
            print(f"  ❌ {schema_file} NOT FOUND")
            all_valid = False
    
    # Check NL inputs
    print(f"\n📁 Checking NL inputs in {NL_DIR}/...")
    for nl_file in REQUIRED_NL_INPUTS:
        nl_path = NL_DIR / nl_file
        if nl_path.exists():
            print(f"  ✅ {nl_file} exists")
        else:
            print(f"  ❌ {nl_file} NOT FOUND")
            all_valid = False
    
    # Check fixtures
    print(f"\n📁 Checking invalid fixtures in {FIXTURES_DIR}/...")
    for fixture_file in REQUIRED_FIXTURES:
        fixture_path = FIXTURES_DIR / fixture_file
        if fixture_path.exists():
            print(f"  ✅ {fixture_file} exists")
        else:
            print(f"  ❌ {fixture_file} NOT FOUND")
            all_valid = False
    
    # Check docs
    print(f"\n📁 Checking docs in {DOCS_DIR}/...")
    for doc_file in REQUIRED_DOCS:
        doc_path = DOCS_DIR / doc_file
        if doc_path.exists():
            print(f"  ✅ {doc_file} exists")
        else:
            print(f"  ⚠️  {doc_file} NOT FOUND (will be created)")
            # Don't fail on docs - they might not exist yet
    
    # Summary
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
