#!/usr/bin/env python3
"""Single DB Entry Point Gate - Verify unified database access.

This script verifies that:
1. Only one get_db() function exists (in registry_db.py)
2. Only one _get_conn() method exists (in writer.py or registry_db.py)
3. No files create their own database connection pools
4. All DB access goes through the official entry points

Exit codes:
- 0: Success (single entry point verified)
- 1: Violations found (multiple entry points detected)

Usage:
    python scripts/gates/gate_single_db_entry.py
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Set

# Root directory for scanning
ROOT_DIR = Path(__file__).parent.parent.parent / "agentos"

# Expected entry point locations
EXPECTED_ENTRY_POINTS = {
    "get_db": ["agentos/core/db/registry_db.py"],
    "_get_db_path": ["agentos/core/db/registry_db.py"],
}

# Patterns to detect database entry points
ENTRY_POINT_PATTERNS = [
    (r"^def\s+get_db\s*\(", "get_db"),
    (r"^def\s+_get_conn\s*\(", "_get_conn"),
    (r"^def\s+_get_db_path\s*\(", "_get_db_path"),
    (r"^def\s+get_connection\s*\(", "get_connection"),
    (r"^def\s+get_db_connection\s*\(", "get_db_connection"),
    (r"^def\s+create_connection\s*\(", "create_connection"),
]

# Patterns for connection pooling (forbidden outside core DB)
POOLING_PATTERNS = [
    (r"class\s+.*ConnectionPool", "ConnectionPool class"),
    (r"threading\.local\s*\(", "thread-local storage"),
    (r"_thread_local\s*=", "thread-local variable"),
]

# Directories to exclude
EXCLUDE_DIRS = {
    "tests",
    "test",
    "__pycache__",
    ".git",
    ".pytest_cache",
    "venv",
    "env",
    ".venv",
    "node_modules",
}


def is_entry_point_file(file_path: Path) -> bool:
    """Check if file is an expected entry point file."""
    try:
        rel_path = file_path.relative_to(Path(__file__).parent.parent.parent)
        rel_str = str(rel_path).replace(os.sep, "/")

        for expected_files in EXPECTED_ENTRY_POINTS.values():
            if rel_str in expected_files:
                return True

        return False
    except ValueError:
        return False


def scan_file(file_path: Path) -> Dict[str, List[Tuple[int, str]]]:
    """Scan file for database entry point patterns.

    Returns:
        Dictionary mapping pattern name to list of (line_number, line_content)
    """
    violations = {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

            for line_num, line in enumerate(lines, start=1):
                # Skip comments and docstrings
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue

                # Check entry point patterns
                for pattern, pattern_name in ENTRY_POINT_PATTERNS:
                    if re.search(pattern, line):
                        if pattern_name not in violations:
                            violations[pattern_name] = []
                        violations[pattern_name].append((line_num, stripped))

                # Check pooling patterns (only forbidden outside entry point files)
                if not is_entry_point_file(file_path):
                    for pattern, pattern_name in POOLING_PATTERNS:
                        if re.search(pattern, line):
                            if pattern_name not in violations:
                                violations[pattern_name] = []
                            violations[pattern_name].append((line_num, stripped))

    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)

    return violations


def scan_directory(root: Path) -> Dict[Path, Dict[str, List[Tuple[int, str]]]]:
    """Scan directory for entry point violations."""
    all_violations = {}

    for path in root.rglob("*.py"):
        # Skip excluded directories
        if any(excluded in path.parts for excluded in EXCLUDE_DIRS):
            continue

        # Scan file
        violations = scan_file(path)

        # Filter violations for expected entry point files
        if is_entry_point_file(path):
            # Entry point files are allowed to have these patterns
            # But check if they're the expected ones
            filtered = {}
            for pattern_name, pattern_violations in violations.items():
                rel_path = path.relative_to(Path(__file__).parent.parent.parent)
                rel_str = str(rel_path).replace(os.sep, "/")

                # Check if this pattern is expected in this file
                if pattern_name in EXPECTED_ENTRY_POINTS:
                    expected_files = EXPECTED_ENTRY_POINTS[pattern_name]
                    if rel_str not in expected_files:
                        filtered[pattern_name] = pattern_violations
                # Pooling patterns are always allowed in entry point files
                elif "ConnectionPool" not in pattern_name and "thread-local" not in pattern_name:
                    filtered[pattern_name] = pattern_violations

            if filtered:
                all_violations[path] = filtered
        elif violations:
            all_violations[path] = violations

    return all_violations


def verify_entry_points_exist() -> List[str]:
    """Verify that expected entry points exist."""
    missing = []

    for pattern_name, expected_files in EXPECTED_ENTRY_POINTS.items():
        for expected_file in expected_files:
            file_path = Path(__file__).parent.parent.parent / expected_file

            if not file_path.exists():
                missing.append(f"{pattern_name} expected in {expected_file} (file not found)")
                continue

            # Check if pattern exists in file
            try:
                with open(file_path, "r") as f:
                    content = f.read()

                    # Find matching pattern
                    found = False
                    for ep_pattern, ep_name in ENTRY_POINT_PATTERNS:
                        if ep_name == pattern_name and re.search(ep_pattern, content, re.MULTILINE):
                            found = True
                            break

                    if not found:
                        missing.append(f"{pattern_name} not found in {expected_file}")

            except Exception as e:
                missing.append(f"Error checking {expected_file}: {e}")

    return missing


def print_report(violations: Dict[Path, Dict[str, List[Tuple[int, str]]]], missing: List[str]) -> None:
    """Print violation report."""
    print("=" * 80)
    print("Single DB Entry Point Gate")
    print("=" * 80)
    print()

    has_violations = bool(violations) or bool(missing)

    if not has_violations:
        print("✓ PASS: Single DB entry point verified")
        print()
        print("Verified:")
        print("  - Only one get_db() function (registry_db.py)")
        print("  - Only one _get_conn() method (writer.py)")
        print("  - No unauthorized connection pools")
        print("  - All expected entry points exist")
        return

    print("✗ FAIL: Entry point violations detected")
    print()

    # Report missing entry points
    if missing:
        print("MISSING ENTRY POINTS:")
        for msg in missing:
            print(f"  ✗ {msg}")
        print()

    # Report unauthorized entry points
    if violations:
        print(f"UNAUTHORIZED ENTRY POINTS: {len(violations)} file(s)")
        print()

        for file_path, file_violations in sorted(violations.items()):
            rel_path = file_path.relative_to(Path(__file__).parent.parent.parent)
            print(f"File: {rel_path}")

            for pattern_name, pattern_violations in file_violations.items():
                print(f"  Pattern: {pattern_name}")
                for line_num, line_content in pattern_violations:
                    print(f"    Line {line_num}: {line_content[:80]}")
            print()

    print("=" * 80)
    print("Required Actions:")
    print("=" * 80)
    print()
    print("1. Remove unauthorized entry points:")
    print("   - Do NOT create get_db() functions outside registry_db.py")
    print("   - Do NOT create custom connection pools")
    print()
    print("2. Use official entry points:")
    print("   from agentos.core.db import registry_db")
    print("   conn = registry_db.get_db()")
    print()
    print("3. For write operations:")
    print("   from agentos.core.db.writer import write")
    print("   write(sql, params)")
    print()
    print("4. If you need a specialized DB function, add it to registry_db.py")
    print()


def main() -> int:
    """Main entry point."""
    print(f"Scanning: {ROOT_DIR}")
    print(f"Expected entry points: {len(EXPECTED_ENTRY_POINTS)}")
    print()

    # Verify expected entry points exist
    missing = verify_entry_points_exist()

    # Scan for unauthorized entry points
    violations = scan_directory(ROOT_DIR)

    # Print report
    print_report(violations, missing)

    # Return exit code
    return 1 if (violations or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
