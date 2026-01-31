#!/usr/bin/env python3
"""
Gate: G_EX_ALLOWLIST_STRICT
验证执行记录中只出现 allowlist 动作
"""

import json
import sys
from pathlib import Path

# Allowlist for demo
ALLOWED_ACTIONS = {
    "write_file",
    "update_file",
    "read_file",
    "mkdir",
    "git_init",
    "git_add",
    "git_commit",
    "git_status",
    "git_diff"
}

FORBIDDEN_ACTIONS = {
    "shell",
    "subprocess",
    "exec",
    "eval",
    "http_fetch",  # 默认禁止，除非显式允许
    "ssh",
    "curl",
    "wget"
}


def check_allowlist_strict(run_tape_path: Path) -> bool:
    """检查 run_tape 中的所有动作是否在 allowlist 内"""
    
    if not run_tape_path.exists():
        print(f"❌ run_tape not found: {run_tape_path}")
        return False
    
    violations = []
    line_no = 0
    
    with open(run_tape_path, encoding="utf-8") as f:
        for line in f:
            line_no += 1
            try:
                event = json.loads(line)
                
                # 检查 operation 动作
                if event.get("event_type") == "operation_start":
                    action = event.get("details", {}).get("action")
                    if action:
                        if action in FORBIDDEN_ACTIONS:
                            violations.append({
                                "line": line_no,
                                "action": action,
                                "reason": "FORBIDDEN action detected"
                            })
                        elif action not in ALLOWED_ACTIONS:
                            violations.append({
                                "line": line_no,
                                "action": action,
                                "reason": "NOT in allowlist"
                            })
            
            except json.JSONDecodeError:
                continue
    
    if violations:
        print(f"❌ Allowlist violations found:")
        for v in violations:
            print(f"   Line {v['line']}: {v['action']} ({v['reason']})")
        return False
    
    print(f"✓ Allowlist strict check passed")
    return True


if __name__ == "__main__":
    # 查找最近的 run_tape.jsonl
    output_dir = Path("outputs")
    if not output_dir.exists():
        output_dir = Path("demo_output")
    
    run_tapes = list(output_dir.glob("**/run_tape.jsonl"))
    
    if not run_tapes:
        print("❌ No run_tape.jsonl found in outputs/")
        sys.exit(1)
    
    # 使用最新的
    latest_run_tape = max(run_tapes, key=lambda p: p.stat().st_mtime)
    
    print(f"🔒 Gate G_EX_ALLOWLIST_STRICT")
    print(f"   Checking: {latest_run_tape}")
    print("=" * 60)
    
    if check_allowlist_strict(latest_run_tape):
        print("=" * 60)
        print("✅ Gate G_EX_ALLOWLIST_STRICT PASSED")
        sys.exit(0)
    else:
        print("=" * 60)
        print("❌ Gate G_EX_ALLOWLIST_STRICT FAILED")
        sys.exit(1)
