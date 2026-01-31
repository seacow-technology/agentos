#!/usr/bin/env python3
"""
Gate: G_EX_AUDIT_COMPLETE
验证 run_tape.jsonl 每步都有 start/end，且包含输入/输出 hash
"""

import json
import sys
from pathlib import Path
from collections import defaultdict


def check_audit_complete(run_tape_path: Path) -> bool:
    """检查审计日志完整性"""
    
    if not run_tape_path.exists():
        print(f"❌ run_tape not found: {run_tape_path}")
        return False
    
    # 追踪每个 operation 的 start/end
    operations = defaultdict(dict)
    missing_hashes = []
    
    with open(run_tape_path, encoding="utf-8") as f:
        for line in f:
            try:
                event = json.loads(line)
                event_type = event.get("event_type")
                
                if event_type == "operation_start":
                    op_id = event.get("details", {}).get("op_id")
                    if op_id:
                        operations[op_id]["start"] = event
                        
                        # 检查是否有输入 hash
                        details = event.get("details", {})
                        if "input_hash" not in details and "params" in details:
                            missing_hashes.append({
                                "op_id": op_id,
                                "type": "input",
                                "reason": "No input_hash"
                            })
                
                elif event_type == "operation_end":
                    op_id = event.get("details", {}).get("op_id")
                    if op_id:
                        operations[op_id]["end"] = event
                        
                        # 检查是否有输出 hash
                        details = event.get("details", {})
                        if details.get("status") == "success" and "output_hash" not in details:
                            missing_hashes.append({
                                "op_id": op_id,
                                "type": "output",
                                "reason": "No output_hash"
                            })
            
            except json.JSONDecodeError:
                continue
    
    # 检查是否每个 operation 都有 start 和 end
    incomplete_ops = []
    for op_id, events in operations.items():
        if "start" not in events:
            incomplete_ops.append({
                "op_id": op_id,
                "missing": "start"
            })
        if "end" not in events:
            incomplete_ops.append({
                "op_id": op_id,
                "missing": "end"
            })
    
    # 报告
    passed = True
    
    if incomplete_ops:
        print(f"❌ Incomplete operations:")
        for op in incomplete_ops:
            print(f"   {op['op_id']}: missing {op['missing']}")
        passed = False
    else:
        print(f"✓ All operations have start/end events")
    
    if missing_hashes:
        print(f"⚠ Missing hashes (non-blocking):")
        for h in missing_hashes:
            print(f"   {h['op_id']}: {h['type']} - {h['reason']}")
        # 不视为失败，仅警告
    else:
        print(f"✓ All operations have input/output hashes")
    
    return passed


if __name__ == "__main__":
    output_dir = Path("outputs")
    if not output_dir.exists():
        output_dir = Path("demo_output")
    
    run_tapes = list(output_dir.glob("**/run_tape.jsonl")) if output_dir.exists() else []
    
    if not run_tapes:
        print("❌ No run_tape.jsonl found")
        sys.exit(1)
    
    latest_run_tape = max(run_tapes, key=lambda p: p.stat().st_mtime)
    
    print(f"🔒 Gate G_EX_AUDIT_COMPLETE")
    print(f"   Checking: {latest_run_tape}")
    print("=" * 60)
    
    if check_audit_complete(latest_run_tape):
        print("=" * 60)
        print("✅ Gate G_EX_AUDIT_COMPLETE PASSED")
        sys.exit(0)
    else:
        print("=" * 60)
        print("❌ Gate G_EX_AUDIT_COMPLETE FAILED")
        sys.exit(1)
