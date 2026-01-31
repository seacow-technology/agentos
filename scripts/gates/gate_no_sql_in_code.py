#!/usr/bin/env python3
"""Migration Gate - Prevent SQL schema changes in code.

This script ensures that all schema changes (CREATE TABLE, ALTER TABLE, etc.)
are done through migration scripts, not directly in code.

All schema modifications must go through:
- agentos/store/migrations/*.py

Exit codes:
- 0: Success (no SQL schema changes in code)
- 1: Violations found

Usage:
    python scripts/gates/gate_no_sql_in_code.py
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict

# Root directory for scanning
ROOT_DIR = Path(__file__).parent.parent.parent / "agentos"

# Forbidden SQL patterns (schema modifications)
FORBIDDEN_SQL_PATTERNS = [
    # Table operations
    (r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS", "CREATE TABLE IF NOT EXISTS"),
    (r"CREATE\s+TABLE", "CREATE TABLE"),
    (r"DROP\s+TABLE", "DROP TABLE"),
    (r"ALTER\s+TABLE.*ADD\s+COLUMN", "ALTER TABLE ADD COLUMN"),
    (r"ALTER\s+TABLE.*DROP\s+COLUMN", "ALTER TABLE DROP COLUMN"),
    (r"ALTER\s+TABLE.*RENAME\s+COLUMN", "ALTER TABLE RENAME COLUMN"),
    (r"ALTER\s+TABLE.*RENAME\s+TO", "ALTER TABLE RENAME TO"),

    # Index operations
    (r"CREATE\s+INDEX", "CREATE INDEX"),
    (r"CREATE\s+UNIQUE\s+INDEX", "CREATE UNIQUE INDEX"),
    (r"DROP\s+INDEX", "DROP INDEX"),

    # Schema introspection that often precedes schema changes
    (r"PRAGMA\s+table_info", "PRAGMA table_info"),
]

# Whitelist: Files/paths that are allowed to contain SQL schema changes
WHITELIST = {
    # Migration system (allowed)
    "agentos/store/migrations",
    "agentos/store/migrator.py",
    "agentos/store/migration",
    "agentos/cli/migrate.py",

    # Test files (allowed)
    "tests/",
    "test_",

    # Schema definition files (read-only, for documentation)
    "agentos/core/brain/store/sqlite_schema.py",

    # Legacy files with embedded schema (to be migrated in future PRs)
    "agentos/store/__init__.py",

    # Module-specific databases (independent from registry.sqlite)
    # CommunicationOS has its own communication.db
    "agentos/core/communication/storage/sqlite_store.py",
    "agentos/core/communication/network_mode.py",

    # DEPRECATED: WebUI sessions (already migrated to registry in v34)
    "agentos/webui/store/session_store.py",

    # PRAGMA table_info for schema version detection (technical debt, acceptable)
    # These files use PRAGMA to detect schema version, not to modify schema
    "agentos/core/lead/adapters/storage.py",
    "agentos/core/supervisor/trace/stats.py",
    "agentos/store/scripts/backfill_audit_decision_fields.py",
}

# Directories to exclude from scanning
EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    "venv",
    "env",
    ".venv",
    "node_modules",
}


def is_whitelisted(file_path: Path) -> bool:
    """Check if file is whitelisted."""
    try:
        rel_path = file_path.relative_to(Path(__file__).parent.parent.parent)
        rel_str = str(rel_path).replace(os.sep, "/")

        # Check if path starts with any whitelist entry
        for allowed in WHITELIST:
            if rel_str.startswith(allowed) or allowed in rel_str:
                return True

        return False
    except ValueError:
        return False


def is_comment_or_docstring(line: str) -> bool:
    """Check if line is a comment or part of docstring."""
    stripped = line.strip()

    # Python comment
    if stripped.startswith("#"):
        return True

    # Docstring markers
    if '"""' in stripped or "'''" in stripped:
        return True

    return False


def scan_file(file_path: Path) -> Dict[str, List[Tuple[int, str]]]:
    """Scan a single file for SQL schema modification patterns.

    Returns:
        Dictionary mapping SQL pattern to list of (line_number, line_content)
    """
    violations = {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

            in_docstring = False
            docstring_marker = None

            for line_num, line in enumerate(lines, start=1):
                stripped = line.strip()

                # Track docstring state
                if '"""' in stripped or "'''" in stripped:
                    marker = '"""' if '"""' in stripped else "'''"
                    if not in_docstring:
                        in_docstring = True
                        docstring_marker = marker
                    elif marker == docstring_marker:
                        in_docstring = False
                        docstring_marker = None
                    continue

                # Skip if in docstring or comment
                if in_docstring or is_comment_or_docstring(line):
                    continue

                # Check for SQL patterns
                for pattern, pattern_name in FORBIDDEN_SQL_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        if pattern_name not in violations:
                            violations[pattern_name] = []
                        violations[pattern_name].append((line_num, stripped))

    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)

    return violations


def scan_directory(root: Path) -> Dict[Path, Dict[str, List[Tuple[int, str]]]]:
    """Scan directory recursively for SQL schema violations."""
    all_violations = {}

    for path in root.rglob("*.py"):
        # Skip excluded directories
        if any(excluded in path.parts for excluded in EXCLUDE_DIRS):
            continue

        # Skip whitelisted files
        if is_whitelisted(path):
            continue

        # Scan file
        violations = scan_file(path)
        if violations:
            all_violations[path] = violations

    return all_violations


def print_report(violations: Dict[Path, Dict[str, List[Tuple[int, str]]]]) -> None:
    """Print violation report."""
    print("=" * 80)
    print("Migration Gate: SQL Schema Changes in Code")
    print("=" * 80)
    print()

    if not violations:
        print("✓ PASS: No SQL schema changes in code")
        print()
        print("All schema modifications are properly contained in migration scripts.")
        return

    print(f"✗ FAIL: Found {len(violations)} file(s) with SQL schema changes")
    print()

    # Summary by SQL pattern
    pattern_counts = {}
    for file_violations in violations.values():
        for pattern in file_violations.keys():
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + len(file_violations[pattern])

    print("SQL Pattern Summary:")
    for pattern, count in sorted(pattern_counts.items(), key=lambda x: -x[1]):
        print(f"  - {pattern}: {count} occurrence(s)")
    print()

    # Detailed violations
    print("Detailed Violations:")
    print()

    for file_path, file_violations in sorted(violations.items()):
        rel_path = file_path.relative_to(Path(__file__).parent.parent.parent)
        print(f"File: {rel_path}")

        for pattern, pattern_violations in file_violations.items():
            print(f"  Pattern: {pattern}")
            for line_num, line_content in pattern_violations:
                print(f"    Line {line_num}: {line_content[:80]}")
        print()

    print("=" * 80)
    print("Required Actions:")
    print("=" * 80)
    print()
    print("1. Move all CREATE TABLE statements to migration scripts:")
    print("   - Create new migration: agentos/store/migrations/00XX_description.py")
    print("   - Use migration template from existing migrations")
    print()
    print("2. Replace inline schema changes with migration-based approach:")
    print("   - Remove CREATE TABLE from code")
    print("   - Add proper migration script")
    print("   - Update migration index")
    print()
    print("3. For initialization code, assume schema already exists via migrations")
    print()
    print("4. If file legitimately needs SQL schema (like schema.py), add to whitelist")
    print()
    print("Migration Script Example:")
    print("------------------------")
    print("""
def upgrade(conn):
    '''Add new feature table.'''
    conn.execute('''
        CREATE TABLE IF NOT EXISTS feature_table (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    ''')
    """)
    print()


def main() -> int:
    """Main entry point."""
    print(f"Scanning: {ROOT_DIR}")
    print(f"Checking for SQL schema changes outside migration scripts")
    print()

    # Scan for violations
    violations = scan_directory(ROOT_DIR)

    # Print report
    print_report(violations)

    # Return exit code
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
