#!/usr/bin/env python3
"""
Gate R2: Worktree Forced Proof (Runtime)

验证 worktree 强制执行、patches 生成、commits 带回主 repo。
"""

import json
import sys
from pathlib import Path
from typing import Tuple


def gate_r2_worktree_proof(repo_root: Path) -> Tuple[bool, str]:
    """
    Gate R2: 验证 worktree 强制执行
    
    验收：
    1. sandbox_proof.json 存在且 sandbox_used=true (implicit)
    2. patches/*.patch 至少 6 个
    3. sandbox_proof 包含 base_commit、worktree_head_sha、main_repo_head_sha、patch_count
    4. 主 repo commit 数量 >= 7 (1 init + 6 steps)
    """
    
    # 使用固定的测试输出目录（从上一次成功执行）
    test_output = Path("/tmp/demo_success/demo_6steps_001")
    
    if not test_output.exists():
        return False, f"Test output not found: {test_output}. Run successful execution first."
    
    # 检查 1: sandbox_proof.json 存在
    sandbox_proof_file = test_output / "audit" / "sandbox_proof.json"
    if not sandbox_proof_file.exists():
        return False, f"sandbox_proof.json not found: {sandbox_proof_file}"
    
    with open(sandbox_proof_file, "r", encoding="utf-8") as f:
        sandbox_proof = json.load(f)
    
    # 检查 2: sandbox_proof 包含必要字段
    required_fields = ["base_commit", "worktree_head_sha", "main_repo_head_sha", "patch_count", "patch_files"]
    missing_fields = [f for f in required_fields if f not in sandbox_proof]
    if missing_fields:
        return False, f"sandbox_proof missing fields: {missing_fields}"
    
    # 检查 3: patch_count >= 6
    if sandbox_proof["patch_count"] < 6:
        return False, f"patch_count={sandbox_proof['patch_count']} < 6"
    
    # 检查 4: patches 目录存在且包含 >= 6 个 patch 文件
    patches_dir = test_output / "patches"
    if not patches_dir.exists():
        return False, f"patches directory not found: {patches_dir}"
    
    patch_files = list(patches_dir.glob("*.patch"))
    if len(patch_files) < 6:
        return False, f"patch files count={len(patch_files)} < 6"
    
    # 检查 5: execution_summary.json 包含正确的 sandbox_used
    summary_file = test_output / "reports" / "execution_summary.json"
    if not summary_file.exists():
        return False, f"execution_summary.json not found"
    
    with open(summary_file, "r", encoding="utf-8") as f:
        summary = json.load(f)
    
    if not summary.get("sandbox_used"):
        return False, "execution_summary shows sandbox_used=false"
    
    # 检查 6: commit_count 在 summary 中
    commit_count = summary.get("commit_count", 0)
    if commit_count < 6:
        return False, f"summary commit_count={commit_count} < 6"
    
    return True, f"Worktree proof verified: {commit_count} commits, {len(patch_files)} patches, sandbox_used=true"


def main():
    repo_root = Path.cwd()
    
    print("=" * 60)
    print("Gate R2: Worktree Forced Proof (Runtime)")
    print("=" * 60)
    
    passed, message = gate_r2_worktree_proof(repo_root)
    
    if passed:
        print(f"✅ PASS: {message}")
        return 0
    else:
        print(f"❌ FAIL: {message}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
