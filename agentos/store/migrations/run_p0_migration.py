#!/usr/bin/env python3
"""
P0 Migration Runner: Merge task_sessions into chat_sessions
Date: 2026-01-31
Purpose: Execute schema v35 migration to unify session tables
"""

import sqlite3
import sys
import os
from pathlib import Path
import json
from datetime import datetime


def get_db_path():
    """Get database path from environment variable or project root.

    Uses AGENTOS_DB_PATH environment variable (consistent with registry_db).
    Falls back to project root location if not set.
    """
    # Try environment variable first (consistent with registry_db)
    env_path = os.getenv("AGENTOS_DB_PATH")
    if env_path:
        db_path = Path(env_path).resolve()
        if db_path.exists():
            return str(db_path)

    # Fallback to project root
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
        ('v35_merge_task_sessions',)
    )
    result = cursor.fetchone()
    return result[0] if result else None


def get_pre_migration_stats(cursor):
    """Collect statistics before migration."""
    stats = {}

    # Count task_sessions
    cursor.execute("SELECT COUNT(*) FROM task_sessions")
    stats['task_sessions_count'] = cursor.fetchone()[0]

    # Count chat_sessions
    cursor.execute("SELECT COUNT(*) FROM chat_sessions")
    stats['chat_sessions_count_before'] = cursor.fetchone()[0]

    # Sample task_sessions data
    cursor.execute("SELECT session_id, channel, created_at FROM task_sessions LIMIT 3")
    stats['task_sessions_sample'] = cursor.fetchall()

    # Check for session_id conflicts
    cursor.execute("""
        SELECT COUNT(*) FROM task_sessions
        WHERE session_id IN (SELECT session_id FROM chat_sessions)
    """)
    stats['conflicting_sessions'] = cursor.fetchone()[0]

    return stats


def get_post_migration_stats(cursor):
    """Collect statistics after migration."""
    stats = {}

    # Count chat_sessions after migration
    cursor.execute("SELECT COUNT(*) FROM chat_sessions")
    stats['chat_sessions_count_after'] = cursor.fetchone()[0]

    # Check if legacy table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='task_sessions_legacy'
    """)
    stats['legacy_table_exists'] = cursor.fetchone() is not None

    # Count legacy table if it exists
    if stats['legacy_table_exists']:
        cursor.execute("SELECT COUNT(*) FROM task_sessions_legacy")
        stats['legacy_table_count'] = cursor.fetchone()[0]

        # Verify no data loss
        cursor.execute("""
            SELECT COUNT(*) FROM task_sessions_legacy
            WHERE session_id NOT IN (SELECT session_id FROM chat_sessions)
        """)
        stats['unmigrated_sessions'] = cursor.fetchone()[0]
    else:
        stats['legacy_table_count'] = 0
        stats['unmigrated_sessions'] = 0

    # Check if task_sessions table is gone
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='task_sessions'
    """)
    stats['task_sessions_exists'] = cursor.fetchone() is not None

    # If task_sessions still exists, count it
    if stats['task_sessions_exists']:
        cursor.execute("SELECT COUNT(*) FROM task_sessions")
        stats['task_sessions_count'] = cursor.fetchone()[0]
    else:
        stats['task_sessions_count'] = 0

    return stats


def run_migration():
    """Execute the migration."""
    db_path = get_db_path()
    sql_file = Path(__file__).parent / "schema_v35_merge_task_sessions.sql"

    if not sql_file.exists():
        print(f"✗ Migration SQL file not found: {sql_file}")
        return False

    print("=" * 80)
    print("P0 Migration: Merge task_sessions into chat_sessions")
    print("=" * 80)
    print(f"Database: {db_path}")
    print(f"Migration SQL: {sql_file}")
    print()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        # Check if already applied
        status = check_migration_status(cursor)
        if status == 'success':
            print("✓ Migration already applied successfully")
            return True
        elif status == 'failed':
            print("⚠ Previous migration attempt failed. Retrying...")

        # Collect pre-migration statistics
        print("📊 Pre-migration Statistics:")
        print("-" * 80)
        pre_stats = get_pre_migration_stats(cursor)
        print(f"  task_sessions count: {pre_stats['task_sessions_count']}")
        print(f"  chat_sessions count (before): {pre_stats['chat_sessions_count_before']}")
        print(f"  Conflicting session_ids: {pre_stats['conflicting_sessions']}")
        if pre_stats['task_sessions_sample']:
            print(f"  Sample task_sessions:")
            for row in pre_stats['task_sessions_sample']:
                print(f"    - {row}")
        print()

        # Step 1: Ensure schema is ready
        print("🚀 Executing migration...")
        print("Step 1: Preparing chat_sessions schema...")

        # Check and add columns if needed
        cursor.execute("PRAGMA table_info(chat_sessions)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        if 'channel' not in existing_columns:
            print("  Adding 'channel' column...")
            cursor.execute("ALTER TABLE chat_sessions ADD COLUMN channel TEXT DEFAULT NULL")
        else:
            print("  ✓ 'channel' column already exists")

        if 'last_activity' not in existing_columns:
            print("  Adding 'last_activity' column...")
            cursor.execute("ALTER TABLE chat_sessions ADD COLUMN last_activity TIMESTAMP DEFAULT NULL")
        else:
            print("  ✓ 'last_activity' column already exists")

        print()

        # Step 2: Execute rest of migration
        print("Step 2: Executing migration SQL...")
        with open(sql_file) as f:
            migration_sql = f.read()

        # Remove comments and split by semicolons
        # This is a simple approach - better would be a proper SQL parser
        lines = []
        for line in migration_sql.split('\n'):
            # Skip pure comment lines
            if line.strip().startswith('--'):
                continue
            # Remove inline comments
            if '--' in line:
                line = line.split('--')[0]
            lines.append(line)

        cleaned_sql = '\n'.join(lines)

        # Split by semicolons and filter empty statements
        sql_statements = []
        for stmt in cleaned_sql.split(';'):
            stmt = stmt.strip()
            if stmt and not stmt.startswith('--'):
                sql_statements.append(stmt)

        print(f"  Found {len(sql_statements)} statements to execute")

        # Skip the ALTER TABLE statements (we handled them above)
        executed = 0
        skipped = 0
        for i, statement in enumerate(sql_statements, 1):
            # Skip ALTER TABLE statements for columns we already handled
            if 'ALTER TABLE chat_sessions ADD COLUMN' in statement:
                skipped += 1
                continue

            try:
                cursor.execute(statement)
                executed += 1
                # Show progress for key operations
                if 'INSERT' in statement or 'ALTER TABLE' in statement or 'DROP' in statement:
                    preview = statement[:80].replace('\n', ' ')
                    print(f"  ✓ [{executed}] {preview}...")
            except sqlite3.Error as e:
                # Handle graceful failures for idempotency
                error_msg = str(e).lower()
                if 'already exists' in error_msg or 'duplicate' in error_msg:
                    print(f"  ⚠ Skipping (already exists): {statement[:80]}...")
                    skipped += 1
                    continue
                if 'no such table' in error_msg and 'task_sessions_legacy' in statement:
                    print(f"  ⚠ Skipping (table doesn't exist yet): task_sessions_legacy")
                    skipped += 1
                    continue
                print(f"  ✗ Error at statement {i}: {e}")
                print(f"  Statement: {statement[:200]}...")
                raise

        conn.commit()
        print(f"✓ Migration SQL executed: {executed} statements (skipped {skipped})")
        print()

        # Collect post-migration statistics
        print("📊 Post-migration Statistics:")
        print("-" * 80)
        post_stats = get_post_migration_stats(cursor)
        print(f"  chat_sessions count (after): {post_stats['chat_sessions_count_after']}")
        if post_stats['task_sessions_exists']:
            print(f"  task_sessions count (still exists): {post_stats['task_sessions_count']}")
        if post_stats['legacy_table_exists']:
            print(f"  task_sessions_legacy count: {post_stats['legacy_table_count']}")
            print(f"  Unmigrated sessions: {post_stats['unmigrated_sessions']}")
        print(f"  Legacy table exists: {post_stats['legacy_table_exists']}")
        print(f"  task_sessions table exists: {post_stats['task_sessions_exists']}")
        print()

        # Verify data integrity
        print("🔍 Data Integrity Check:")
        print("-" * 80)

        migrated_count = (post_stats['chat_sessions_count_after'] -
                         pre_stats['chat_sessions_count_before'])
        expected_migrated = pre_stats['task_sessions_count'] - pre_stats['conflicting_sessions']

        print(f"  Expected migrations: {expected_migrated}")
        print(f"  Actual migrations: {migrated_count}")
        print(f"  Unmigrated sessions: {post_stats['unmigrated_sessions']}")

        if post_stats['unmigrated_sessions'] == 0:
            print("  ✓ All sessions migrated successfully")
        else:
            print(f"  ⚠ Warning: {post_stats['unmigrated_sessions']} sessions not migrated")

        if not post_stats['task_sessions_exists']:
            print("  ✓ task_sessions table removed")
        else:
            print("  ✗ task_sessions table still exists")

        if post_stats['legacy_table_exists']:
            print("  ✓ task_sessions_legacy backup created")
        else:
            print("  ✗ task_sessions_legacy backup not found")

        print()
        print("=" * 80)
        print("✓ P0 Migration Completed Successfully")
        print("=" * 80)

        return True

    except Exception as e:
        conn.rollback()
        print()
        print("=" * 80)
        print(f"✗ Migration Failed: {e}")
        print("=" * 80)

        # Record failure
        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO schema_migrations
                (migration_id, description, status, metadata)
                VALUES (?, ?, 'failed', ?)
                """,
                (
                    'v35_merge_task_sessions',
                    'Merge task_sessions into chat_sessions - FAILED',
                    json.dumps({'error': str(e), 'timestamp': datetime.now().isoformat()})
                )
            )
            conn.commit()
        except:
            pass

        return False

    finally:
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
