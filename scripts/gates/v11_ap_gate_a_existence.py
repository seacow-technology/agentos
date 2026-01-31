#!/usr/bin/env python3
"""
v11 AP Gate A: Existence Check

Validates that all required AnswerPack components exist:
- Schemas (answer_pack.schema.json, blockers.schema.json)
- Core modules (answer_store.py, answer_validator.py, answer_applier.py)
- CLI commands (answers.py, pipeline.py)
- Documentation
- Example fixtures
"""

import sys
from pathlib import Path

# Assume script is in scripts/gates/
PROJECT_ROOT = Path(__file__).parent.parent.parent
EXIT_CODE = 0


def check_file_exists(file_path: Path, description: str) -> bool:
    """Check if a file exists and report."""
    global EXIT_CODE
    if file_path.exists():
        print(f"✓ {description}: {file_path.relative_to(PROJECT_ROOT)}")
        return True
    else:
        print(f"✗ MISSING: {description}: {file_path.relative_to(PROJECT_ROOT)}")
        EXIT_CODE = 1
        return False


def main():
    global EXIT_CODE
    print("=" * 60)
    print("v11 AP Gate A: Existence Check")
    print("=" * 60)
    print()

    # 1. Schemas
    print("[1] Schemas")
    check_file_exists(
        PROJECT_ROOT / "agentos/schemas/execution/answer_pack.schema.json",
        "AnswerPack schema"
    )
    check_file_exists(
        PROJECT_ROOT / "agentos/schemas/execution/blockers.schema.json",
        "Blockers schema"
    )
    print()

    # 2. Core modules
    print("[2] Core Modules")
    check_file_exists(
        PROJECT_ROOT / "agentos/core/answers/__init__.py",
        "Answers module init"
    )
    check_file_exists(
        PROJECT_ROOT / "agentos/core/answers/answer_store.py",
        "AnswerStore"
    )
    check_file_exists(
        PROJECT_ROOT / "agentos/core/answers/answer_validator.py",
        "AnswerValidator"
    )
    check_file_exists(
        PROJECT_ROOT / "agentos/core/answers/answer_applier.py",
        "AnswerApplier"
    )
    print()

    # 3. CLI commands
    print("[3] CLI Commands")
    check_file_exists(
        PROJECT_ROOT / "agentos/cli/answers.py",
        "Answers CLI"
    )
    check_file_exists(
        PROJECT_ROOT / "agentos/cli/pipeline.py",
        "Pipeline CLI (with resume)"
    )
    print()

    # 4. Gates
    print("[4] Gates")
    check_file_exists(
        PROJECT_ROOT / "scripts/gates/v11_ap_gate_a_existence.py",
        "Gate A (this file)"
    )
    print()

    # 5. Fixtures
    print("[5] Fixtures")
    fixtures_dir = PROJECT_ROOT / "fixtures/answer_pack"
    if fixtures_dir.exists():
        print(f"✓ Fixtures directory: {fixtures_dir.relative_to(PROJECT_ROOT)}")
    else:
        print(f"✗ MISSING: Fixtures directory: {fixtures_dir.relative_to(PROJECT_ROOT)}")
        EXIT_CODE = 1
    print()

    # Summary
    print("=" * 60)
    if EXIT_CODE == 0:
        print("✓ AP GATE A PASSED: All required files exist")
    else:
        print("✗ AP GATE A FAILED: Some files are missing")
    print("=" * 60)

    return EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
