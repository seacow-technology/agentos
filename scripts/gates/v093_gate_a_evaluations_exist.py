#!/usr/bin/env python3
"""
v0.9.3 Gate A: Evaluations Exist

Checks:
- At least 3 example evaluation results exist
- IDs are unique
- Naming follows convention
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples" / "intents" / "evaluations"

def main():
    print("=" * 70)
    print("v0.9.3 Gate A: Evaluations Exist")
    print("=" * 70)
    print()
    
    # Find evaluation result files
    eval_files = list(EXAMPLES_DIR.glob("eval_example_*.json"))
    
    if len(eval_files) < 3:
        print(f"❌ FAILED: Found {len(eval_files)} evaluation examples, need at least 3")
        return False
    
    print(f"✅ Found {len(eval_files)} evaluation examples")
    
    # Check IDs are unique
    ids = set()
    for eval_file in eval_files:
        with open(eval_file, encoding="utf-8") as f:
            data = json.load(f)
            eval_id = data.get("id", "")
            
            if eval_id in ids:
                print(f"❌ FAILED: Duplicate ID {eval_id}")
                return False
            
            ids.add(eval_id)
            print(f"  ✓ {eval_id}")
    
    print()
    print("=" * 70)
    print("✅ Gate A: PASSED")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
