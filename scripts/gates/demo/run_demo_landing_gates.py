#!/usr/bin/env python3
"""
Gate Runner: Demo Landing Gates
运行所有 Demo 专用的 Gates
"""

import sys
import subprocess
from pathlib import Path


GATES = [
    ("G_EX_ALLOWLIST_STRICT", "g_ex_allowlist_strict.py", "执行记录只有 allowlist 动作"),
    ("G_EX_NO_SHELL", "g_ex_no_shell.py", "代码和日志中无 shell 调用"),
    ("G_EX_AUDIT_COMPLETE", "g_ex_audit_complete.py", "审计日志完整（start/end + hashes）"),
    ("G_EX_SITE_STRUCTURE", "g_ex_site_structure.py", "HTML 包含 5 个必需 sections"),
]


def run_gate(gate_script: Path) -> bool:
    """运行单个 gate"""
    result = subprocess.run(
        ["python3", str(gate_script)],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    return result.returncode == 0


def main():
    gates_dir = Path(__file__).parent
    
    print("🔒 Running Demo Landing Gates")
    print("=" * 60)
    print()
    
    passed = 0
    failed = 0
    
    for gate_name, gate_file, description in GATES:
        gate_path = gates_dir / gate_file
        
        if not gate_path.exists():
            print(f"⚠ Gate not found: {gate_file}")
            continue
        
        print(f"Running: {gate_name}")
        print(f"  {description}")
        print()
        
        if run_gate(gate_path):
            passed += 1
        else:
            failed += 1
        
        print()
    
    print("=" * 60)
    print(f"✅ Passed: {passed}/{len(GATES)}")
    if failed > 0:
        print(f"❌ Failed: {failed}/{len(GATES)}")
        sys.exit(1)
    else:
        print("🎉 All Gates PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
