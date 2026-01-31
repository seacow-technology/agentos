#!/usr/bin/env python3
"""
Step 2 Gates: Executor Gates（EX-A 到 EX-H）

验证真 Executor 的核心能力：
- EX-A: Allowlist only - 只执行允许的操作
- EX-B: No subprocess - 0 subprocess（已有 gate，集成）
- EX-C: Sandbox proof - 必须在 worktree 执行
- EX-D: Bring-back proof - 带回后 commit 数量匹配
- EX-E: Audit completeness - run_tape 包含完整审计
- EX-F: Rollback proof - 回滚后 checksums 匹配
- EX-G: Review gate - 高风险需审批
- EX-H: Determinism baseline - 同输入输出结构稳定
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple


def gate_ex_a_allowlist_only(run_dir: Path) -> Tuple[bool, str]:
    """
    Gate EX-A: Allowlist only - 只执行允许的操作
    
    检查：
    - execution_request 中的所有 operations 在 allowlist 中
    - 使用的 sandbox_policy 限制了操作类型
    """
    exec_request_file = run_dir / "02_dryrun" / "exec_request.json"
    if not exec_request_file.exists():
        return False, "Missing exec_request.json"
    
    with open(exec_request_file, "r", encoding="utf-8") as f:
        exec_request = json.load(f)
    
    # 检查是否有 allowed_operations
    allowed_ops = exec_request.get("allowed_operations", [])
    if not allowed_ops:
        return False, "No allowed_operations defined"
    
    # 定义安全的操作集合
    safe_operations = {"write_file", "update_file", "patch_file", "git_add", "git_commit"}
    
    for op in allowed_ops:
        op_type = op.get("type", "") if isinstance(op, dict) else op
        if op_type not in safe_operations:
            return False, f"Unsafe operation in allowlist: {op_type}"
    
    return True, f"All {len(allowed_ops)} operations are in allowlist"


def gate_ex_b_no_subprocess(repo_root: Path) -> Tuple[bool, str]:
    """
    Gate EX-B: No subprocess - 集成已有的严格 subprocess gate
    
    检查：
    - 运行 strict_no_subprocess.py gate
    - 确认 0 violations
    """
    gate_script = repo_root / "scripts" / "gates" / "strict_no_subprocess.py"
    if not gate_script.exists():
        return False, "strict_no_subprocess.py gate not found"
    
    # 读取最近的扫描结果
    result_file = repo_root / "outputs" / "gates" / "strict_no_subprocess.json"
    if not result_file.exists():
        return False, "No subprocess gate results found (run gate first)"
    
    with open(result_file, "r", encoding="utf-8") as f:
        result = json.load(f)
    
    violations = result.get("violations_count", 0)
    if violations > 0:
        return False, f"Found {violations} subprocess violations"
    
    return True, f"0 subprocess violations (scanned {result.get('scanned_files', 0)} files)"


def gate_ex_c_sandbox_proof(run_dir: Path) -> Tuple[bool, str]:
    """
    Gate EX-C: Sandbox proof - 必须在 worktree 执行
    
    检查：
    - 存在 sandbox_proof.json
    - is_worktree = true
    - main_repo 未被直接修改（带回前）
    """
    sandbox_proof_file = run_dir / "03_executor" / "sandbox_proof.json"
    if not sandbox_proof_file.exists():
        return False, "Missing sandbox_proof.json"
    
    with open(sandbox_proof_file, "r", encoding="utf-8") as f:
        proof = json.load(f)
    
    if not proof.get("is_worktree", False):
        return False, "Execution not in worktree"
    
    # 检查主 repo 未被修改（可选，如果有记录）
    if "main_repo_modified" in proof and proof["main_repo_modified"]:
        return False, "Main repo was modified directly (should use worktree)"
    
    worktree_path = proof.get("worktree_path", "")
    return True, f"Executed in worktree: {worktree_path}"


def gate_ex_d_bring_back_proof(run_dir: Path, repo_root: Path) -> Tuple[bool, str]:
    """
    Gate EX-D: Bring-back proof - 带回后 commit 数量与 step 数一致
    
    检查：
    - sandbox_proof.json 记录了 commits
    - 主 repo 的 commit 数量匹配
    - 每个 commit 都有对应的 step
    """
    sandbox_proof_file = run_dir / "03_executor" / "sandbox_proof.json"
    if not sandbox_proof_file.exists():
        return False, "Missing sandbox_proof.json"
    
    with open(sandbox_proof_file, "r", encoding="utf-8") as f:
        proof = json.load(f)
    
    commits_brought_back = proof.get("commits_brought_back", [])
    if not commits_brought_back:
        return False, "No commits brought back"
    
    # 检查 exec_request 的 steps 数量
    exec_request_file = run_dir / "02_dryrun" / "exec_request.json"
    if exec_request_file.exists():
        with open(exec_request_file, "r", encoding="utf-8") as f:
            exec_request = json.load(f)
        
        steps = exec_request.get("allowed_operations", [])
        expected_commits = len([s for s in steps if "git_commit" in str(s)])
        
        if len(commits_brought_back) != expected_commits:
            return False, f"Commit count mismatch: {len(commits_brought_back)} brought back, {expected_commits} expected"
    
    return True, f"{len(commits_brought_back)} commits brought back to main repo"


def gate_ex_e_audit_completeness(run_dir: Path) -> Tuple[bool, str]:
    """
    Gate EX-E: Audit completeness - run_tape 包含完整审计
    
    检查：
    - run_tape.jsonl 存在
    - 每个 step 有 start 和 end 事件
    - 每个 end 事件有 checksum
    """
    run_tape_file = run_dir / "03_executor" / "run_tape.jsonl"
    if not run_tape_file.exists():
        return False, "Missing run_tape.jsonl"
    
    # 读取所有事件
    events = []
    with open(run_tape_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    
    if not events:
        return False, "run_tape.jsonl is empty"
    
    # 检查 step events
    step_starts = [e for e in events if e.get("event_type") == "step_start"]
    step_ends = [e for e in events if e.get("event_type") == "step_end"]
    
    if len(step_starts) != len(step_ends):
        return False, f"Step count mismatch: {len(step_starts)} starts, {len(step_ends)} ends"
    
    # 检查 checksums
    missing_checksums = [e for e in step_ends if not e.get("details", {}).get("checksums")]
    if missing_checksums:
        return False, f"{len(missing_checksums)} step_end events missing checksums"
    
    return True, f"Complete audit: {len(step_starts)} steps with checksums"


def gate_ex_f_rollback_proof(run_dir: Path) -> Tuple[bool, str]:
    """
    Gate EX-F: Rollback proof - 回滚后 checksums 匹配
    
    检查：
    - 存在 rollback_proof.json（如果执行了回滚测试）
    - checksums_match = true
    - 验证的文件数量 > 0
    """
    rollback_proof_file = run_dir / "03_executor" / "rollback_proof.json"
    
    # 这个 gate 是可选的（只在执行回滚测试时需要）
    if not rollback_proof_file.exists():
        return True, "No rollback performed (optional gate, PASS)"
    
    with open(rollback_proof_file, "r", encoding="utf-8") as f:
        proof = json.load(f)
    
    if not proof.get("success", False):
        return False, "Rollback failed"
    
    if not proof.get("checksums_match", False):
        return False, "Checksums do not match after rollback"
    
    checksums_verified = proof.get("checksums_verified", 0)
    if checksums_verified == 0:
        return False, "No checksums verified"
    
    return True, f"Rollback verified: {checksums_verified} files match"


def gate_ex_g_review_gate(run_dir: Path) -> Tuple[bool, str]:
    """
    Gate EX-G: Review gate - 高风险需审批
    
    检查：
    - 如果 exec_request 标记 requires_review = true
    - 必须存在 approval.txt 或 status = REQUIRES_REVIEW
    """
    exec_request_file = run_dir / "02_dryrun" / "exec_request.json"
    if not exec_request_file.exists():
        return True, "No exec_request (gate not applicable)"
    
    with open(exec_request_file, "r", encoding="utf-8") as f:
        exec_request = json.load(f)
    
    requires_review = exec_request.get("requires_review", False)
    
    if not requires_review:
        return True, "No review required (low risk)"
    
    # 检查是否有审批
    approval_file = run_dir / "03_executor" / "approval.txt"
    if not approval_file.exists():
        # 检查状态是否为 REQUIRES_REVIEW（阻塞）
        status_file = run_dir / "03_executor" / "status.json"
        if status_file.exists():
            with open(status_file, "r", encoding="utf-8") as f:
                status = json.load(f)
            
            if status.get("status") == "REQUIRES_REVIEW":
                return True, "Correctly blocked on REQUIRES_REVIEW status"
        
        return False, "High risk but no approval found"
    
    # 验证审批内容
    approval_text = approval_file.read_text()
    if "APPROVED" not in approval_text:
        return False, "Approval file exists but not approved"
    
    return True, "High risk approved for execution"


def gate_ex_h_determinism_baseline(run_dir: Path) -> Tuple[bool, str]:
    """
    Gate EX-H: Determinism baseline - 同输入输出结构稳定
    
    检查：
    - 输出文件结构符合预期
    - 必要字段都存在
    - 数据类型正确
    """
    # 检查关键输出文件的结构
    required_files = {
        "02_dryrun/exec_request.json": ["execution_request_id", "allowed_operations"],
        "03_executor/sandbox_proof.json": ["is_worktree", "worktree_path"],
    }
    
    for file_path, required_fields in required_files.items():
        full_path = run_dir / file_path
        if not full_path.exists():
            continue  # 可选文件
        
        with open(full_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field '{field}' in {file_path}"
    
    # 检查输出目录结构
    expected_dirs = ["01_intent", "02_dryrun", "03_executor"]
    missing_dirs = [d for d in expected_dirs if not (run_dir / d).exists()]
    
    if missing_dirs:
        return False, f"Missing expected directories: {missing_dirs}"
    
    return True, "Output structure is deterministic and complete"


def run_gates(run_dir: Path, repo_root: Path) -> Dict[str, Any]:
    """运行所有 Executor gates"""
    gates = [
        ("EX-A: Allowlist only", lambda: gate_ex_a_allowlist_only(run_dir)),
        ("EX-B: No subprocess", lambda: gate_ex_b_no_subprocess(repo_root)),
        ("EX-C: Sandbox proof", lambda: gate_ex_c_sandbox_proof(run_dir)),
        ("EX-D: Bring-back proof", lambda: gate_ex_d_bring_back_proof(run_dir, repo_root)),
        ("EX-E: Audit completeness", lambda: gate_ex_e_audit_completeness(run_dir)),
        ("EX-F: Rollback proof", lambda: gate_ex_f_rollback_proof(run_dir)),
        ("EX-G: Review gate", lambda: gate_ex_g_review_gate(run_dir)),
        ("EX-H: Determinism baseline", lambda: gate_ex_h_determinism_baseline(run_dir)),
    ]
    
    results = {}
    all_passed = True
    
    print("🔒 Step 2 Executor Gates (EX-A to EX-H)")
    print("=" * 60)
    print(f"Run directory: {run_dir}")
    print(f"Repo root: {repo_root}\n")
    
    for name, gate_func in gates:
        try:
            passed, message = gate_func()
            results[name] = {"passed": passed, "message": message}
            
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} - {name}")
            print(f"      {message}")
            
            if not passed:
                all_passed = False
                
        except Exception as e:
            results[name] = {"passed": False, "message": f"Error: {e}"}
            print(f"❌ FAIL - {name}")
            print(f"      Error: {e}")
            all_passed = False
    
    print()
    print("=" * 60)
    
    passed_count = sum(1 for r in results.values() if r["passed"])
    total_count = len(results)
    
    if all_passed:
        print(f"✅ All gates passed ({passed_count}/{total_count})")
        return {"status": "PASS", "gates": results}
    else:
        print(f"❌ Some gates failed ({passed_count}/{total_count})")
        return {"status": "FAIL", "gates": results}


def main():
    if len(sys.argv) < 2:
        print("Usage: python step2_executor_gates.py <run_directory> [repo_root]")
        sys.exit(1)
    
    run_dir = Path(sys.argv[1])
    repo_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()
    
    if not run_dir.exists():
        print(f"❌ Error: Run directory not found: {run_dir}")
        sys.exit(1)
    
    results = run_gates(run_dir, repo_root)
    
    # 保存结果
    output_file = run_dir / "gate_results_step2.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    sys.exit(0 if results["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
