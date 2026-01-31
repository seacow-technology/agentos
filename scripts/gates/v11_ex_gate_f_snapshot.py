#!/usr/bin/env python3
"""
EX Gate F - 可复现快照测试

验证相同输入产生相同输出结构
"""

import sys
import json
from pathlib import Path
import tempfile

EXIT_CODE = 0
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_executor_determinism():
    """测试Executor的确定性行为"""
    global EXIT_CODE
    
    try:
        from agentos.core.executor import ExecutorEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # 创建测试repo
            repo_path = tmpdir / "test_repo"
            repo_path.mkdir()
            
            # 初始化git repo
            import subprocess
            subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, check=True, capture_output=True)
            
            # 创建初始commit
            (repo_path / "README.md").write_text("# Test")
            subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_path, check=True, capture_output=True)
            
            # 创建输出目录
            output_dir = tmpdir / "outputs"
            output_dir.mkdir()
            
            # 创建两个相同的execution request
            exec_request = {
                "execution_request_id": "exec_req_snapshot_test",
                "schema_version": "0.11.1",
                "execution_mode": "controlled",
                "allowed_operations": ["file_write"],
                "requires_review": False
            }
            
            sandbox_policy = {
                "policy_id": "test_policy",
                "allowlist": ["file_write"]
            }
            
            # 执行两次
            engine1 = ExecutorEngine(repo_path, output_dir / "run1")
            result1 = engine1.execute(exec_request, sandbox_policy)
            
            engine2 = ExecutorEngine(repo_path, output_dir / "run2")
            result2 = engine2.execute(exec_request, sandbox_policy)
            
            # 比较结果结构（不比较时间戳）
            keys1 = set(result1.keys())
            keys2 = set(result2.keys())
            
            if keys1 != keys2:
                print(f"✗ Result structure differs:")
                print(f"  Run1 keys: {keys1}")
                print(f"  Run2 keys: {keys2}")
                EXIT_CODE = 1
                return False
            
            # 验证status一致
            if result1["status"] != result2["status"]:
                print(f"✗ Status differs: {result1['status']} vs {result2['status']}")
                EXIT_CODE = 1
                return False
            
            print("✓ Executor determinism: Consistent results across runs")
            return True
            
    except Exception as e:
        print(f"✗ Determinism test failed: {e}")
        import traceback
        traceback.print_exc()
        EXIT_CODE = 1
        return False


def test_audit_log_structure():
    """测试审计日志结构稳定性"""
    global EXIT_CODE
    
    try:
        from agentos.core.executor import AuditLogger
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # 创建两个logger，记录相同事件
            log1_path = tmpdir / "log1.jsonl"
            log2_path = tmpdir / "log2.jsonl"
            
            logger1 = AuditLogger(log1_path)
            logger1.log_operation_start("op_001", "file_write", {"file": "test.txt"})
            logger1.log_operation_end("op_001", "success")
            
            logger2 = AuditLogger(log2_path)
            logger2.log_operation_start("op_001", "file_write", {"file": "test.txt"})
            logger2.log_operation_end("op_001", "success")
            
            # 读取并比较结构
            events1 = logger1.get_all_events()
            events2 = logger2.get_all_events()
            
            if len(events1) != len(events2):
                print(f"✗ Event count differs: {len(events1)} vs {len(events2)}")
                EXIT_CODE = 1
                return False
            
            # 比较事件结构（忽略timestamp）
            for e1, e2 in zip(events1, events2):
                keys1 = set(k for k in e1.keys() if k != "timestamp")
                keys2 = set(k for k in e2.keys() if k != "timestamp")
                
                if keys1 != keys2:
                    print(f"✗ Event structure differs")
                    EXIT_CODE = 1
                    return False
            
            print("✓ Audit log structure: Consistent across runs")
            return True
            
    except Exception as e:
        print(f"✗ Audit log structure test failed: {e}")
        EXIT_CODE = 1
        return False


def main():
    global EXIT_CODE
    
    print("=" * 60)
    print("EX Gate F - Reproducibility Snapshot Tests")
    print("=" * 60)
    print()
    
    print("[Executor Determinism]")
    test_executor_determinism()
    print()
    
    print("[Audit Log Structure]")
    test_audit_log_structure()
    print()
    
    print("=" * 60)
    if EXIT_CODE == 0:
        print("✅ EX Gate F: REPRODUCIBILITY VERIFIED")
    else:
        print("❌ EX Gate F: REPRODUCIBILITY FAILED")
    print("=" * 60)
    
    return EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
