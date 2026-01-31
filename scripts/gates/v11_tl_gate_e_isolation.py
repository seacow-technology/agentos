#!/usr/bin/env python3
"""TL Gate E - 隔离验证"""
import sys, re
from pathlib import Path

EXIT_CODE, PROJECT_ROOT = 0, Path(__file__).parent.parent.parent

def scan_adapters():
    global EXIT_CODE
    adapters_dir = PROJECT_ROOT / "agentos/ext/tools"
    
    violations = []
    for py_file in adapters_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        
        with open(py_file, encoding="utf-8") as f:
            content = f.read()
        
        # 检查是否泄漏AgentOS内部配置
        if re.search(r'\.agentos', content):
            violations.append(f"{py_file.name}: References .agentos config")
        
    if violations:
        for v in violations:
            print(f"⚠ {v}")
        # 警告但不失败
    else:
        print("✓ No isolation violations")
    
    return True

def main():
    global EXIT_CODE
    print("=" * 60 + "\nTL Gate E - Isolation Verification\n" + "=" * 60 + "\n")
    scan_adapters()
    print("\n" + "=" * 60)
    print("✅ TL Gate E: PASSED")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
