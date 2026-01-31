#!/usr/bin/env python3
"""
EX Gate C - Executor 负向测试

测试Executor对违规行为的检测
"""

import sys
import json
from pathlib import Path

EXIT_CODE = 0
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_bypass_allowlist():
    """测试绕过allowlist的尝试"""
    global EXIT_CODE
    
    try:
        from agentos.core.executor import Allowlist
        
        allowlist = Allowlist()
        
        # 尝试执行不在allowlist中的操作
        malicious_ops = ["rm_rf", "curl", "wget", "arbitrary_shell"]
        
        for op in malicious_ops:
            if allowlist.is_allowed("file_operation", op):
                print(f"✗ Security: '{op}' should NOT be allowed")
                EXIT_CODE = 1
                return False
        
        print("✓ Bypass allowlist test: All malicious operations rejected")
        return True
        
    except Exception as e:
        print(f"✗ Bypass allowlist test failed: {e}")
        EXIT_CODE = 1
        return False


def test_path_escape():
    """测试路径逃逸检测"""
    global EXIT_CODE
    
    try:
        from agentos.core.executor import Sandbox
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "test_repo"
            repo_path.mkdir()
            
            sandbox = Sandbox(repo_path)
            
            # 测试路径逃逸
            malicious_paths = [
                Path("/etc/passwd"),
                Path("/tmp/evil"),
                Path(tmpdir) / "outside_repo",
            ]
            
            # 不创建worktree时，所有路径都应该返回False
            for path in malicious_paths:
                if sandbox.is_path_in_worktree(path):
                    print(f"✗ Security: Path '{path}' should NOT be in worktree")
                    EXIT_CODE = 1
                    return False
        
        print("✓ Path escape test: All malicious paths rejected")
        return True
        
    except Exception as e:
        print(f"✗ Path escape test failed: {e}")
        EXIT_CODE = 1
        return False


def test_concurrent_lock():
    """测试并发锁机制"""
    global EXIT_CODE
    
    try:
        from agentos.core.executor import ExecutionLock
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_dir = Path(tmpdir) / "locks"
            lock_dir.mkdir()
            
            lock1 = ExecutionLock(lock_dir)
            lock2 = ExecutionLock(lock_dir)
            
            # 第一个锁应该成功
            if not lock1.acquire("run_001", "repo_abc", ttl_seconds=60):
                print("✗ Lock: First acquire should succeed")
                EXIT_CODE = 1
                return False
            
            # 第二个锁应该失败（同一repo）
            if lock2.acquire("run_002", "repo_abc", ttl_seconds=60):
                print("✗ Lock: Second acquire should fail (concurrent execution)")
                EXIT_CODE = 1
                return False
            
            lock1.release()
        
        print("✓ Concurrent lock test: Concurrent execution blocked")
        return True
        
    except Exception as e:
        print(f"✗ Concurrent lock test failed: {e}")
        EXIT_CODE = 1
        return False


def test_review_gate():
    """测试审批门控"""
    global EXIT_CODE
    
    try:
        from agentos.core.executor import ReviewGate
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            approval_dir = Path(tmpdir) / "approvals"
            approval_dir.mkdir()
            
            gate = ReviewGate(approval_dir)
            
            # 测试未审批的执行请求
            exec_req = {
                "execution_request_id": "exec_req_001",
                "requires_review": True
            }
            
            if not gate.requires_review(exec_req):
                print("✗ Review Gate: Should require review")
                EXIT_CODE = 1
                return False
            
            # 检查未审批时的状态
            approval = gate.check_approval("exec_req_001")
            if approval is not None:
                print("✗ Review Gate: Should have no approval yet")
                EXIT_CODE = 1
                return False
        
        print("✓ Review gate test: Unapproved execution blocked")
        return True
        
    except Exception as e:
        print(f"✗ Review gate test failed: {e}")
        EXIT_CODE = 1
        return False


def test_audit_logging():
    """测试审计日志完整性"""
    global EXIT_CODE
    
    try:
        from agentos.core.executor import AuditLogger
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            run_tape = Path(tmpdir) / "run_tape.jsonl"
            
            logger = AuditLogger(run_tape)
            
            # 记录一些事件
            logger.log_operation_start("op_001", "file_write", {"file": "test.txt"})
            logger.log_operation_end("op_001", "success")
            
            # 验证日志文件存在
            if not run_tape.exists():
                print("✗ Audit: run_tape.jsonl not created")
                EXIT_CODE = 1
                return False
            
            # 验证日志内容
            events = logger.get_all_events()
            if len(events) != 2:
                print(f"✗ Audit: Expected 2 events, got {len(events)}")
                EXIT_CODE = 1
                return False
        
        print("✓ Audit logging test: All events recorded")
        return True
        
    except Exception as e:
        print(f"✗ Audit logging test failed: {e}")
        EXIT_CODE = 1
        return False


def main():
    global EXIT_CODE
    
    print("=" * 60)
    print("EX Gate C - Executor Negative Tests")
    print("=" * 60)
    print()
    
    tests = [
        ("Bypass Allowlist", test_bypass_allowlist),
        ("Path Escape", test_path_escape),
        ("Concurrent Lock", test_concurrent_lock),
        ("Review Gate", test_review_gate),
        ("Audit Logging", test_audit_logging),
    ]
    
    for test_name, test_func in tests:
        print(f"[{test_name}]")
        test_func()
        print()
    
    print("=" * 60)
    if EXIT_CODE == 0:
        print("✅ EX Gate C: ALL NEGATIVE TESTS PASSED")
    else:
        print("❌ EX Gate C: NEGATIVE TESTS FAILED")
    print("=" * 60)
    
    return EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
