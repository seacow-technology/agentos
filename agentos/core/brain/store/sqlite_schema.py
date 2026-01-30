"""
BrainOS SQLite Schema Definition

Defines the database schema for BrainOS knowledge graph:
- entities: nodes in the graph (Repo, Commit, File, etc.)
- edges: relationships between entities (MODIFIES, REFERENCES, etc.)
- evidence: provenance/evidence for edges
- build_metadata: build job metadata and statistics
- fts_commits: full-text search for commit messages
"""

import sqlite3
import time
from pathlib import Path
from typing import Optional

# Schema version for migrations
SCHEMA_VERSION = "1.0.0"

# Core tables DDL
ENTITIES_TABLE = """
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,           -- 'Repo'/'File'/'Commit'/...
    key TEXT NOT NULL,            -- 幂等键: 'commit:abc123'/'file:path/to/file.py'
    name TEXT NOT NULL,
    attrs_json TEXT DEFAULT '{}', -- JSON 格式的其他属性
    created_at REAL NOT NULL,     -- Unix timestamp
    UNIQUE(type, key)
);
"""

EDGES_TABLE = """
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    src_entity_id INTEGER NOT NULL,
    dst_entity_id INTEGER NOT NULL,
    type TEXT NOT NULL,           -- 'MODIFIES'/'REFERENCES'/...
    key TEXT NOT NULL,            -- 幂等键: 'MODIFIES|commit:abc|file:path'
    attrs_json TEXT DEFAULT '{}',
    confidence REAL DEFAULT 1.0,
    created_at REAL NOT NULL,
    FOREIGN KEY(src_entity_id) REFERENCES entities(id),
    FOREIGN KEY(dst_entity_id) REFERENCES entities(id),
    UNIQUE(key)
);
"""

EVIDENCE_TABLE = """
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    edge_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,    -- 'git'/'doc'/'code'
    source_ref TEXT NOT NULL,     -- commit hash / doc path
    span_json TEXT DEFAULT '{}',  -- 行号范围等
    attrs_json TEXT DEFAULT '{}',
    created_at REAL NOT NULL,
    FOREIGN KEY(edge_id) REFERENCES edges(id),
    UNIQUE(edge_id, source_type, source_ref, span_json)
);
"""

BUILD_METADATA_TABLE = """
CREATE TABLE IF NOT EXISTS build_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    graph_version TEXT NOT NULL,  -- timestamp + commit
    source_commit TEXT NOT NULL,
    repo_path TEXT NOT NULL,
    built_at REAL NOT NULL,
    duration_ms INTEGER NOT NULL,
    entity_count INTEGER NOT NULL,
    edge_count INTEGER NOT NULL,
    evidence_count INTEGER NOT NULL,
    enabled_extractors TEXT NOT NULL, -- JSON array
    errors TEXT DEFAULT '[]'          -- JSON array
);
"""

# FTS5 virtual table for commit message search
FTS_COMMITS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS fts_commits USING fts5(
    commit_hash UNINDEXED,
    message,
    tokenize='porter'
);
"""

# Indexes for performance
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);",
    "CREATE INDEX IF NOT EXISTS idx_entities_key ON entities(key);",
    "CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src_entity_id);",
    "CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst_entity_id);",
    "CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(type);",
    "CREATE INDEX IF NOT EXISTS idx_evidence_edge ON evidence(edge_id);",
]

# Schema metadata table
SCHEMA_METADATA_TABLE = """
CREATE TABLE IF NOT EXISTS _schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""


def init_schema(db_path: str) -> None:
    """
    Initialize the BrainOS SQLite schema.

    Creates all tables, indexes, and metadata.
    Safe to call multiple times (idempotent).

    Args:
        db_path: Path to SQLite database file
    """
    # Ensure parent directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Create core tables
        cursor.execute(ENTITIES_TABLE)
        cursor.execute(EDGES_TABLE)
        cursor.execute(EVIDENCE_TABLE)
        cursor.execute(BUILD_METADATA_TABLE)
        cursor.execute(FTS_COMMITS_TABLE)
        cursor.execute(SCHEMA_METADATA_TABLE)

        # Create indexes
        for index_sql in INDEXES:
            cursor.execute(index_sql)

        # Record schema version
        cursor.execute("""
            INSERT OR REPLACE INTO _schema_metadata (key, value, updated_at)
            VALUES ('schema_version', ?, ?)
        """, (SCHEMA_VERSION, time.time()))

        conn.commit()

    finally:
        conn.close()


def get_schema_version(db_path: str) -> Optional[str]:
    """Get the current schema version from database."""
    if not Path(db_path).exists():
        return None

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT value FROM _schema_metadata WHERE key = 'schema_version'
        """)
        result = cursor.fetchone()
        return result[0] if result else None
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return None
    finally:
        conn.close()


def verify_schema(db_path: str) -> bool:
    """
    Verify that all required tables and indexes exist.

    Returns:
        True if schema is valid, False otherwise
    """
    if not Path(db_path).exists():
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check required tables
        required_tables = [
            'entities', 'edges', 'evidence',
            'build_metadata', 'fts_commits', '_schema_metadata'
        ]

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
        """)
        existing_tables = {row[0] for row in cursor.fetchall()}

        for table in required_tables:
            if table not in existing_tables:
                return False

        # Check required indexes
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name LIKE 'idx_%'
        """)
        existing_indexes = {row[0] for row in cursor.fetchall()}

        required_indexes = [
            'idx_entities_type', 'idx_entities_key',
            'idx_edges_src', 'idx_edges_dst', 'idx_edges_type',
            'idx_evidence_edge'
        ]

        for index in required_indexes:
            if index not in existing_indexes:
                return False

        return True

    finally:
        conn.close()
