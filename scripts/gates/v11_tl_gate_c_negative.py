#!/usr/bin/env python3
"""TL Gate C - 负向测试"""
import sys, tempfile
from pathlib import Path

EXIT_CODE, PROJECT_ROOT = 0, Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_adapter_verification():
    global EXIT_CODE
    from agentos.ext.tools import ClaudeCliAdapter
    
    adapter = ClaudeCliAdapter()
    
    # 测试失败的result pack
    failed_pack = {
        "status": "failed",
        "policy_attestation": {"scope_compliant": False, "red_lines_respected": False}
    }
    
    is_valid, errors = adapter.verify(failed_pack)
    if is_valid:
        print("✗ Should reject failed pack")
        EXIT_CODE = 1
        return False
    
    print("✓ Correctly rejected invalid result pack")
    return True

def main():
    global EXIT_CODE
    print("=" * 60 + "\nTL Gate C - Negative Tests\n" + "=" * 60 + "\n")
    print("[Adapter Verification]")
    test_adapter_verification()
    print("\n" + "=" * 60)
    print("✅ TL Gate C: PASSED" if EXIT_CODE == 0 else "❌ TL Gate C: FAILED")
    print("=" * 60)
    return EXIT_CODE

if __name__ == "__main__":
    sys.exit(main())
