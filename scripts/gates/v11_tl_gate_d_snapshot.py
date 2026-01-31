#!/usr/bin/env python3
"""TL Gate D - 快照一致性"""
import sys, json
from pathlib import Path

EXIT_CODE, PROJECT_ROOT = 0, Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_pack_consistency():
    global EXIT_CODE
    from agentos.ext.tools import ClaudeCliAdapter
    
    adapter = ClaudeCliAdapter()
    exec_req = {"execution_request_id": "test_123", "execution_mode": "controlled"}
    repo_state = {"branch": "main", "commit_hash": "0"*40, "is_dirty": False}
    
    pack1 = adapter.pack(exec_req, repo_state)
    pack2 = adapter.pack(exec_req, repo_state)
    
    # 比较结构（忽略timestamps）
    keys1 = set(k for k in pack1.keys() if not k.endswith("_at"))
    keys2 = set(k for k in pack2.keys() if not k.endswith("_at"))
    
    if keys1 != keys2:
        print(f"✗ Pack structure differs")
        EXIT_CODE = 1
        return False
    
    print("✓ Pack structure consistent")
    return True

def main():
    global EXIT_CODE
    print("=" * 60 + "\nTL Gate D - Snapshot Consistency\n" + "=" * 60 + "\n")
    test_pack_consistency()
    print("\n" + "=" * 60)
    print("✅ TL Gate D: PASSED" if EXIT_CODE == 0 else "❌ TL Gate D: FAILED")
    print("=" * 60)
    return EXIT_CODE

if __name__ == "__main__":
    sys.exit(main())
