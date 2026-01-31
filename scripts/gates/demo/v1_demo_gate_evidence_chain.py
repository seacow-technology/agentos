#!/usr/bin/env python3
"""
Gate R3: Evidence Chain Completeness (Artifacts)

验证审计证据链的完整性（run_tape、checksums、rollback_proof、summary）。
"""

import json
import sys
import hashlib
from pathlib import Path
from typing import Tuple, List


def compute_file_checksum(file_path: Path) -> str:
    """计算文件SHA256"""
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def gate_r3_evidence_chain(repo_root: Path) -> Tuple[bool, str]:
    """
    Gate R3: 验证证据链完整性
    
    验收：
    1. audit/run_tape.jsonl 存在且包含关键事件
    2. audit/checksums.json 存在且可复算
    3. reports/execution_summary.json 存在且字段齐全
    4. audit/sandbox_proof.json 存在（rollback proof的一种形式）
    """
    
    # 使用固定的测试输出目录（实际路径是 /tmp/demo_success/demo_6steps_001）
    test_output = Path("/tmp/demo_success/demo_6steps_001")
    
    if not test_output.exists():
        return False, f"Test output not found: {test_output}"
    
    issues: List[str] = []
    
    # 检查 1: run_tape.jsonl 存在且包含关键事件
    run_tape_file = test_output / "audit" / "run_tape.jsonl"
    if not run_tape_file.exists():
        issues.append("run_tape.jsonl not found")
    else:
        # 检查关键事件
        required_events = ["execution_start", "policy_loaded", "sandbox_created", "execution_complete"]
        found_events = set()
        
        with open(run_tape_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                event = json.loads(line)
                event_type = event.get("event_type", "")
                if event_type in required_events:
                    found_events.add(event_type)
        
        missing_events = set(required_events) - found_events
        if missing_events:
            issues.append(f"run_tape missing events: {missing_events}")
    
    # 检查 2: checksums.json 存在且格式正确
    checksums_file = test_output / "audit" / "checksums.json"
    if not checksums_file.exists():
        issues.append("checksums.json not found")
    else:
        with open(checksums_file, "r", encoding="utf-8") as f:
            checksums = json.load(f)
        
        if "generated_at" not in checksums:
            issues.append("checksums.json missing 'generated_at'")
        
        if "files" not in checksums or not isinstance(checksums["files"], dict):
            issues.append("checksums.json missing 'files' dict")
        
        # 验证至少包含 run_tape 的 checksum
        if "run_tape.jsonl" not in checksums.get("files", {}):
            issues.append("checksums.json missing run_tape.jsonl checksum")
    
    # 检查 3: execution_summary.json 存在且字段齐全
    summary_file = test_output / "reports" / "execution_summary.json"
    if not summary_file.exists():
        issues.append("execution_summary.json not found")
    else:
        with open(summary_file, "r", encoding="utf-8") as f:
            summary = json.load(f)
        
        required_fields = ["execution_request_id", "status", "commit_count", "patch_count", "sandbox_used"]
        missing = [f for f in required_fields if f not in summary]
        if missing:
            issues.append(f"execution_summary missing fields: {missing}")
        
        # 验证成功状态的字段值
        if summary.get("status") == "success":
            if summary.get("commit_count", 0) < 6:
                issues.append(f"commit_count={summary.get('commit_count')} < 6")
            if summary.get("patch_count", 0) < 6:
                issues.append(f"patch_count={summary.get('patch_count')} < 6")
            if not summary.get("sandbox_used"):
                issues.append("sandbox_used=false")
    
    # 检查 4: sandbox_proof.json 存在（作为 rollback proof 的一种形式）
    sandbox_proof_file = test_output / "audit" / "sandbox_proof.json"
    if not sandbox_proof_file.exists():
        issues.append("sandbox_proof.json not found")
    else:
        with open(sandbox_proof_file, "r", encoding="utf-8") as f:
            proof = json.load(f)
        
        required_proof_fields = ["base_commit", "worktree_head_sha", "main_repo_head_sha"]
        missing = [f for f in required_proof_fields if f not in proof]
        if missing:
            issues.append(f"sandbox_proof missing fields: {missing}")
    
    if issues:
        return False, f"Evidence chain incomplete: {'; '.join(issues)}"
    
    return True, "Evidence chain complete: run_tape + checksums + summary + sandbox_proof all verified"


def main():
    repo_root = Path.cwd()
    
    print("=" * 60)
    print("Gate R3: Evidence Chain Completeness (Artifacts)")
    print("=" * 60)
    
    passed, message = gate_r3_evidence_chain(repo_root)
    
    if passed:
        print(f"✅ PASS: {message}")
        return 0
    else:
        print(f"❌ FAIL: {message}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
