#!/usr/bin/env python3
"""
v11 AP Gate D: No Execution Symbols

Ensures AnswerPack code doesn't contain dangerous execution patterns:
- subprocess (with shell=True or otherwise)
- os.system
- eval/exec
- __import__

This is a static code scan of all answer-related Python files.
"""

import sys
import re
from pathlib import Path

# Assume script is in scripts/gates/
PROJECT_ROOT = Path(__file__).parent.parent.parent
EXIT_CODE = 0

# Dangerous patterns
DANGEROUS_PATTERNS = [
    (r'subprocess\.(call|run|Popen|check_call|check_output)', 'subprocess execution'),
    (r'os\.system', 'os.system execution'),
    (r'\beval\s*\(', 'eval() usage'),
    (r'\bexec\s*\(', 'exec() usage'),
    (r'__import__\s*\(', '__import__() usage'),
]


def scan_file(file_path: Path) -> list[tuple[int, str, str]]:
    """Scan a Python file for dangerous patterns.
    
    Returns:
        List of (line_number, pattern_name, line_content)
    """
    findings = []
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                # Skip comments
                if line.strip().startswith("#"):
                    continue
                
                for pattern, name in DANGEROUS_PATTERNS:
                    if re.search(pattern, line):
                        findings.append((line_num, name, line.strip()))
    
    except Exception as e:
        print(f"  ! Error reading {file_path}: {e}")
    
    return findings


def main():
    print("=" * 60)
    print("v11 AP Gate D: No Execution Symbols")
    print("=" * 60)
    print()

    # Scan all answer-related Python files
    answer_files = [
        PROJECT_ROOT / "agentos/core/answers/answer_store.py",
        PROJECT_ROOT / "agentos/core/answers/answer_validator.py",
        PROJECT_ROOT / "agentos/core/answers/answer_applier.py",
        PROJECT_ROOT / "agentos/core/answers/__init__.py",
        PROJECT_ROOT / "agentos/cli/answers.py",
    ]

    print("[1] Scanning AnswerPack code for execution symbols")
    
    global EXIT_CODE
    total_findings = 0
    
    for file_path in answer_files:
        if not file_path.exists():
            print(f"  ! {file_path.name}: File not found (skipping)")
            continue
        
        findings = scan_file(file_path)
        
        if findings:
            print(f"  ✗ {file_path.name}: {len(findings)} dangerous pattern(s) found")
            for line_num, pattern_name, line_content in findings:
                print(f"      Line {line_num}: {pattern_name}")
                print(f"        {line_content[:80]}")
            EXIT_CODE = 1
            total_findings += len(findings)
        else:
            print(f"  ✓ {file_path.name}: Clean")
    
    print()

    # Summary
    print("=" * 60)
    if EXIT_CODE == 0:
        print("✓ AP GATE D PASSED: No execution symbols found")
    else:
        print(f"✗ AP GATE D FAILED: {total_findings} dangerous pattern(s) detected")
        print("  AnswerPack code must not execute shell commands or dynamic code")
    print("=" * 60)

    return EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
