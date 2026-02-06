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

# P3-B: Snapshot tables for Compare functionality
BRAIN_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS brain_snapshots (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    description TEXT,

    -- 统计摘要
    entity_count INTEGER NOT NULL,
    edge_count INTEGER NOT NULL,
    evidence_count INTEGER NOT NULL,

    -- 覆盖摘要
    coverage_percentage REAL NOT NULL,
    git_coverage REAL NOT NULL,
    doc_coverage REAL NOT NULL,
    code_coverage REAL NOT NULL,

    -- 盲区摘要
    blind_spot_count INTEGER NOT NULL,
    high_risk_blind_spot_count INTEGER NOT NULL,

    -- 元数据
    graph_version TEXT NOT NULL,
    created_by TEXT,

    UNIQUE(timestamp)
);
"""

BRAIN_SNAPSHOT_ENTITIES_TABLE = """
CREATE TABLE IF NOT EXISTS brain_snapshot_entities (
    snapshot_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    entity_name TEXT NOT NULL,

    -- 快照时的认知属性
    evidence_count INTEGER NOT NULL,
    coverage_sources TEXT NOT NULL,
    is_blind_spot INTEGER NOT NULL,
    blind_spot_severity REAL,

    PRIMARY KEY (snapshot_id, entity_id),
    FOREIGN KEY (snapshot_id) REFERENCES brain_snapshots(id)
);
"""

BRAIN_SNAPSHOT_EDGES_TABLE = """
CREATE TABLE IF NOT EXISTS brain_snapshot_edges (
    snapshot_id TEXT NOT NULL,
    edge_id TEXT NOT NULL,
    src_entity_id TEXT NOT NULL,
    dst_entity_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,

    -- 快照时的证据
    evidence_count INTEGER NOT NULL,
    evidence_types TEXT NOT NULL,

    PRIMARY KEY (snapshot_id, edge_id),
    FOREIGN KEY (snapshot_id) REFERENCES brain_snapshots(id)
);
"""

# Snapshot indexes
SNAPSHOT_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_brain_snapshots_timestamp ON brain_snapshots(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_brain_snapshot_entities_snapshot ON brain_snapshot_entities(snapshot_id);",
    "CREATE INDEX IF NOT EXISTS idx_brain_snapshot_edges_snapshot ON brain_snapshot_edges(snapshot_id);",
]

# P4-A: Decision Records (Governance Layer)
DECISION_RECORDS_TABLE = """
CREATE TABLE IF NOT EXISTS decision_records (
    decision_id TEXT PRIMARY KEY,
    decision_type TEXT NOT NULL,
    seed TEXT NOT NULL,
    inputs TEXT NOT NULL,
    outputs TEXT NOT NULL,
    rules_triggered TEXT NOT NULL,
    final_verdict TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    timestamp TEXT NOT NULL,
    snapshot_ref TEXT,
    signed_by TEXT,
    sign_timestamp TEXT,
    sign_note TEXT,
    status TEXT NOT NULL,
    record_hash TEXT NOT NULL,

    CHECK (status IN ('PENDING', 'APPROVED', 'BLOCKED', 'SIGNED', 'FAILED'))
);
"""

DECISION_SIGNOFFS_TABLE = """
CREATE TABLE IF NOT EXISTS decision_signoffs (
    signoff_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    signed_by TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    note TEXT NOT NULL,

    FOREIGN KEY (decision_id) REFERENCES decision_records(decision_id)
);
"""

# Decision indexes
DECISION_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_decision_records_seed ON decision_records(seed);",
    "CREATE INDEX IF NOT EXISTS idx_decision_records_type ON decision_records(decision_type);",
    "CREATE INDEX IF NOT EXISTS idx_decision_records_timestamp ON decision_records(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_decision_records_status ON decision_records(status);",
    "CREATE INDEX IF NOT EXISTS idx_decision_signoffs_decision_id ON decision_signoffs(decision_id);",
]


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

        # Create snapshot tables (P3-B)
        cursor.execute(BRAIN_SNAPSHOTS_TABLE)
        cursor.execute(BRAIN_SNAPSHOT_ENTITIES_TABLE)
        cursor.execute(BRAIN_SNAPSHOT_EDGES_TABLE)

        # Create decision tables (P4-A)
        cursor.execute(DECISION_RECORDS_TABLE)
        cursor.execute(DECISION_SIGNOFFS_TABLE)

        # Create indexes
        for index_sql in INDEXES:
            cursor.execute(index_sql)

        # Create snapshot indexes
        for index_sql in SNAPSHOT_INDEXES:
            cursor.execute(index_sql)

        # Create decision indexes
        for index_sql in DECISION_INDEXES:
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
            'build_metadata', 'fts_commits', '_schema_metadata',
            'brain_snapshots', 'brain_snapshot_entities', 'brain_snapshot_edges',
            'decision_records', 'decision_signoffs'
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
