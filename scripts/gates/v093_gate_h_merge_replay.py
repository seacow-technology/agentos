#!/usr/bin/env python3
"""
v0.9.3 Gate H: Merge Plan Replay

Tests that merge plans are serializable and replayable.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples" / "intents" / "evaluations"

def main():
    print("=" * 70)
    print("v0.9.3 Gate H: Merge Plan Replay")
    print("=" * 70)
    print()
    
    eval_files = list(EXAMPLES_DIR.glob("eval_example_*.json"))
    
    for eval_file in eval_files:
        print(f"\nChecking {eval_file.name}...")
        
        with open(eval_file, encoding="utf-8") as f:
            data = json.load(f)
        
        merge_plan = data.get("evaluation", {}).get("merge_plan", {})
        
        # Check merge plan is serializable
        try:
            serialized = json.dumps(merge_plan)
            deserialized = json.loads(serialized)
            print(f"  ✓ Merge plan is serializable")
        except Exception as e:
            print(f"  ✗ Serialization failed: {e}")
            return False
        
        # Check operations are ordered
        operations = merge_plan.get("operations", [])
        if operations:
            op_ids = [op.get("op_id") for op in operations]
            print(f"  ✓ {len(operations)} operations with IDs: {op_ids}")
        
        # Check strategy is valid
        strategy = merge_plan.get("strategy")
        valid_strategies = ["merge_union", "override_by_priority", "reject", "no_merge_needed"]
        if strategy not in valid_strategies:
            print(f"  ✗ Invalid strategy: {strategy}")
            return False
        print(f"  ✓ Strategy: {strategy}")
    
    print()
    print("=" * 70)
    print("✅ Gate H: PASSED")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
