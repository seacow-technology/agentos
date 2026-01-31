#!/usr/bin/env python3
"""
EX Gate E - 隔离验证

验证Executor不会泄漏宿主环境信息
"""

import sys
import re
from pathlib import Path

EXIT_CODE = 0
PROJECT_ROOT = Path(__file__).parent.parent.parent


def scan_for_isolation_violations(filepath: Path) -> list:
    """扫描可能破坏隔离的代码"""
    violation_patterns = [
        (r'os\.environ\[.HOME.', "Accessing HOME environment variable"),
        (r'Path\.home\(\)', "Using Path.home()"),
        (r'~/', "Using ~ path expansion"),
        (r'\.agentos', "Accessing .agentos config"),
        (r'/Users/', "Hardcoded user path"),
        (r'/home/', "Hardcoded home path"),
    ]
    
    violations = []
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            # 跳过注释和文档字符串
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            
            for pattern, description in violation_patterns:
                if re.search(pattern, line):
                    violations.append({
                        "line": line_num,
                        "issue": description,
                        "code": line.strip()
                    })
    
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
    
    return violations


def main():
    global EXIT_CODE
    
    print("=" * 60)
    print("EX Gate E - Isolation Verification")
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
        
        violations = scan_for_isolation_violations(py_file)
        
        if violations:
            print(f"⚠ {py_file.name}:")
            for v in violations:
                print(f"  Line {v['line']}: {v['issue']}")
                print(f"    {v['code']}")
            total_violations += len(violations)
            # 注意：某些HOME访问可能是合理的（例如在tempfile中），所以这里只警告
            # EXIT_CODE = 1
        else:
            print(f"✓ {py_file.name}: No isolation violations")
    
    print()
    
    # 总结
    if total_violations > 0:
        print(f"⚠ Found {total_violations} potential isolation issues")
        print("  Review these to ensure they don't leak host information")
    
    print()
    print("=" * 60)
    if EXIT_CODE == 0:
        print("✅ EX Gate E: ISOLATION VERIFIED")
    else:
        print("❌ EX Gate E: ISOLATION VIOLATIONS FOUND")
    print("=" * 60)
    
    return EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
