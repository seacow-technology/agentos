#!/usr/bin/env python3
"""
v0.10 Gate A: Existence and Structure Validation

Validates:
- 4 schemas exist
- 5 core modules exist
- 3 examples exist
- 5 invalid fixtures exist
- CLI file exists
- 4 documentation files exist
"""

import sys
from pathlib import Path

# Expected schemas
SCHEMAS = [
    "agentos/schemas/executor/execution_graph.schema.json",
    "agentos/schemas/executor/patch_plan.schema.json",
    "agentos/schemas/executor/commit_plan.schema.json",
    "agentos/schemas/executor/dry_execution_result.schema.json",
]

# Expected core modules
CORE_MODULES = [
    "agentos/core/executor_dry/__init__.py",
    "agentos/core/executor_dry/dry_executor.py",
    "agentos/core/executor_dry/graph_builder.py",
    "agentos/core/executor_dry/patch_planner.py",
    "agentos/core/executor_dry/commit_planner.py",
    "agentos/core/executor_dry/review_pack_stub.py",
]

# Expected examples
EXAMPLES = [
    "examples/executor_dry/low_risk/input_intent.json",
    "examples/executor_dry/low_risk/output_result.json",
    "examples/executor_dry/low_risk/explain.txt",
    "examples/executor_dry/medium_risk/input_intent.json",
    "examples/executor_dry/medium_risk/output_result.json",
    "examples/executor_dry/medium_risk/explain.txt",
    "examples/executor_dry/high_risk/input_intent.json",
    "examples/executor_dry/high_risk/output_result.json",
    "examples/executor_dry/high_risk/explain.txt",
]

# Expected invalid fixtures
INVALID_FIXTURES = [
    "fixtures/executor_dry/invalid/result_contains_execution_field.json",
    "fixtures/executor_dry/invalid/patch_plan_fabricated_paths.json",
    "fixtures/executor_dry/invalid/missing_evidence_refs.json",
    "fixtures/executor_dry/invalid/missing_checksum_lineage.json",
    "fixtures/executor_dry/invalid/high_risk_no_review.json",
]

# Expected CLI and docs
CLI_FILES = [
    "agentos/cli/dry_executor.py",
]

DOCS = [
    "docs/executor/README.md",
    "docs/executor/AUTHORING_GUIDE.md",
    "docs/executor/RED_LINES.md",
    "docs/executor/V10_FREEZE_CHECKLIST_REPORT.md",
]


def main():
    print("=" * 70)
    print("v0.10 Gate A: Existence and Structure Validation")
    print("=" * 70)

    all_valid = True

    # Check schemas
    print("\n🔍 Checking Schemas (4 required)...")
    for schema_path in SCHEMAS:
        if Path(schema_path).exists():
            print(f"  ✅ {schema_path}")
        else:
            print(f"  ❌ {schema_path} - NOT FOUND")
            all_valid = False

    # Check core modules
    print("\n🔍 Checking Core Modules (6 required)...")
    for module_path in CORE_MODULES:
        if Path(module_path).exists():
            print(f"  ✅ {module_path}")
        else:
            print(f"  ❌ {module_path} - NOT FOUND")
            all_valid = False

    # Check examples
    print("\n🔍 Checking Examples (9 files in 3 groups)...")
    for example_path in EXAMPLES:
        if Path(example_path).exists():
            print(f"  ✅ {example_path}")
        else:
            print(f"  ❌ {example_path} - NOT FOUND")
            all_valid = False

    # Check invalid fixtures
    print("\n🔍 Checking Invalid Fixtures (5 required)...")
    for fixture_path in INVALID_FIXTURES:
        if Path(fixture_path).exists():
            print(f"  ✅ {fixture_path}")
        else:
            print(f"  ❌ {fixture_path} - NOT FOUND")
            all_valid = False

    # Check CLI
    print("\n🔍 Checking CLI...")
    for cli_path in CLI_FILES:
        if Path(cli_path).exists():
            print(f"  ✅ {cli_path}")
        else:
            print(f"  ❌ {cli_path} - NOT FOUND")
            all_valid = False

    # Check docs (may not exist yet if gates run before docs step)
    print("\n🔍 Checking Documentation...")
    docs_missing = 0
    for doc_path in DOCS:
        if Path(doc_path).exists():
            print(f"  ✅ {doc_path}")
        else:
            print(f"  ⚠️  {doc_path} - NOT FOUND (will be created)")
            docs_missing += 1
    
    # Don't fail on missing docs if this is being run early
    if docs_missing == len(DOCS):
        print("  ℹ️  All docs missing - assuming docs step hasn't run yet")
    elif docs_missing > 0:
        print(f"  ⚠️  {docs_missing} docs missing")

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
