#!/usr/bin/env python3
"""
Gate: Enforce Time & Timestamp Contract

Prevents regression of forbidden datetime usage:
1. datetime.utcnow() - deprecated in Python 3.12+
2. datetime.now() without timezone parameter
3. Direct timestamp creation without UTC awareness

Ensures all code uses agentos.core.time.clock module.

Exit codes:
- 0: Success (no violations found)
- 1: Violations found

Usage:
    python scripts/gates/gate_datetime_usage.py
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict

# Root directory for scanning
ROOT_DIR = Path(__file__).parent.parent.parent / "agentos"

# Whitelist: Files that are allowed to use datetime directly
WHITELIST = {
    # Core clock module itself (implements utc_now)
    "agentos/core/time/clock.py",
    "agentos/core/time/__init__.py",

    # Test files that test datetime behavior
    "agentos/core/time/test_clock.py",
}

# Directories to exclude from scanning
EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    "node_modules",
    ".venv",
    "venv",
}

# Patterns to detect
PATTERNS = {
    "utcnow": re.compile(r'\bdatetime\.utcnow\s*\('),
    "now_no_tz": re.compile(r'\bdatetime\.now\s*\(\s*\)'),  # datetime.now() with no args
}


class DatetimeViolation:
    """Represents a datetime usage violation"""

    def __init__(self, file_path: Path, line_num: int, line_content: str, violation_type: str):
        self.file_path = file_path
        self.line_num = line_num
        self.line_content = line_content.strip()
        self.violation_type = violation_type

    def __str__(self):
        return f"  {self.file_path.relative_to(ROOT_DIR.parent)}:{self.line_num}\n    {self.line_content}"


def should_skip_file(file_path: Path) -> bool:
    """Check if file should be skipped"""
    # Skip if in whitelist
    try:
        rel_path = str(file_path.relative_to(ROOT_DIR.parent))
        if rel_path in WHITELIST:
            return True
    except ValueError:
        pass

    # Skip if in excluded directory
    for part in file_path.parts:
        if part in EXCLUDE_DIRS:
            return True

    # Skip non-Python files
    if file_path.suffix != ".py":
        return True

    return False


def check_file(file_path: Path) -> List[DatetimeViolation]:
    """Check a single file for datetime violations"""
    violations = []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, start=1):
                # Skip comments
                if line.strip().startswith('#'):
                    continue

                # Check for datetime.utcnow()
                if PATTERNS["utcnow"].search(line):
                    violations.append(DatetimeViolation(
                        file_path, line_num, line, "datetime.utcnow()"
                    ))

                # Check for datetime.now() without timezone
                if PATTERNS["now_no_tz"].search(line):
                    # Make sure it's not datetime.now(tz=...) or datetime.now(timezone.utc)
                    # Only flag bare datetime.now()
                    if 'tz=' not in line and 'timezone' not in line:
                        violations.append(DatetimeViolation(
                            file_path, line_num, line, "datetime.now() without timezone"
                        ))

    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)

    return violations


def scan_directory(root: Path) -> Dict[str, List[DatetimeViolation]]:
    """Scan directory recursively for violations"""
    violations_by_type = {
        "datetime.utcnow()": [],
        "datetime.now() without timezone": [],
    }

    for file_path in root.rglob("*.py"):
        if should_skip_file(file_path):
            continue

        file_violations = check_file(file_path)
        for violation in file_violations:
            violations_by_type[violation.violation_type].append(violation)

    return violations_by_type


def print_report(violations_by_type: Dict[str, List[DatetimeViolation]]) -> bool:
    """Print report and return True if violations found"""
    total_violations = sum(len(v) for v in violations_by_type.values())

    print("=" * 80)
    print("Time & Timestamp Contract Enforcement")
    print("=" * 80)
    print()

    if total_violations == 0:
        print("✅ SUCCESS: No datetime usage violations found!")
        print()
        print("All code follows the Time & Timestamp Contract:")
        print("  - No datetime.utcnow() usage (deprecated)")
        print("  - No datetime.now() without timezone")
        print("  - All timestamps use agentos.core.time.clock module")
        print()
        return False

    print(f"❌ VIOLATIONS FOUND: {total_violations} datetime usage violations")
    print()

    # Report by violation type
    for violation_type, violations in violations_by_type.items():
        if not violations:
            continue

        print(f"{'=' * 80}")
        print(f"Violation: {violation_type}")
        print(f"Count: {len(violations)}")
        print(f"{'=' * 80}")
        print()

        for violation in violations:
            print(violation)

        print()

    # Print remediation instructions
    print("=" * 80)
    print("How to Fix")
    print("=" * 80)
    print()
    print("Replace forbidden patterns with clock module:")
    print()
    print("  Before:")
    print("    from datetime import datetime")
    print("    timestamp = datetime.utcnow()")
    print("    timestamp = datetime.now()")
    print()
    print("  After:")
    print("    from agentos.core.time import utc_now")
    print("    timestamp = utc_now()")
    print()
    print("Additional helpers:")
    print("  - utc_now_ms() -> int (epoch milliseconds)")
    print("  - utc_now_iso() -> str (ISO 8601 with Z suffix)")
    print("  - from_epoch_ms(ms) -> datetime")
    print("  - to_epoch_ms(dt) -> int")
    print()
    print("See: agentos/core/time/clock.py")
    print()

    return True


def main():
    """Main gate execution"""
    if not ROOT_DIR.exists():
        print(f"Error: Root directory not found: {ROOT_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning: {ROOT_DIR}")
    print()

    violations_by_type = scan_directory(ROOT_DIR)
    has_violations = print_report(violations_by_type)

    if has_violations:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
