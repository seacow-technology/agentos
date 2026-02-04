#!/usr/bin/env python3
"""
Phase D3 Migration: Trust Tier Tables

Applies schema_v68_trust_tiers.sql to create:
- trust_tier_history: Tier change audit trail
- trust_tier_current: Current tier cache
"""

import os
import sys
import sqlite3
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from agentos.store import get_db_path


def run_migration():
    """Run D3 trust tier migration."""
    db_path = get_db_path()

    print(f"Running D3 Trust Tier Migration on: {db_path}")

    # Read schema file
    schema_file = Path(__file__).parent / "schema_v68_trust_tiers.sql"

    if not schema_file.exists():
        print(f"❌ Schema file not found: {schema_file}")
        return False

    with open(schema_file, 'r') as f:
        schema_sql = f.read()

    # Apply schema
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Execute schema
        cursor.executescript(schema_sql)
        conn.commit()

        # Verify tables
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('trust_tier_history', 'trust_tier_current')
        """)
        tables = [row[0] for row in cursor.fetchall()]

        if 'trust_tier_history' in tables and 'trust_tier_current' in tables:
            print("✅ Trust tier tables created successfully")

            # Check schema version
            cursor.execute("SELECT version FROM schema_versions WHERE version = 68")
            if cursor.fetchone():
                print("✅ Schema version 68 recorded")
            else:
                print("⚠️  Schema version 68 not recorded (schema_versions table might not exist)")

            conn.close()
            return True
        else:
            print(f"❌ Tables not created. Found: {tables}")
            conn.close()
            return False

    except sqlite3.Error as e:
        print(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
