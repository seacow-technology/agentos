#!/usr/bin/env python3
"""Schema Gate - Prevent duplicate session/message tables.

This script checks the database schema to ensure:
1. Only one set of session tables (chat_sessions)
2. Only one set of message tables (chat_messages)
3. No webui_* tables (except _legacy for backwards compatibility)
4. No duplicate table definitions

Exit codes:
- 0: Success (schema is clean)
- 1: Violations found (duplicate tables detected)
- 2: Database not initialized yet (warning, not error)

Usage:
    python scripts/gates/gate_no_duplicate_tables.py
"""

import sqlite3
import sys
from pathlib import Path
from typing import List, Dict, Set

# Database path (default)
DEFAULT_DB_PATH = Path("store/registry.sqlite")


def get_db_path() -> Path:
    """Get database path from environment or default."""
    import os
    env_path = os.getenv("AGENTOS_DB_PATH", str(DEFAULT_DB_PATH))
    return Path(env_path)


def get_all_tables(conn: sqlite3.Connection) -> List[str]:
    """Get all table names from database."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    return [row[0] for row in cursor.fetchall()]


def check_duplicate_session_tables(tables: List[str]) -> List[str]:
    """Check for multiple session tables."""
    session_tables = [
        t for t in tables
        if 'session' in t.lower()
        and not t.endswith('_legacy')
        and not t.endswith('_archive')
    ]

    if len(session_tables) > 1:
        return session_tables
    return []


def check_duplicate_message_tables(tables: List[str]) -> List[str]:
    """Check for multiple message tables."""
    message_tables = [
        t for t in tables
        if 'message' in t.lower()
        and not t.endswith('_legacy')
        and not t.endswith('_archive')
    ]

    if len(message_tables) > 1:
        return message_tables
    return []


def check_webui_tables(tables: List[str]) -> List[str]:
    """Check for webui_* tables (should be legacy only)."""
    webui_tables = [
        t for t in tables
        if t.startswith('webui_')
        and not t.endswith('_legacy')
        and not t.endswith('_archive')
    ]
    return webui_tables


def check_table_name_conflicts(tables: List[str]) -> Dict[str, List[str]]:
    """Check for similar table names that might indicate duplication."""
    conflicts = {}

    # Check for variations of common table names
    base_names = {
        'session': ['session', 'sessions', 'chat_session', 'chat_sessions'],
        'message': ['message', 'messages', 'chat_message', 'chat_messages'],
        'task': ['task', 'tasks'],
        'user': ['user', 'users'],
        'agent': ['agent', 'agents'],
    }

    for base, variations in base_names.items():
        matching = [
            t for t in tables
            for v in variations
            if t.lower() == v and not t.endswith('_legacy')
        ]
        if len(matching) > 1:
            conflicts[base] = matching

    return conflicts


def get_table_schema(conn: sqlite3.Connection, table_name: str) -> str:
    """Get CREATE TABLE statement for a table."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sql FROM sqlite_master
        WHERE type='table' AND name=?
    """, (table_name,))
    row = cursor.fetchone()
    return row[0] if row else ""


def analyze_schema(db_path: Path) -> Dict:
    """Analyze database schema for violations."""
    if not db_path.exists():
        return {
            "status": "not_initialized",
            "message": f"Database not initialized yet: {db_path}"
        }

    conn = sqlite3.connect(db_path)

    try:
        tables = get_all_tables(conn)

        violations = []

        # Check for duplicate session tables
        dup_sessions = check_duplicate_session_tables(tables)
        if dup_sessions:
            violations.append({
                "type": "duplicate_session_tables",
                "tables": dup_sessions,
                "severity": "critical",
                "message": f"Multiple session tables found: {dup_sessions}"
            })

        # Check for duplicate message tables
        dup_messages = check_duplicate_message_tables(tables)
        if dup_messages:
            violations.append({
                "type": "duplicate_message_tables",
                "tables": dup_messages,
                "severity": "critical",
                "message": f"Multiple message tables found: {dup_messages}"
            })

        # Check for non-legacy webui tables
        webui_tables = check_webui_tables(tables)
        if webui_tables:
            violations.append({
                "type": "webui_tables",
                "tables": webui_tables,
                "severity": "high",
                "message": f"Found webui_* tables (should be _legacy): {webui_tables}"
            })

        # Check for name conflicts
        conflicts = check_table_name_conflicts(tables)
        if conflicts:
            for base, matching in conflicts.items():
                violations.append({
                    "type": "table_name_conflict",
                    "tables": matching,
                    "severity": "medium",
                    "message": f"Similar table names for '{base}': {matching}"
                })

        return {
            "status": "checked",
            "total_tables": len(tables),
            "tables": tables,
            "violations": violations
        }

    finally:
        conn.close()


def print_report(analysis: Dict) -> None:
    """Print schema analysis report."""
    print("=" * 80)
    print("Schema Gate: Duplicate Table Detection")
    print("=" * 80)
    print()

    if analysis["status"] == "not_initialized":
        print(f"⚠ WARNING: {analysis['message']}")
        print()
        print("This is not an error. The database will be initialized on first run.")
        return

    print(f"Total tables: {analysis['total_tables']}")
    print()

    violations = analysis.get("violations", [])

    if not violations:
        print("✓ PASS: Schema is clean (single session/message tables)")
        print()
        print("Verified:")
        print("  - No duplicate session tables")
        print("  - No duplicate message tables")
        print("  - No non-legacy webui_* tables")
        print("  - No table name conflicts")
        return

    print(f"✗ FAIL: Found {len(violations)} schema violation(s)")
    print()

    # Group by severity
    critical = [v for v in violations if v["severity"] == "critical"]
    high = [v for v in violations if v["severity"] == "high"]
    medium = [v for v in violations if v["severity"] == "medium"]

    if critical:
        print("CRITICAL VIOLATIONS:")
        for v in critical:
            print(f"  ✗ {v['message']}")
        print()

    if high:
        print("HIGH PRIORITY:")
        for v in high:
            print(f"  ⚠ {v['message']}")
        print()

    if medium:
        print("MEDIUM PRIORITY:")
        for v in medium:
            print(f"  • {v['message']}")
        print()

    print("=" * 80)
    print("Required Actions:")
    print("=" * 80)
    print()
    print("1. Remove duplicate tables - Keep only canonical versions:")
    print("   - chat_sessions (not 'sessions' or 'session')")
    print("   - chat_messages (not 'messages' or 'message')")
    print()
    print("2. Rename webui_* tables to webui_*_legacy if needed for migration")
    print()
    print("3. Create migration script to consolidate data if tables contain different records")
    print()
    print("4. Update code to use canonical table names only")
    print()


def main() -> int:
    """Main entry point."""
    db_path = get_db_path()

    print(f"Checking database schema: {db_path}")
    print()

    analysis = analyze_schema(db_path)
    print_report(analysis)

    # Return exit code
    if analysis["status"] == "not_initialized":
        return 0  # Not an error, just not initialized yet

    violations = analysis.get("violations", [])
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
