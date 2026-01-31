#!/usr/bin/env python3
"""
EX Gate G - 锁验证（并发执行拒绝）

验证并发执行会被正确拒绝
"""

import sys
from pathlib import Path
import tempfile

EXIT_CODE = 0
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_concurrent_execution_blocked():
    """测试并发执行被阻止"""
    global EXIT_CODE
    
    try:
        from agentos.core.executor import ExecutionLock
        
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_dir = Path(tmpdir) / "locks"
            lock_dir.mkdir()
            
            lock1 = ExecutionLock(lock_dir)
            lock2 = ExecutionLock(lock_dir)
            
            repo_hash = "test_repo_abc"
            
            # 第一个锁获取成功
            acquired1 = lock1.acquire("run_001", repo_hash, ttl_seconds=60)
            if not acquired1:
                print("✗ First lock acquire failed")
                EXIT_CODE = 1
                return False
            
            print("✓ First lock acquired: run_001")
            
            # 第二个锁应该失败
            acquired2 = lock2.acquire("run_002", repo_hash, ttl_seconds=60)
            if acquired2:
                print("✗ Second lock should be REJECTED (concurrent execution)")
                EXIT_CODE = 1
                return False
            
            print("✓ Second lock REJECTED: run_002 (concurrent execution blocked)")
            
            # 释放第一个锁
            lock1.release()
            print("✓ First lock released")
            
            # 现在第二个锁应该成功
            acquired3 = lock2.acquire("run_003", repo_hash, ttl_seconds=60)
            if not acquired3:
                print("✗ Third lock acquire failed after first released")
                EXIT_CODE = 1
                return False
            
            print("✓ Third lock acquired after release: run_003")
            lock2.release()
            
            return True
            
    except Exception as e:
        print(f"✗ Concurrent execution test failed: {e}")
        import traceback
        traceback.print_exc()
        EXIT_CODE = 1
        return False


def main():
    global EXIT_CODE
    
    print("=" * 60)
    print("EX Gate G - Lock Verification (Concurrent Rejection)")
    print("=" * 60)
    print()
    
    print("[Concurrent Execution Blocking]")
    test_concurrent_execution_blocked()
    print()
    
    print("=" * 60)
    if EXIT_CODE == 0:
        print("✅ EX Gate G: CONCURRENT EXECUTION BLOCKED")
    else:
        print("❌ EX Gate G: LOCK VERIFICATION FAILED")
    print("=" * 60)
    
    return EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
