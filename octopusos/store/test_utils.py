"""
Test utilities for store layer testing

Provides helper functions to create test databases and run migrations.
"""

import sqlite3
import tempfile
from pathlib import Path


def create_test_db() -> str:
    """
    Create temporary test database with v23 schema

    Returns:
        Database path (temporary file that will be auto-deleted)
    """
    # Create temporary file for database
    temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = temp_file.name
    temp_file.close()

    # Run migrations
    run_migrations(db_path)

    return db_path


def run_migrations(db_path: str):
    """
    Execute v23 migration to set up schema

    Args:
        db_path: Path to SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Read v23 migration SQL
    migrations_dir = Path(__file__).parent / "migrations"
    v23_sql_path = migrations_dir / "schema_v23.sql"

    if not v23_sql_path.exists():
        raise FileNotFoundError(f"Migration file not found: {v23_sql_path}")

    v23_sql = v23_sql_path.read_text()

    # Execute migration
    cursor.executescript(v23_sql)

    conn.commit()
    conn.close()


def create_in_memory_db() -> str:
    """
    Create in-memory test database (faster but can't be inspected)

    Returns:
        Database path (":memory:")
    """
    db_path = ":memory:"
    run_migrations_in_memory(db_path)
    return db_path


def run_migrations_in_memory(db_path: str):
    """
    Execute v23 migration for in-memory database

    Note: In-memory databases are ephemeral and require the connection
    to stay open. This is a simplified version for testing.

    Args:
        db_path: Database path (should be ":memory:")
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Inline v23 schema for in-memory testing
    # This avoids file I/O and makes tests faster
    v23_schema = """
    -- Content Items table
    CREATE TABLE IF NOT EXISTS content_items (
        id TEXT PRIMARY KEY,
        content_type TEXT NOT NULL,
        name TEXT NOT NULL,
        version TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft',
        source_uri TEXT,
        metadata_json TEXT,
        release_notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        CHECK (content_type IN ('agent', 'workflow', 'skill', 'tool')),
        CHECK (status IN ('draft', 'active', 'deprecated', 'frozen'))
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_content_items_type_name_version
        ON content_items(content_type, name, version);
    CREATE INDEX IF NOT EXISTS idx_content_items_type_name
        ON content_items(content_type, name);
    CREATE INDEX IF NOT EXISTS idx_content_items_status
        ON content_items(status);

    -- Answer Packs table
    CREATE TABLE IF NOT EXISTS answer_packs (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'draft',
        items_json TEXT NOT NULL,
        metadata_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        CHECK (status IN ('draft', 'active', 'archived'))
    );

    CREATE INDEX IF NOT EXISTS idx_answer_packs_status
        ON answer_packs(status);
    CREATE INDEX IF NOT EXISTS idx_answer_packs_name
        ON answer_packs(name);

    -- Answer Pack Links table
    CREATE TABLE IF NOT EXISTS answer_pack_links (
        id TEXT PRIMARY KEY,
        pack_id TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (pack_id) REFERENCES answer_packs(id) ON DELETE CASCADE,
        CHECK (entity_type IN ('task', 'intent'))
    );

    CREATE INDEX IF NOT EXISTS idx_answer_pack_links_pack
        ON answer_pack_links(pack_id);
    CREATE INDEX IF NOT EXISTS idx_answer_pack_links_entity
        ON answer_pack_links(entity_type, entity_id);

    -- Schema version
    CREATE TABLE IF NOT EXISTS schema_version (version TEXT PRIMARY KEY);
    INSERT OR REPLACE INTO schema_version (version) VALUES ('0.23.0');
    """

    cursor.executescript(v23_schema)
    conn.commit()
    conn.close()
