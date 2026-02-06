#!/usr/bin/env python3
"""
P2 Migration Runner: Add Decision Records Tables
Date: 2026-01-31
Purpose: Execute schema v36 migration to add decision_records and decision_signoffs tables
"""

import sqlite3
import sys
import os
from pathlib import Path
from datetime import datetime


def get_db_path():
    """Get database path from environment variable or project root."""
    env_path = os.getenv("AGENTOS_DB_PATH")
    if env_path:
        db_path = Path(env_path).resolve()
        if db_path.exists():
            return str(db_path)

    project_root = Path(__file__).parent.parent.parent.parent
    db_path = project_root / "store" / "registry.sqlite"

    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found. Tried:\n"
            f"  - Environment: {env_path}\n"
            f"  - Project root: {db_path}"
        )

    return str(db_path)


def check_migration_status(cursor):
    """Check if migration has already been applied."""
    cursor.execute(
        "SELECT status FROM schema_migrations WHERE migration_id = ?",
        ('v36_decision_records',)
    )
    result = cursor.fetchone()
    return result[0] if result else None


def run_migration(db_path: str, migration_sql_path: Path):
    """Execute the migration SQL script."""
    print("=" * 80)
    print("P2 Migration: Add Decision Records Tables")
    print("=" * 80)
    print(f"Database: {db_path}")
    print(f"Migration SQL: {migration_sql_path}")
    print()

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if migration already applied
        status = check_migration_status(cursor)
        if status == 'success':
            print("✓ Migration already applied successfully")
            return 0

        # Read migration SQL
        with open(migration_sql_path, 'r') as f:
            migration_sql = f.read()

        # Execute migration
        print("Executing migration...")
        cursor.executescript(migration_sql)
        conn.commit()

        # Verify tables created
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='decision_records'"
        )
        if not cursor.fetchone():
            raise RuntimeError("Migration failed: decision_records table not created")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='decision_signoffs'"
        )
        if not cursor.fetchone():
            raise RuntimeError("Migration failed: decision_signoffs table not created")

        print("✓ Migration completed successfully")
        print()
        print("Tables created:")
        print("  - decision_records")
        print("  - decision_signoffs")
        print()
        return 0

    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        return 1

    finally:
        conn.close()


def main():
    """Main entry point."""
    try:
        # Get database path
        db_path = get_db_path()

        # Get migration SQL path
        script_dir = Path(__file__).parent
        migration_sql_path = script_dir / "schema_v36_decision_records.sql"

        if not migration_sql_path.exists():
            print(f"✗ Migration SQL not found: {migration_sql_path}")
            return 1

        # Run migration
        return run_migration(db_path, migration_sql_path)

    except Exception as e:
        print(f"✗ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
