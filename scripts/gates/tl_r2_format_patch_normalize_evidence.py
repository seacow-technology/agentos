#!/usr/bin/env python3
"""
TL-R2-FORMAT-PATCH-NORMALIZE: format-patch 标准化证据必出现

终审 Gate A：确保 bring-back 场景中 format-patch 标准化证据真实记录

断言：
1. diff_validation.normalized_from_format_patch == true
2. diff_validation.normalized_start_line != null（且为 int >= 0）

目的：
- 防止 format-patch 检测逻辑软化/漂移
- 保证 "为什么 verifier 说它是 format-patch" 可一句话定位

硬证据：
- outputs/gates/tl_r2_format_patch_normalize/audit/run_tape.jsonl
- outputs/gates/tl_r2_format_patch_normalize/reports/gate_results.json
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parents[2]
sys.path.insert(0, str(project_root))

from agentos.ext.tools import DiffVerifier, ToolResult


def run_format_patch_normalize_gate():
    """
    终审 Gate A：format-patch 标准化证据必出现
    
    验证：
    1. 对一个 format-patch 文件，DiffVerifier 能检测到并标准化
    2. diff_validation 包含 normalized_from_format_patch=true
    3. diff_validation 包含 normalized_start_line（int >= 0）
    """
    
    gate_dir = project_root / "outputs" / "gates" / "tl_r2_format_patch_normalize"
    audit_dir = gate_dir / "audit"
    reports_dir = gate_dir / "reports"
    
    audit_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    run_tape_path = audit_dir / "run_tape.jsonl"
    gate_results_path = reports_dir / "gate_results.json"
    
    # 模拟 format-patch 输出（带邮件头）
    sample_format_patch = """From 1234567890abcdef Mon Sep 17 00:00:00 2001
From: Test Author <test@example.com>
Date: Mon, 1 Jan 2024 00:00:00 +0000
Subject: [PATCH] Add new feature

This is a commit message.
---
diff --git a/test.txt b/test.txt
index 1234567..abcdefg 100644
--- a/test.txt
+++ b/test.txt
@@ -1,3 +1,4 @@
 line 1
 line 2
+new line
 line 3
"""
    
    # 测试 DiffVerifier 检测
    result = ToolResult(
        tool="test-format-patch",
        status="success",
        diff=sample_format_patch,
        files_touched=["test.txt"],
        line_count=len(sample_format_patch.split('\n')),
        tool_run_id="gate-format-patch-normalize"
    )
    
    # 运行 verify
    validation = DiffVerifier.verify(result, allowed_paths=["**"], forbidden_paths=[])
    
    # 断言 1: normalized_from_format_patch == true
    if not validation.normalized_from_format_patch:
        error_msg = "❌ FAIL: normalized_from_format_patch should be True for format-patch input"
        print(error_msg)
        
        # 写 run_tape
        with open(run_tape_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "event": "format_patch_normalize_check",
                "status": "FAIL",
                "reason": error_msg,
                "validation": validation.to_dict()
            }) + "\n")
        
        # 写 gate_results
        with open(gate_results_path, "w", encoding="utf-8") as f:
            json.dump({
                "gate_status": "FAIL",
                "gate_name": "TL-R2-FORMAT-PATCH-NORMALIZE",
                "reason": error_msg,
                "validation": validation.to_dict()
            }, f, indent=2)
        
        return 1
    
    # 断言 2: normalized_start_line != null 且 >= 0
    if validation.normalized_start_line is None:
        error_msg = "❌ FAIL: normalized_start_line should not be None"
        print(error_msg)
        
        # 写 run_tape
        with open(run_tape_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "event": "format_patch_normalize_check",
                "status": "FAIL",
                "reason": error_msg,
                "validation": validation.to_dict()
            }) + "\n")
        
        # 写 gate_results
        with open(gate_results_path, "w", encoding="utf-8") as f:
            json.dump({
                "gate_status": "FAIL",
                "gate_name": "TL-R2-FORMAT-PATCH-NORMALIZE",
                "reason": error_msg,
                "validation": validation.to_dict()
            }, f, indent=2)
        
        return 1
    
    if not isinstance(validation.normalized_start_line, int) or validation.normalized_start_line < 0:
        error_msg = f"❌ FAIL: normalized_start_line should be int >= 0, got {validation.normalized_start_line}"
        print(error_msg)
        
        # 写 run_tape
        with open(run_tape_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "event": "format_patch_normalize_check",
                "status": "FAIL",
                "reason": error_msg,
                "validation": validation.to_dict()
            }) + "\n")
        
        # 写 gate_results
        with open(gate_results_path, "w", encoding="utf-8") as f:
            json.dump({
                "gate_status": "FAIL",
                "gate_name": "TL-R2-FORMAT-PATCH-NORMALIZE",
                "reason": error_msg,
                "validation": validation.to_dict()
            }, f, indent=2)
        
        return 1
    
    # ✅ PASS
    success_msg = (
        f"✅ PASS: format-patch normalize evidence confirmed\n"
        f"  - normalized_from_format_patch: {validation.normalized_from_format_patch}\n"
        f"  - normalized_start_line: {validation.normalized_start_line} (0-based)\n"
        f"  - errors: {len(validation.errors)}, warnings: {len(validation.warnings)}"
    )
    print(success_msg)
    
    # 写 run_tape
    with open(run_tape_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "event": "format_patch_normalize_check",
            "status": "PASS",
            "validation": validation.to_dict()
        }) + "\n")
    
    # 写 gate_results
    with open(gate_results_path, "w", encoding="utf-8") as f:
        json.dump({
            "gate_status": "PASS",
            "gate_name": "TL-R2-FORMAT-PATCH-NORMALIZE",
            "validation": validation.to_dict(),
            "message": success_msg
        }, f, indent=2)
    
    return 0


if __name__ == "__main__":
    sys.exit(run_format_patch_normalize_gate())
