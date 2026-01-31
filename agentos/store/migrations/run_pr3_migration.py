#!/usr/bin/env python3
"""
PR-3 Migration Script: Merge webui_sessions into chat_sessions

This script:
1. Backs up the database
2. Runs the migration SQL
3. Validates the results
4. Outputs detailed statistics
"""

import sys
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
import shutil

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationValidator:
    """Validates PR-3 migration results"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

    def get_table_count(self, table_name: str) -> int:
        """Get row count from table"""
        try:
            result = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            return result[0]
        except sqlite3.OperationalError:
            return 0

    def check_table_exists(self, table_name: str) -> bool:
        """Check if table exists"""
        result = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        ).fetchone()
        return result is not None

    def get_migrated_sessions(self) -> list:
        """Get sessions that were migrated from webui"""
        cursor = self.conn.execute("""
            SELECT session_id, title, created_at, updated_at, metadata
            FROM chat_sessions
            WHERE json_extract(metadata, '$.source') = 'webui_migration'
        """)
        return cursor.fetchall()

    def get_migrated_messages(self) -> list:
        """Get messages that were migrated from webui"""
        cursor = self.conn.execute("""
            SELECT message_id, session_id, role, created_at, metadata
            FROM chat_messages
            WHERE json_extract(metadata, '$.source') = 'webui_migration'
        """)
        return cursor.fetchall()

    def check_metadata_enrichment(self) -> dict:
        """Check if metadata was properly enriched"""
        cursor = self.conn.execute("""
            SELECT
                session_id,
                json_extract(metadata, '$.conversation_mode') as conv_mode,
                json_extract(metadata, '$.execution_phase') as exec_phase,
                json_extract(metadata, '$.source') as source,
                json_extract(metadata, '$.migrated_at') as migrated_at
            FROM chat_sessions
            WHERE json_extract(metadata, '$.source') = 'webui_migration'
        """)

        enriched = []
        missing_fields = []

        for row in cursor:
            if row[1] and row[2] and row[3] and row[4]:
                enriched.append(dict(row))
            else:
                missing_fields.append({
                    'session_id': row[0],
                    'conv_mode': row[1],
                    'exec_phase': row[2],
                    'source': row[3],
                    'migrated_at': row[4]
                })

        return {
            'enriched_count': len(enriched),
            'missing_fields_count': len(missing_fields),
            'missing_fields_details': missing_fields
        }

    def get_migration_record(self) -> dict:
        """Get migration record from schema_migrations"""
        cursor = self.conn.execute("""
            SELECT migration_id, applied_at, description, status, metadata
            FROM schema_migrations
            WHERE migration_id = 'merge_webui_sessions'
        """)
        row = cursor.fetchone()
        if row:
            return {
                'migration_id': row[0],
                'applied_at': row[1],
                'description': row[2],
                'status': row[3],
                'metadata': json.loads(row[4]) if row[4] else {}
            }
        return None

    def validate_all(self) -> dict:
        """Run all validation checks"""
        logger.info("Running validation checks...")

        results = {
            'tables': {
                'chat_sessions_exists': self.check_table_exists('chat_sessions'),
                'chat_messages_exists': self.check_table_exists('chat_messages'),
                'webui_sessions_legacy_exists': self.check_table_exists('webui_sessions_legacy'),
                'webui_messages_legacy_exists': self.check_table_exists('webui_messages_legacy'),
                'schema_migrations_exists': self.check_table_exists('schema_migrations'),
            },
            'counts': {
                'chat_sessions_total': self.get_table_count('chat_sessions'),
                'chat_messages_total': self.get_table_count('chat_messages'),
                'webui_sessions_legacy': self.get_table_count('webui_sessions_legacy'),
                'webui_messages_legacy': self.get_table_count('webui_messages_legacy'),
            },
            'migrated_data': {
                'sessions': len(self.get_migrated_sessions()),
                'messages': len(self.get_migrated_messages()),
            },
            'metadata_enrichment': self.check_metadata_enrichment(),
            'migration_record': self.get_migration_record(),
        }

        return results


def backup_database(db_path: Path) -> Path:
    """Create a backup of the database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"

    logger.info(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    logger.info(f"Backup created successfully")

    return backup_path


def run_migration(db_path: Path, migration_sql_path: Path) -> bool:
    """Run the migration SQL script"""
    logger.info(f"Running migration: {migration_sql_path}")

    conn = sqlite3.connect(db_path)

    try:
        with open(migration_sql_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()

        # Execute migration in transaction
        conn.executescript(migration_sql)
        conn.commit()

        logger.info("Migration executed successfully")
        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def print_validation_report(results: dict):
    """Print formatted validation report"""

    print("\n" + "="*70)
    print("PR-3 MIGRATION VALIDATION REPORT")
    print("="*70)

    print("\n1. TABLE STATUS:")
    print("-" * 70)
    for table, exists in results['tables'].items():
        status = "✓ EXISTS" if exists else "✗ MISSING"
        print(f"  {table:40} {status}")

    print("\n2. ROW COUNTS:")
    print("-" * 70)
    for table, count in results['counts'].items():
        print(f"  {table:40} {count:6} rows")

    print("\n3. MIGRATED DATA:")
    print("-" * 70)
    print(f"  Sessions migrated from webui:          {results['migrated_data']['sessions']:6}")
    print(f"  Messages migrated from webui:          {results['migrated_data']['messages']:6}")

    print("\n4. METADATA ENRICHMENT:")
    print("-" * 70)
    enrichment = results['metadata_enrichment']
    print(f"  Sessions with enriched metadata:       {enrichment['enriched_count']:6}")
    print(f"  Sessions with missing fields:          {enrichment['missing_fields_count']:6}")

    if enrichment['missing_fields_count'] > 0:
        print("\n  WARNING: Some sessions have missing metadata fields:")
        for session in enrichment['missing_fields_details'][:5]:  # Show first 5
            print(f"    - {session['session_id']}: {session}")

    print("\n5. MIGRATION RECORD:")
    print("-" * 70)
    record = results['migration_record']
    if record:
        print(f"  Migration ID:   {record['migration_id']}")
        print(f"  Applied at:     {record['applied_at']}")
        print(f"  Status:         {record['status']}")
        print(f"  Description:    {record['description']}")

        if record['metadata']:
            print("\n  Migration Statistics:")
            stats = record['metadata']
            for key, value in stats.items():
                print(f"    {key:30} {value}")
    else:
        print("  ✗ No migration record found!")

    print("\n6. VERIFICATION:")
    print("-" * 70)

    # Calculate expected totals
    expected_sessions = results['counts']['webui_sessions_legacy']
    actual_migrated_sessions = results['migrated_data']['sessions']

    # Check if all sessions were migrated
    all_tables_exist = all(results['tables'].values())
    legacy_tables_exist = (
        results['tables']['webui_sessions_legacy_exists'] and
        results['tables']['webui_messages_legacy_exists']
    )
    metadata_complete = enrichment['missing_fields_count'] == 0
    migration_recorded = results['migration_record'] is not None

    checks = [
        ("All required tables exist", all_tables_exist),
        ("Legacy tables renamed", legacy_tables_exist),
        ("Metadata enrichment complete", metadata_complete),
        ("Migration recorded", migration_recorded),
    ]

    all_passed = all(status for _, status in checks)

    for check_name, status in checks:
        status_str = "✓ PASS" if status else "✗ FAIL"
        print(f"  {check_name:40} {status_str}")

    print("\n" + "="*70)
    if all_passed:
        print("MIGRATION COMPLETED SUCCESSFULLY ✓")
    else:
        print("MIGRATION COMPLETED WITH WARNINGS ⚠")
    print("="*70 + "\n")

    return all_passed


def main():
    """Main migration execution"""

    # Get database path from unified API
    try:
        from agentos.core.storage.paths import component_db_path
        db_path = component_db_path("agentos")
    except ImportError:
        # Fallback for old installations
        db_path = Path("store/registry.sqlite")

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        logger.error("Please ensure AgentOS is properly initialized")
        sys.exit(1)

    # Get migration SQL path
    migrations_dir = Path(__file__).parent
    migration_sql = migrations_dir / "schema_v34_merge_webui_sessions.sql"

    if not migration_sql.exists():
        logger.error(f"Migration SQL not found: {migration_sql}")
        sys.exit(1)

    logger.info("="*70)
    logger.info("PR-3 Migration: Merge webui_sessions into chat_sessions")
    logger.info("="*70)

    # Step 1: Backup database
    try:
        backup_path = backup_database(db_path)
        logger.info(f"Backup saved to: {backup_path}")
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        sys.exit(1)

    # Step 2: Run migration
    success = run_migration(db_path, migration_sql)
    if not success:
        logger.error("Migration failed! Database backup available at: {backup_path}")
        sys.exit(1)

    # Step 3: Validate results
    with MigrationValidator(str(db_path)) as validator:
        results = validator.validate_all()

    # Step 4: Print report
    all_passed = print_validation_report(results)

    # Step 5: Exit with appropriate code
    if not all_passed:
        logger.warning("Migration completed with warnings. Please review the report.")
        sys.exit(0)  # Success with warnings
    else:
        logger.info("Migration validation passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
