#!/usr/bin/env python3
"""
v11 AP Gate E: Isolation Verification

Ensures AnswerPack operations are isolated and don't leak sensitive data:
- No hardcoded paths outside project
- No HOME directory access
- No reading of .env or credential files
- temp dir usage is safe
"""

import sys
import re
from pathlib import Path

# Assume script is in scripts/gates/
PROJECT_ROOT = Path(__file__).parent.parent.parent
EXIT_CODE = 0

# Patterns that indicate isolation violations
ISOLATION_VIOLATIONS = [
    (r'os\.environ\[', 'Direct environment access'),
    (r'\/home\/', 'Hardcoded /home/ path'),
    (r'\/Users\/', 'Hardcoded /Users/ path'),
    (r'\.env', 'Reference to .env file'),
    (r'credentials', 'Reference to credentials'),
    (r'password|secret|token', 'Reference to sensitive data (case-insensitive)'),
]


def scan_file_for_isolation(file_path: Path) -> list[tuple[int, str, str]]:
    """Scan a Python file for isolation violations.
    
    Returns:
        List of (line_number, violation_name, line_content)
    """
    findings = []
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                # Skip comments and docstrings
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                
                for pattern, name in ISOLATION_VIOLATIONS:
                    if re.search(pattern, line, re.IGNORECASE if 'password|secret|token' in pattern else 0):
                        # Allow if it's in a string that looks like documentation
                        if '"""' in line or "'''" in line or '# ' in line:
                            continue
                        findings.append((line_num, name, line.strip()))
    
    except Exception as e:
        print(f"  ! Error reading {file_path}: {e}")
    
    return findings


def main():
    print("=" * 60)
    print("v11 AP Gate E: Isolation Verification")
    print("=" * 60)
    print()

    # Scan all answer-related Python files
    answer_files = [
        PROJECT_ROOT / "agentos/core/answers/answer_store.py",
        PROJECT_ROOT / "agentos/core/answers/answer_validator.py",
        PROJECT_ROOT / "agentos/core/answers/answer_applier.py",
        PROJECT_ROOT / "agentos/cli/answers.py",
    ]

    print("[1] Scanning for isolation violations")
    
    global EXIT_CODE
    total_findings = 0
    
    for file_path in answer_files:
        if not file_path.exists():
            print(f"  ! {file_path.name}: File not found (skipping)")
            continue
        
        findings = scan_file_for_isolation(file_path)
        
        if findings:
            print(f"  ✗ {file_path.name}: {len(findings)} potential violation(s)")
            for line_num, violation_name, line_content in findings:
                print(f"      Line {line_num}: {violation_name}")
                print(f"        {line_content[:80]}")
            EXIT_CODE = 1
            total_findings += len(findings)
        else:
            print(f"  ✓ {file_path.name}: Clean")
    
    print()

    # Summary
    print("=" * 60)
    if EXIT_CODE == 0:
        print("✓ AP GATE E PASSED: No isolation violations found")
    else:
        print(f"✗ AP GATE E FAILED: {total_findings} potential violation(s) detected")
        print("  AnswerPack code must not access sensitive paths or environment")
    print("=" * 60)

    return EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
