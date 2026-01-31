#!/usr/bin/env python3
"""
Gate: G_EX_NO_SHELL
验证代码与 run_tape 均不得出现 subprocess / shell / exec / eval
"""

import json
import sys
from pathlib import Path
import re

FORBIDDEN_PATTERNS = [
    r'subprocess\.',
    r'os\.system',
    r'os\.popen',
    r'shell=True',
    r'\bexec\(',
    r'\beval\(',
    r'__import__'
]


def check_no_shell_in_code(repo_path: Path) -> bool:
    """检查代码中是否有 shell 调用"""
    
    violations = []
    
    # 检查 Python 文件
    for py_file in repo_path.rglob("*.py"):
        # 跳过测试和 gates 自身
        if "test_" in py_file.name or "gate" in py_file.name:
            continue
        
        content = py_file.read_text()
        
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, content):
                violations.append({
                    "file": str(py_file.relative_to(repo_path)),
                    "pattern": pattern
                })
    
    if violations:
        print(f"❌ Shell/subprocess usage found in code:")
        for v in violations:
            print(f"   {v['file']}: {v['pattern']}")
        return False
    
    print(f"✓ No shell in code")
    return True


def check_no_shell_in_run_tape(run_tape_path: Path) -> bool:
    """检查 run_tape 中是否有 shell 动作"""
    
    if not run_tape_path.exists():
        print(f"⚠ run_tape not found: {run_tape_path}")
        return True  # 不存在则跳过
    
    violations = []
    line_no = 0
    
    with open(run_tape_path, encoding="utf-8") as f:
        for line in f:
            line_no += 1
            try:
                event = json.loads(line)
                
                # 检查是否有 shell 相关动作
                if event.get("event_type") == "operation_start":
                    action = event.get("details", {}).get("action", "")
                    if "shell" in action.lower() or "subprocess" in action.lower():
                        violations.append({
                            "line": line_no,
                            "action": action
                        })
            
            except json.JSONDecodeError:
                continue
    
    if violations:
        print(f"❌ Shell actions found in run_tape:")
        for v in violations:
            print(f"   Line {v['line']}: {v['action']}")
        return False
    
    print(f"✓ No shell in run_tape")
    return True


if __name__ == "__main__":
    repo_path = Path(".")
    
    # 查找 run_tape
    output_dir = Path("outputs")
    if not output_dir.exists():
        output_dir = Path("demo_output")
    
    run_tapes = list(output_dir.glob("**/run_tape.jsonl")) if output_dir.exists() else []
    latest_run_tape = max(run_tapes, key=lambda p: p.stat().st_mtime) if run_tapes else None
    
    print(f"🔒 Gate G_EX_NO_SHELL")
    print("=" * 60)
    
    passed = True
    
    # 检查代码
    if not check_no_shell_in_code(repo_path):
        passed = False
    
    # 检查 run_tape
    if latest_run_tape and not check_no_shell_in_run_tape(latest_run_tape):
        passed = False
    
    print("=" * 60)
    if passed:
        print("✅ Gate G_EX_NO_SHELL PASSED")
        sys.exit(0)
    else:
        print("❌ Gate G_EX_NO_SHELL FAILED")
        sys.exit(1)
