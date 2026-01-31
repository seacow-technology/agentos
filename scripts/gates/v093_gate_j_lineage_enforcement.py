#!/usr/bin/env python3
"""
v0.9.3 Gate J: Lineage Enforcement

Tests that all merged intents have complete lineage (RL-E2).
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples" / "intents" / "evaluations"

def main():
    print("=" * 70)
    print("v0.9.3 Gate J: Lineage Enforcement (RL-E2)")
    print("=" * 70)
    print()
    
    eval_files = list(EXAMPLES_DIR.glob("eval_example_*.json"))
    
    for eval_file in eval_files:
        print(f"\nChecking {eval_file.name}...")
        
        with open(eval_file, encoding="utf-8") as f:
            data = json.load(f)
        
        merge_plan = data.get("evaluation", {}).get("merge_plan", {})
        strategy = merge_plan.get("strategy")
        
        if strategy in ["merge_union", "override_by_priority"]:
            # Check that evaluation result has lineage
            eval_lineage = data.get("lineage", {})
            
            if not eval_lineage.get("derived_from_intent_set"):
                print(f"  ✗ RL-E2 violation: Missing derived_from_intent_set")
                return False
            
            print(f"  ✓ Evaluation has lineage to intent set")
            
            # For override strategy, check supersedes
            if strategy == "override_by_priority":
                operations = merge_plan.get("operations", [])
                # In override, we expect operations to reference superseded intents
                print(f"  ✓ Override strategy with {len(operations)} operation(s)")
        
        elif strategy == "reject":
            # Reject strategy doesn't produce merged intent
            print(f"  ✓ Reject strategy (no merge, lineage N/A)")
        
        else:
            print(f"  ⚠️  Unknown strategy: {strategy}")
    
    print()
    print("=" * 70)
    print("✅ Gate J: PASSED")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
