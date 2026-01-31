#!/usr/bin/env python3
"""Gate: Prevent database connection closing issues

This script prevents the anti-pattern of closing connections obtained from get_db().
The get_db() function returns a shared connection that should NOT be closed by callers.

Exit codes:
- 0: Success (no violations found)
- 1: Violations found

Usage:
    python scripts/gates/gate_db_close_guard.py
    python scripts/gates/gate_db_close_guard.py --fix  # Show fix suggestions
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Set

# Root directory for scanning
ROOT_DIR = Path(__file__).parent.parent.parent / "agentos"

# Directories to scan
SCAN_DIRS = [
    "agentos/store",
    "agentos/router",
    "agentos/core/supervisor",
    "agentos/webui/api",
]

# Directories to exclude from scanning
EXCLUDE_PATHS = {
    "tests",
    "test",
    "migrations",
    "scripts",
    "__pycache__",
    ".git",
    ".pytest_cache",
    "venv",
    "env",
    ".venv",
}


class Violation:
    """Represents a single violation"""
    def __init__(self, file_path: Path, line_num: int, line_content: str,
                 has_get_db: bool, context_lines: List[Tuple[int, str]]):
        self.file_path = file_path
        self.line_num = line_num
        self.line_content = line_content
        self.has_get_db = has_get_db
        self.context_lines = context_lines


def should_exclude_path(path: Path) -> bool:
    """Check if path should be excluded from scanning"""
    return any(excluded in path.parts for excluded in EXCLUDE_PATHS)


def imports_get_db(content: str) -> bool:
    """Check if file imports get_db function"""
    # Match 'get_db' as a whole word, not as part of 'get_db_path' etc.
    patterns = [
        r'from\s+.*\s+import\s+.*\bget_db\b',
        r'import\s+.*\bget_db\b',
    ]

    for pattern in patterns:
        if re.search(pattern, content):
            return True
    return False


def find_function_start(lines: List[str], close_line_idx: int) -> int:
    """
    Find the start of the function containing the close() call.
    Returns the line index of the function definition, or 0 if not found.
    """
    # Look backwards for a 'def ' or 'async def ' statement
    for i in range(close_line_idx - 1, -1, -1):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith('def ') or stripped.startswith('async def '):
            return i
    return 0


def is_explicit_sqlite_scope(lines: List[str], close_line_idx: int, context: int = 50) -> bool:
    """
    Check if .close() is in an explicit sqlite3.connect() scope.

    Returns True if we find sqlite3.connect() within the SAME FUNCTION
    and no get_db() calls in that function.

    Also returns True if the variable being closed was assigned from a method
    call that creates a new connection (like registry._get_connection()).

    Special case: If the close() is inside a conditional block that checks
    for self.db_path or similar (indicating custom DB mode), it's safe.
    """
    # Find the function start to avoid picking up code from other functions
    func_start_idx = find_function_start(lines, close_line_idx)

    # Use the entire function scope, not just a context window
    # This ensures we don't miss sqlite3.connect() calls at the start of long functions
    start_idx = func_start_idx
    scope_lines = lines[start_idx:close_line_idx + 1]

    # Filter out comments when checking for get_db calls
    code_lines = []
    for line in scope_lines:
        # Remove comments from line
        if '#' in line:
            line = line[:line.index('#')]
        code_lines.append(line)

    scope_text = "\n".join(scope_lines)
    code_text = "\n".join(code_lines)

    # Check for direct sqlite3.connect in the scope
    has_sqlite_connect = bool(re.search(r'sqlite3\.connect\s*\(', scope_text))

    # Check for _get_connection() which creates new connections
    has_get_connection = bool(re.search(r'\._get_connection\s*\(', scope_text))

    # Check for get_db in the scope (problematic) - only in actual code, not comments
    # Use word boundary to match 'get_db()' but not 'get_db_path()'
    has_get_db = bool(re.search(r'\bget_db\s*\(', code_text))

    # Special case: Check if close() is inside a conditional branch
    # that guards against using shared connection (e.g., "if self.db_path:")
    # Look backwards from close() to find the nearest if/elif/else
    close_block_lines = []
    # Get the indentation level of the close() call
    close_line = lines[close_line_idx] if close_line_idx < len(lines) else ""
    indent_level = len(close_line) - len(close_line.lstrip()) if close_line else 0

    for i in range(close_line_idx - 1, max(func_start_idx - 1, close_line_idx - 30), -1):
        line = lines[i]
        stripped = line.strip()

        # Found a conditional block at the same or lower indentation
        current_indent = len(line) - len(line.lstrip())
        if current_indent < indent_level and (stripped.startswith('if ') or stripped.startswith('elif ')):
            close_block_lines.append(line)
            # Check if this conditional guards for custom DB mode
            if 'self.db_path' in line or 'db_path' in line:
                # This close() is inside a custom DB path branch, it's safe
                return True
            break

        close_block_lines.append(line)

    # If we have sqlite3.connect or _get_connection and no get_db, it's likely safe
    return (has_sqlite_connect or has_get_connection) and not has_get_db


def scan_file(file_path: Path) -> List[Violation]:
    """
    Scan a single file for violations.

    A violation is:
    1. File imports get_db or "from ... import get_db"
    2. File contains .close() call
    3. The .close() is NOT in an explicit sqlite3.connect scope
    """
    violations = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split("\n")

        # Check if file imports get_db
        has_get_db_import = imports_get_db(content)

        # Find all .close() calls
        for line_num, line in enumerate(lines, start=1):
            # Skip comments and docstrings
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue

            # Look for .close() pattern
            if re.search(r'\.close\s*\(', line):
                # Skip if it's explicitly a file handle close
                if 'file' in line.lower() or 'lock_file' in line.lower() or 'sock' in line.lower():
                    continue

                # Skip if it's a process handle close
                if 'stdout.close()' in line or 'stderr.close()' in line:
                    continue

                # Check if it's in an explicit sqlite3.connect scope
                in_sqlite_scope = is_explicit_sqlite_scope(lines, line_num - 1)

                # If file imports get_db and .close() is NOT in sqlite scope, it's a violation
                if has_get_db_import and not in_sqlite_scope:
                    # Get context lines
                    context_start = max(0, line_num - 5)
                    context_end = min(len(lines), line_num + 3)
                    context_lines = [
                        (i + 1, lines[i])
                        for i in range(context_start, context_end)
                    ]

                    violations.append(Violation(
                        file_path=file_path,
                        line_num=line_num,
                        line_content=line.strip(),
                        has_get_db=has_get_db_import,
                        context_lines=context_lines
                    ))

    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)

    return violations


def scan_directories() -> Dict[Path, List[Violation]]:
    """Scan all configured directories for violations"""
    all_violations = {}

    root = Path(__file__).parent.parent.parent

    for scan_dir in SCAN_DIRS:
        scan_path = root / scan_dir

        if not scan_path.exists():
            continue

        for py_file in scan_path.rglob("*.py"):
            # Skip excluded paths
            if should_exclude_path(py_file):
                continue

            violations = scan_file(py_file)
            if violations:
                all_violations[py_file] = violations

    return all_violations


def print_report(violations: Dict[Path, List[Violation]], show_fix: bool = False) -> None:
    """Print detailed violation report"""
    print("=" * 80)
    print("DB Connection Close Guard Gate")
    print("=" * 80)
    print()

    if not violations:
        print("✓ PASS: No violations found")
        print()
        print("All files correctly avoid closing get_db() connections.")
        return

    total_violations = sum(len(v) for v in violations.values())
    print(f"✗ FAIL: Found {total_violations} violation(s) in {len(violations)} file(s)")
    print()

    # Detailed violations
    for file_path, file_violations in sorted(violations.items()):
        rel_path = file_path.relative_to(Path(__file__).parent.parent.parent)
        print(f"File: {rel_path}")
        print()

        for violation in file_violations:
            print(f"  Line {violation.line_num}: {violation.line_content}")
            print()
            print("  Context:")
            for ctx_line_num, ctx_line in violation.context_lines:
                marker = ">>>" if ctx_line_num == violation.line_num else "   "
                print(f"  {marker} {ctx_line_num:4d} | {ctx_line}")
            print()

            if show_fix:
                print("  Fix suggestion:")
                if "self.db_path" in "\n".join(line for _, line in violation.context_lines):
                    print("    - This appears to be in a custom db_path scope")
                    print("    - If using get_db(), use transaction() context manager:")
                    print("      from agentos.core.db.registry_db import transaction")
                    print("      with transaction() as conn:")
                    print("          # ... do work")
                    print("          # NO conn.close() needed!")
                else:
                    print("    - Replace with transaction() context manager:")
                    print("      from agentos.core.db.registry_db import transaction")
                    print("      with transaction() as conn:")
                    print("          cursor = conn.cursor()")
                    print("          # ... do work")
                    print("          # NO conn.close() needed!")
                print()

        print("-" * 80)
        print()

    print("=" * 80)
    print("Required Actions:")
    print("=" * 80)
    print()
    print("DO NOT close connections from get_db()!")
    print()
    print("Instead, use one of these patterns:")
    print()
    print("1. Use transaction() context manager (RECOMMENDED):")
    print("   from agentos.core.db.registry_db import transaction")
    print("   with transaction() as conn:")
    print("       cursor = conn.cursor()")
    print("       # ... do work")
    print("       # Connection is automatically managed")
    print()
    print("2. If you need to use sqlite3.connect() directly:")
    print("   conn = sqlite3.connect(db_path)")
    print("   try:")
    print("       # ... do work")
    print("   finally:")
    print("       conn.close()  # OK: you created it, you close it")
    print()
    print("3. NEVER do this:")
    print("   conn = get_db()")
    print("   # ... do work")
    print("   conn.close()  # WRONG: get_db() returns shared connection!")
    print()


def main() -> int:
    """Main entry point"""
    show_fix = "--fix" in sys.argv

    print(f"Scanning directories: {', '.join(SCAN_DIRS)}")
    print(f"Excluded paths: {', '.join(EXCLUDE_PATHS)}")
    print()

    # Scan for violations
    violations = scan_directories()

    # Print report
    print_report(violations, show_fix=show_fix)

    # Return exit code
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
