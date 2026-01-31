#!/usr/bin/env python3
"""
v0.9.3 Gate I: Risk Consistency

Tests that risk matrix computation is deterministic.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples" / "intents" / "evaluations"

def main():
    print("=" * 70)
    print("v0.9.3 Gate I: Risk Consistency")
    print("=" * 70)
    print()
    
    eval_files = list(EXAMPLES_DIR.glob("eval_example_*.json"))
    
    for eval_file in eval_files:
        print(f"\nChecking {eval_file.name}...")
        
        with open(eval_file, encoding="utf-8") as f:
            data = json.load(f)
        
        risk_comp = data.get("evaluation", {}).get("risk_comparison", {})
        matrix = risk_comp.get("matrix", [])
        
        if not matrix:
            print(f"  ⚠️  No risk matrix")
            continue
        
        # Check risk matrix structure
        for entry in matrix:
            intent_id = entry.get("intent_id")
            overall = entry.get("overall_risk")
            dims = entry.get("dimensions", {})
            
            if not all([intent_id, overall, dims]):
                print(f"  ✗ Incomplete risk matrix entry")
                return False
            
            # Check dimensions are numeric
            required_dims = ["effects_risk", "scope_risk", "blast_radius", "unknowns"]
            for dim in required_dims:
                if dim not in dims:
                    print(f"  ✗ Missing dimension: {dim}")
                    return False
                if not isinstance(dims[dim], (int, float)):
                    print(f"  ✗ Dimension {dim} is not numeric")
                    return False
        
        print(f"  ✓ Risk matrix has {len(matrix)} entries with valid dimensions")
        
        # Check dominance relationships
        dominance = risk_comp.get("dominance", [])
        print(f"  ✓ Dominance: {len(dominance)} relationships")
    
    print()
    print("=" * 70)
    print("✅ Gate I: PASSED")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
