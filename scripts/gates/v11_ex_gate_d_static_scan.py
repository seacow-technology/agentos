#!/usr/bin/env python3
"""
EX Gate D - 静态扫描禁止执行

扫描Executor代码，确保没有危险的执行符号
"""

import sys
import re
from pathlib import Path

EXIT_CODE = 0
PROJECT_ROOT = Path(__file__).parent.parent.parent


def scan_file_for_dangerous_patterns(filepath: Path) -> list:
    """扫描文件中的危险模式"""
    dangerous_patterns = [
        (r'subprocess\..*shell\s*=\s*True', "subprocess with shell=True"),
        (r'os\.system\s*\(', "os.system()"),
        (r'\beval\s*\(', "eval()"),
        (r'\bexec\s*\(', "exec()"),
        (r'__import__\s*\(', "__import__()"),
        (r'compile\s*\(.*\bexec\b', "compile() with exec"),
    ]
    
    violations = []
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            # 跳过注释行
            if line.strip().startswith("#"):
                continue
            
            for pattern, description in dangerous_patterns:
                if re.search(pattern, line):
                    violations.append({
                        "line": line_num,
                        "pattern": description,
                        "code": line.strip()
                    })
    
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
    
    return violations


def main():
    global EXIT_CODE
    
    print("=" * 60)
    print("EX Gate D - Static Scan for Dangerous Execution")
    print("=" * 60)
    print()
    
    # 扫描Executor模块
    executor_dir = PROJECT_ROOT / "agentos/core/executor"
    
    if not executor_dir.exists():
        print("✗ Executor directory not found")
        return 1
    
    total_violations = 0
    
    for py_file in executor_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        
        violations = scan_file_for_dangerous_patterns(py_file)
        
        if violations:
            print(f"✗ {py_file.name}:")
            for v in violations:
                print(f"  Line {v['line']}: {v['pattern']}")
                print(f"    {v['code']}")
            total_violations += len(violations)
            EXIT_CODE = 1
        else:
            print(f"✓ {py_file.name}: Clean")
    
    print()
    print("=" * 60)
    if EXIT_CODE == 0:
        print("✅ EX Gate D: NO DANGEROUS EXECUTION PATTERNS")
    else:
        print(f"❌ EX Gate D: FOUND {total_violations} VIOLATIONS")
    print("=" * 60)
    
    return EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
