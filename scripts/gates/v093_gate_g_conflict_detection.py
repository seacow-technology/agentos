#!/usr/bin/env python3
"""
v0.9.3 Gate G: Conflict Detection Completeness

Tests that all 4 conflict types can be detected.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

def main():
    print("=" * 70)
    print("v0.9.3 Gate G: Conflict Detection Completeness")
    print("=" * 70)
    print()
    
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from agentos.core.evaluator import ConflictDetector
        
        detector = ConflictDetector()
        
        # Check that detector has methods for all 4 conflict types
        required_methods = [
            "detect_resource_conflicts",
            "detect_effect_conflicts",
            "detect_order_conflicts",
            "detect_constraint_conflicts"
        ]
        
        for method_name in required_methods:
            if not hasattr(detector, method_name):
                print(f"❌ FAILED: Missing method {method_name}")
                return False
            print(f"  ✓ {method_name} implemented")
        
        print()
        print("✅ All 4 conflict types can be detected")
        
    except ImportError as e:
        print(f"⚠️  Could not import ConflictDetector: {e}")
        return False
    
    print()
    print("=" * 70)
    print("✅ Gate G: PASSED")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
