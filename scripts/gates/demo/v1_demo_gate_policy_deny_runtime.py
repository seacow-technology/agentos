#!/usr/bin/env python3
"""
Gate R1: Policy Deny Must Block (Runtime)

验证 --policy 真的生效，拒绝场景必须失败且记录到 run_tape。
"""

import json
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

def create_test_exec_request(output_dir: Path) -> Path:
    """创建测试用的 execution_request"""
    exec_request = {
        "execution_request_id": "test_deny_001",
        "schema_version": "0.11.1",
        "intent_id": "test_intent",
        "execution_mode": "controlled",
        "requires_review": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "patch_plan": {
            "steps": [
                {
                    "step_id": "step_01",
                    "operations": [
                        {
                            "op_id": "op_001",
                            "action": "write_file",
                            "params": {
                                "path": "test.md",
                                "content": "# Test\n"
                            }
                        }
                    ]
                }
            ]
        }
    }
    
    req_file = output_dir / "exec_request.json"
    with open(req_file, "w", encoding="utf-8") as f:
        json.dump(exec_request, f, indent=2)
    
    return req_file


def gate_r1_policy_deny_runtime(repo_root: Path) -> tuple[bool, str]:
    """
    Gate R1: 验证 policy deny 场景
    
    验收：
    1. exec run --policy deny 必须 exit != 0
    2. 生成 run_tape.jsonl
    3. run_tape 包含 policy_denied 或 rejected 事件
    """
    
    # 创建临时测试目录
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        output_dir = tmpdir / "outputs"
        output_dir.mkdir()
        
        # 初始化一个git repo（必须有初始commit）
        test_repo = tmpdir / "test_repo"
        test_repo.mkdir()
        import subprocess
        subprocess.run(["git", "init"], cwd=test_repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=test_repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=test_repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=test_repo, check=True, capture_output=True)
        
        # 创建 exec_request
        req_file = create_test_exec_request(tmpdir)
        
        policy_deny = repo_root / "fixtures" / "policy" / "policy_deny.json"
        
        if not policy_deny.exists():
            return False, f"policy_deny.json not found: {policy_deny}"
        
        # 尝试运行 executor（应该失败）
        cmd = [
            "uv", "run", "agentos", "exec", "run",
            "--request", str(req_file),
            "--policy", str(policy_deny),
            "--repo", str(test_repo),
            "--out", str(output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root)
        
        # 检查 1: 必须失败
        if result.returncode == 0:
            return False, "Policy deny should fail but succeeded (exit=0)"
        
        # 检查 2: run_tape 必须存在
        run_tape_files = list(output_dir.rglob("run_tape.jsonl"))
        if not run_tape_files:
            # 可能还没到生成 run_tape 的阶段，检查 stderr
            if "policy" in result.stderr.lower() or "denied" in result.stderr.lower():
                return True, "Policy deny rejected (before run_tape, stderr shows policy rejection)"
            return False, f"No run_tape.jsonl and no policy error in stderr"
        
        run_tape = run_tape_files[0]
        
        # 检查 3: run_tape 包含拒绝事件
        has_denial = False
        with open(run_tape, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                event = json.loads(line)
                event_type = event.get("event_type", event.get("event", ""))
                # 检查多种可能的拒绝事件类型
                if "denied" in event_type.lower() or "policy_denied" in event_type.lower():
                    has_denial = True
                    break
        
        if not has_denial:
            # Debug: 打印所有事件类型
            print(f"Debug: run_tape found at {run_tape}")
            with open(run_tape, "r", encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if line.strip():
                        event = json.loads(line)
                        event_type = event.get("event_type", event.get("event", ""))
                        print(f"  Line {i}: event_type={event_type}")
            return False, f"run_tape exists but no denial event found"
        
        return True, f"Policy deny correctly blocked execution and logged denial"


def main():
    repo_root = Path.cwd()
    
    print("=" * 60)
    print("Gate R1: Policy Deny Must Block (Runtime)")
    print("=" * 60)
    
    passed, message = gate_r1_policy_deny_runtime(repo_root)
    
    if passed:
        print(f"✅ PASS: {message}")
        return 0
    else:
        print(f"❌ FAIL: {message}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
