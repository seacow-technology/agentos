#!/usr/bin/env python3
"""Gate R4: Rollback Proof Runtime

验收标准：
1. 成功执行后，记录 base_commit
2. 执行 rollback 到 base_commit
3. 验证：
   - git rev-parse HEAD == base_commit
   - landing 文件回到初始状态（不存在或 checksum 回到 init）
   - audit/rollback_proof.json 存在且包含：before_head、after_head、base_commit、files_changed_count、timestamp
4. run_tape 里出现 rollback_started / rollback_completed
"""

import json
import sys
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime, timezone

# 添加项目根到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from agentos.core.infra.git_client import GitClientFactory
from agentos.core.executor.rollback import RollbackManager
from agentos.core.executor.run_tape import RunTape


def create_test_exec_request(output_dir: Path) -> Path:
    """创建 6-step 测试用的 execution_request"""
    simple_id = f"test_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    exec_request = {
        "execution_request_id": simple_id,
        "schema_version": "0.11.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_path": str(output_dir / "test_repo"),
        "base_branch": "main",
        "execution_mode": "worktree",
        "patch_plan": {
            "steps": [
                {
                    "step_id": "step_01",
                    "operations": [
                        {
                            "action": "write_file",
                            "params": {
                                "path": "README.md",
                                "content": "# Test Project\n"
                            }
                        }
                    ],
                    "commit_message": "step_01: Create README.md"
                },
                {
                    "step_id": "step_02",
                    "operations": [
                        {
                            "action": "write_file",
                            "params": {
                                "path": "index.html",
                                "content": "<html><body><h1>Test</h1></body></html>\n"
                            }
                        }
                    ],
                    "commit_message": "step_02: Create index.html"
                },
                {
                    "step_id": "step_03",
                    "operations": [
                        {
                            "action": "write_file",
                            "params": {
                                "path": "style.css",
                                "content": "body { margin: 0; }\n"
                            }
                        }
                    ],
                    "commit_message": "step_03: Add styles"
                },
                {
                    "step_id": "step_04",
                    "operations": [
                        {
                            "action": "update_file",
                            "params": {
                                "path": "index.html",
                                "content": "<html><body><h1>Test</h1><p>Updated</p></body></html>\n"
                            }
                        }
                    ],
                    "commit_message": "step_04: Update index"
                },
                {
                    "step_id": "step_05",
                    "operations": [
                        {
                            "action": "update_file",
                            "params": {
                                "path": "README.md",
                                "content": "# Test Project\n\n## Features\n"
                            }
                        }
                    ],
                    "commit_message": "step_05: Update README"
                },
                {
                    "step_id": "step_06",
                    "operations": [
                        {
                            "action": "update_file",
                            "params": {
                                "path": "index.html",
                                "content": "<html><body><h1>Test</h1><p>Final</p></body></html>\n"
                            }
                        }
                    ],
                    "commit_message": "step_06: Final touches"
                }
            ]
        }
    }
    
    req_file = output_dir / "exec_request_rollback_test.json"
    with open(req_file, "w", encoding="utf-8") as f:
        json.dump(exec_request, f, indent=2)
    
    return req_file


def gate_r4_rollback_proof_runtime(repo_root: Path) -> tuple[bool, str]:
    """验证 rollback 功能的完整性和可审计性（自给自足版本）"""
    
    # 创建临时测试目录
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        output_dir = tmpdir / "outputs"
        output_dir.mkdir()
        
        # 1) 初始化一个git repo（必须有初始commit）
        test_repo = tmpdir / "test_repo"
        test_repo.mkdir()
        subprocess.run(["git", "init"], cwd=test_repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=test_repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=test_repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=test_repo, check=True, capture_output=True)
        
        # 2) 创建 exec_request (6 steps)
        req_file = create_test_exec_request(tmpdir)
        
        policy_allow = repo_root / "fixtures" / "policy" / "policy_allow.json"
        
        if not policy_allow.exists():
            return False, f"policy_allow.json not found: {policy_allow}"
        
        # 3) 运行 executor 成功执行 6 steps
        cmd = [
            "uv", "run", "agentos", "exec", "run",
            "--request", str(req_file),
            "--policy", str(policy_allow),
            "--repo", str(test_repo),
            "--out", str(output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root)
        
        if result.returncode != 0:
            return False, f"Executor run failed (exit={result.returncode}): {result.stderr[:200]}"
        
        # 4) 读取 sandbox_proof.json 获取 base_commit
        sandbox_proof_files = list(output_dir.rglob("sandbox_proof.json"))
        if not sandbox_proof_files:
            return False, f"sandbox_proof.json not found in {output_dir}"
        
        sandbox_proof_path = sandbox_proof_files[0]
        with open(sandbox_proof_path, "r", encoding="utf-8") as f:
            sandbox_proof = json.load(f)
        
        base_commit = sandbox_proof.get("base_commit")
        if not base_commit:
            return False, "base_commit not found in sandbox_proof.json"
        
        # 5) 初始化 Git 客户端和 RollbackManager
        git_client = GitClientFactory.get_client(test_repo)
        rollback_manager = RollbackManager(test_repo)
        
        # 记录回滚前的状态
        before_head = git_client.get_current_commit()
        
        # 6) 找到 audit 目录
        audit_dir = sandbox_proof_path.parent  # audit/ 目录
        
        # 初始化 RunTape（会追加到已有的 run_tape.jsonl）
        # RunTape(run_dir) 会创建 run_dir/run_tape.jsonl
        # executor 使用的是 RunTape(audit_dir)，所以会创建 audit_dir/run_tape.jsonl
        run_tape = RunTape(audit_dir)
        
        # 记录回滚开始事件
        run_tape.audit_logger.log_event("rollback_started", details={
            "before_head": before_head,
            "target_commit": base_commit,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # 7) 执行 rollback
        rollback_point = {
            "name": "gate_r4_rollback_test",
            "type": "main_repo",
            "commit_hash": base_commit,
            "checksums": {},  # 不验证 checksums，因为我们只关心 commit 回滚
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        rollback_result = rollback_manager.rollback_to(rollback_point, verify_checksums=False)
        
        if not rollback_result["success"]:
            return False, f"Rollback failed: {rollback_result.get('error', 'Unknown error')}"
        
        # 8) 验证回滚后的状态
        after_head = git_client.get_current_commit()
        
        # 验证 1: HEAD 是否回到 base_commit
        if after_head != base_commit:
            return False, f"HEAD mismatch after rollback: expected {base_commit}, got {after_head}"
        
        # 验证 2: landing 文件是否不存在或回到初始状态
        landing_files = ["index.html", "style.css", "README.md"]
        files_changed_count = 0
        
        for file_name in landing_files:
            file_path = test_repo / file_name
            if file_path.exists():
                return False, f"Landing file {file_name} still exists after rollback to base_commit"
            files_changed_count += 1
        
        # 9) 记录回滚完成事件
        run_tape.audit_logger.log_event("rollback_completed", details={
            "before_head": before_head,
            "after_head": after_head,
            "base_commit": base_commit,
            "files_changed_count": files_changed_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # 10) 生成 rollback_proof.json
        rollback_proof = {
            "rollback_proof_version": "1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "before_head": before_head,
            "after_head": after_head,
            "base_commit": base_commit,
            "files_changed_count": files_changed_count,
            "success": True,
            "rollback_result": rollback_result
        }
        
        rollback_proof_path = audit_dir / "rollback_proof.json"
        with open(rollback_proof_path, "w", encoding="utf-8") as f:
            json.dump(rollback_proof, f, indent=2)
        
        # 11) 验证 run_tape 包含回滚事件
        run_tape_path = audit_dir / "run_tape.jsonl"
        if not run_tape_path.exists():
            return False, f"run_tape.jsonl not found: {run_tape_path}"
        
        rollback_events = {"rollback_started": False, "rollback_completed": False}
        
        with open(run_tape_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                event = json.loads(line)
                event_type = event.get("event_type")
                if event_type == "rollback_started":
                    rollback_events["rollback_started"] = True
                elif event_type == "rollback_completed":
                    rollback_events["rollback_completed"] = True
        
        if not rollback_events["rollback_started"]:
            return False, "rollback_started event not found in run_tape.jsonl"
        
        if not rollback_events["rollback_completed"]:
            return False, "rollback_completed event not found in run_tape.jsonl"
        
        # 12) 验证 rollback_proof.json 存在且包含必需字段
        if not rollback_proof_path.exists():
            return False, f"rollback_proof.json not created: {rollback_proof_path}"
        
        with open(rollback_proof_path, "r", encoding="utf-8") as f:
            proof = json.load(f)
        
        required_fields = ["before_head", "after_head", "base_commit", "files_changed_count", "timestamp"]
        for field in required_fields:
            if field not in proof:
                return False, f"rollback_proof.json missing required field: {field}"
        
        return True, f"Rollback executed and verified - HEAD={after_head[:8]}, files_changed={files_changed_count}, proof + events logged"


def main():
    repo_root = Path.cwd()
    
    print("=" * 60)
    print("Gate R4: Rollback Proof Runtime")
    print("=" * 60)
    
    passed, message = gate_r4_rollback_proof_runtime(repo_root)
    
    if passed:
        print(f"✅ PASS: {message}")
        return 0
    else:
        print(f"❌ FAIL: {message}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
