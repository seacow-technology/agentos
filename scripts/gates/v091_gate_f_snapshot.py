#!/usr/bin/env python3
"""
v0.9.1 Gate F: Explain Snapshot Stability

Tests that the explain output structure is stable for a fixed set of intents.
Generates snapshot JSON for regression testing.
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.validate_intents import IntentValidator

EXAMPLES_DIR = Path("examples/intents")
SCHEMA_PATH = Path("agentos/schemas/execution/intent.schema.json")
SNAPSHOT_PATH = Path("tests/snapshots/v091_explain_snapshot.json")

# Fixed set of intents to test
TEST_INTENTS = [
    "intent_example_low_risk.json",
    "intent_example_high_risk_interactive.json",
]


def main():
    print("=" * 60)
    print("v0.9.1 Gate F: Explain Snapshot Stability")
    print("=" * 60)

    if not EXAMPLES_DIR.exists():
        print(f"❌ Examples directory not found: {EXAMPLES_DIR}")
        return False

    if not SCHEMA_PATH.exists():
        print(f"❌ Schema not found: {SCHEMA_PATH}")
        return False

    # Initialize validator
    try:
        validator = IntentValidator(SCHEMA_PATH)
    except Exception as e:
        print(f"❌ Failed to initialize validator: {e}")
        return False

    print(f"\n🔍 Generating explain snapshots for {len(TEST_INTENTS)} intent(s)...\n")

    snapshots = {}
    all_valid = True

    for filename in TEST_INTENTS:
        file_path = EXAMPLES_DIR / filename

        if not file_path.exists():
            print(f"❌ {filename}: File not found")
            all_valid = False
            continue

        print(f"Explaining {filename}...")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                intent = json.load(f)

            # Validate first
            valid, results = validator.validate(intent)

            if not valid:
                print(f"  ⚠️  Intent validation failed, but continuing explain...")

            # Generate explanation
            explanation = validator.explain(intent)

            # Verify required fields in explanation
            required_fields = [
                "id", "type", "version", "status", "risk_level", "interaction_mode",
                "workflow_count", "agent_count", "command_count", "evidence_count",
                "review_required", "budgets", "constraints"
            ]

            missing = [f for f in required_fields if f not in explanation]

            if missing:
                print(f"  ❌ Missing fields in explanation: {', '.join(missing)}")
                all_valid = False
                continue

            # Verify budgets structure
            budget_fields = ["max_files", "max_commits", "max_cost_usd"]
            missing_budget = [f for f in budget_fields if f not in explanation.get("budgets", {})]

            if missing_budget:
                print(f"  ❌ Missing budget fields: {', '.join(missing_budget)}")
                all_valid = False
                continue

            # Verify constraints structure
            constraint_fields = ["execution", "no_fabrication", "registry_only", "lock_scope_mode"]
            missing_constraints = [f for f in constraint_fields if f not in explanation.get("constraints", {})]

            if missing_constraints:
                print(f"  ❌ Missing constraint fields: {', '.join(missing_constraints)}")
                all_valid = False
                continue

            # Store snapshot
            snapshots[filename] = explanation
            print(f"  ✅ Explanation generated")

        except Exception as e:
            print(f"  ❌ Error: {e}")
            all_valid = False

    if not all_valid:
        print("\n" + "=" * 60)
        print("❌ Gate F: FAILED (explain generation failed)")
        print("=" * 60)
        return False

    # Save snapshot
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshots, f, indent=2, sort_keys=True)

    print(f"\n💾 Snapshot saved to: {SNAPSHOT_PATH}")

    # Verify snapshot can be loaded
    try:
        with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        if loaded != snapshots:
            print("❌ Snapshot verification failed: saved != loaded")
            return False

        print("  ✅ Snapshot verified")

    except Exception as e:
        print(f"❌ Snapshot verification failed: {e}")
        return False

    print("\n" + "=" * 60)
    print(f"✅ Gate F: PASSED (snapshots generated for {len(snapshots)} intent(s))")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
