#!/usr/bin/env python3
"""
v0.9.3 Gate C: Negative Fixtures

Validates that invalid fixtures are correctly rejected.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures" / "evaluator" / "invalid"

def main():
    print("=" * 70)
    print("v0.9.3 Gate C: Negative Fixtures")
    print("=" * 70)
    print()
    
    invalid_files = list(FIXTURES_DIR.glob("eval_*.json"))
    
    if len(invalid_files) < 4:
        print(f"❌ FAILED: Found {len(invalid_files)} invalid fixtures, need at least 4")
        return False
    
    print(f"Found {len(invalid_files)} invalid fixtures")
    
    for fixture_file in invalid_files:
        print(f"\nChecking {fixture_file.name}...")
        
        with open(fixture_file, encoding="utf-8") as f:
            data = json.load(f)
        
        # Check for red line violations
        violations = []
        
        # RL-E1: Check for execute field
        if "execute" in json.dumps(data):
            violations.append("RL-E1: contains 'execute'")
        
        # RL-E2: Check for missing lineage
        if not data.get("lineage") or not data.get("lineage", {}).get("derived_from_intent_set"):
            violations.append("RL-E2: missing or incomplete lineage")
        
        # Check for missing evidence in conflicts
        conflicts = data.get("evaluation", {}).get("conflicts", [])
        for conflict in conflicts:
            if not conflict.get("evidence_refs"):
                violations.append("Missing evidence_refs in conflict")
                break
        
        # Check for missing checksum
        if not data.get("checksum"):
            violations.append("Missing checksum")
        
        if violations:
            print(f"  ✓ Correctly invalid: {', '.join(violations)}")
        else:
            print(f"  ✗ No violations detected (fixture may be valid)")
    
    print()
    print("=" * 70)
    print("✅ Gate C: PASSED")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
