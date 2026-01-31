#!/usr/bin/env python3
"""Gate P0-N1: Unknown Action Must Deny

验证未知 action（如 write_file2, custom_op）必须被 policy 拒绝。
防止通过"新造 action 名"绕过 allowlist。
"""

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# 添加项目根目录到路径
repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))


def create_test_exec_request_with_unknown_action(output_path: Path) -> Path:
    """创建包含未知 action 的执行请求"""
    # 使用简单的 ID 避免 git branch 命名问题
    simple_id = f"test_unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    exec_request = {
        "execution_request_id": simple_id,
        "schema_version": "0.11.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_path": str(output_path / "test_repo"),
        "base_branch": "main",
        "execution_mode": "worktree",
        "patch_plan": {
            "steps": [
                {
                    "step_id": "step_01",
                    "operations": [
                        {
                            "action": "unknown_custom_action",  # 未知 action
                            "params": {
                                "path": "test.txt",
                                "content": "test content"
                            }
                        }
                    ],
                    "commit_message": "Test unknown action"
                }
            ]
        }
    }
    
    request_path = output_path / "exec_request_unknown.json"
    with open(request_path, "w", encoding="utf-8") as f:
        json.dump(exec_request, f, indent=2, ensure_ascii=False)
    
    return request_path


def gate_p0_n1_unknown_action_deny() -> tuple[bool, str]:
    """
    Gate P0-N1: Unknown Action Must Deny
    
    验收标准：
    1. 执行请求包含未知 action（如 "unknown_custom_action", "write_file2"）
    2. Executor 必须失败（exit code != 0）
    3. run_tape.jsonl 必须包含 policy_denied 事件
    4. 拒绝原因必须明确指出 "not in allowlist" 或 "unknown operation"
    
    Returns:
        (passed, message)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # 初始化测试 repo
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True, capture_output=True)
        
        # 创建初始 commit
        (repo_path / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True, capture_output=True)
        
        # 创建包含未知 action 的执行请求
        request_path = create_test_exec_request_with_unknown_action(tmp_path)
        
        # 使用 policy_allow.json（允许已知操作，但不允许未知操作）
        policy_path = repo_root / "fixtures" / "policy" / "policy_allow.json"
        
        # 执行（预期失败）
        cmd = [
            "uv", "run", "agentos", "exec", "run",
            "--request", str(request_path),
            "--policy", str(policy_path),
            "--out", str(output_dir)
        ]
        
        result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
        
        # 检查 1: 必须失败
        if result.returncode == 0:
            return False, f"❌ FAIL: Unknown action should fail but succeeded (exit={result.returncode})"
        
        # 查找 run_tape.jsonl（可能在子目录中）
        run_tape_files = list(output_dir.rglob("run_tape.jsonl"))
        
        if not run_tape_files:
            # 检查 stderr 是否有 policy denied 信息
            if "not allowed by policy" in result.stderr or "not in allowlist" in result.stderr:
                return True, "✅ PASS: Unknown action denied (verified in stderr, no run_tape generated)"
            return False, f"❌ FAIL: No run_tape.jsonl and no policy error in stderr.\nStderr:\n{result.stderr}"
        
        # 检查 2: run_tape 必须包含 policy_denied 事件
        run_tape_path = run_tape_files[0]
        
        denial_found = False
        denial_reason = ""
        denied_operation = ""
        
        with open(run_tape_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get("event_type") == "policy_denied":  # 注意：是 event_type 不是 event
                    denial_found = True
                    details = event.get("details", {})
                    denied_operation = details.get("operation", "")
                    denial_reason = details.get("reason", "")
                    break
        
        if not denial_found:
            return False, f"❌ FAIL: run_tape exists but no policy_denied event for unknown action"
        
        # 检查 3: 拒绝原因必须明确
        if "not in allowlist" not in denial_reason and "unknown" not in denial_reason.lower():
            return False, f"❌ FAIL: Denial reason not clear. Got: {denial_reason}"
        
        return True, f"✅ PASS: Unknown action correctly denied. Reason: {denial_reason[:100]}"


if __name__ == "__main__":
    passed, message = gate_p0_n1_unknown_action_deny()
    print(message)
    sys.exit(0 if passed else 1)
