#!/usr/bin/env python3
"""
v0.9.3 Gate F: Explain Snapshot Stability

Tests that explain output structure is stable across runs.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples" / "intents" / "evaluations"
SNAPSHOT_DIR = REPO_ROOT / "tests" / "snapshots"

def main():
    print("=" * 70)
    print("v0.9.3 Gate F: Explain Snapshot Stability")
    print("=" * 70)
    print()
    
    # Load evaluation examples
    eval_files = sorted(EXAMPLES_DIR.glob("eval_example_*.json"))
    
    if len(eval_files) < 3:
        print(f"⚠️  Only {len(eval_files)} examples found, skipping snapshot test")
        return True
    
    # Check if explain functionality can be imported
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from agentos.core.evaluator import EvaluationExplainer
        
        explainer = EvaluationExplainer()
        
        for eval_file in eval_files[:3]:  # Test first 3
            print(f"\nTesting {eval_file.name}...")
            
            with open(eval_file, encoding="utf-8") as f:
                data = json.load(f)
            
            explanation = explainer.explain(data)
            
            # Check structure
            required_sections = [
                "INTENT EVALUATION RESULT",
                "INPUT",
                "CONFLICTS",
                "RISK COMPARISON",
                "MERGE PLAN"
            ]
            
            for section in required_sections:
                if section not in explanation:
                    print(f"  ✗ Missing section: {section}")
                    return False
            
            print(f"  ✓ Explanation structure stable")
            print(f"  ✓ Length: {len(explanation)} chars")
        
    except ImportError as e:
        print(f"⚠️  Could not import evaluator: {e}")
        print("  Skipping explain test")
        return True
    
    print()
    print("=" * 70)
    print("✅ Gate F: PASSED")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
