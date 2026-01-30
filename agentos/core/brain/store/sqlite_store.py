"""
BrainOS SQLite Store Implementation

Provides idempotent operations for managing the knowledge graph:
- Entity CRUD (with UPSERT for idempotence)
- Edge CRUD (with UPSERT for idempotence)
- Evidence insertion (deduplicated)
- Statistics and metadata queries
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .sqlite_schema import init_schema, verify_schema


class SQLiteStore:
    """
    BrainOS SQLite storage backend.

    Provides idempotent operations for the knowledge graph.
    Thread-safe for read operations, write operations should be serialized.
    """

    def __init__(self, db_path: str, auto_init: bool = True):
        """
        Initialize store connection.

        Args:
            db_path: Path to SQLite database file
            auto_init: Automatically initialize schema if needed (default: True)
        """
        self.db_path = db_path

        # Initialize schema if needed
        if auto_init:
            if not Path(db_path).exists() or not verify_schema(db_path):
                init_schema(db_path)

        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Get or create connection to database."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON")
        return self.conn

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        self.close()

    def upsert_entity(
        self,
        entity_type: str,
        key: str,
        name: str,
        attrs: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Insert or update an entity (idempotent).

        Args:
            entity_type: Entity type (e.g., 'Commit', 'File', 'Repo')
            key: Unique key for idempotence (e.g., 'commit:abc123')
            name: Display name
            attrs: Additional attributes as dict

        Returns:
            Entity ID (existing or newly created)
        """
        conn = self.connect()
        cursor = conn.cursor()

        attrs_json = json.dumps(attrs or {})
        created_at = time.time()

        # Try to insert, on conflict do nothing (idempotent)
        cursor.execute("""
            INSERT INTO entities (type, key, name, attrs_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(type, key) DO UPDATE SET
                name = excluded.name,
                attrs_json = excluded.attrs_json
        """, (entity_type, key, name, attrs_json, created_at))

        # Get the entity ID
        cursor.execute("""
            SELECT id FROM entities WHERE type = ? AND key = ?
        """, (entity_type, key))

        result = cursor.fetchone()
        if not result:
            raise RuntimeError(f"Failed to upsert entity: {entity_type}:{key}")

        return result[0]

    def upsert_edge(
        self,
        src_entity_id: int,
        dst_entity_id: int,
        edge_type: str,
        key: str,
        attrs: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0
    ) -> int:
        """
        Insert or update an edge (idempotent).

        Args:
            src_entity_id: Source entity ID
            dst_entity_id: Destination entity ID
            edge_type: Edge type (e.g., 'MODIFIES', 'REFERENCES')
            key: Unique key for idempotence
            attrs: Additional attributes as dict
            confidence: Confidence score (0.0-1.0)

        Returns:
            Edge ID (existing or newly created)
        """
        conn = self.connect()
        cursor = conn.cursor()

        attrs_json = json.dumps(attrs or {})
        created_at = time.time()

        # Try to insert, on conflict do nothing (idempotent)
        cursor.execute("""
            INSERT INTO edges (
                src_entity_id, dst_entity_id, type, key,
                attrs_json, confidence, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                attrs_json = excluded.attrs_json,
                confidence = excluded.confidence
        """, (src_entity_id, dst_entity_id, edge_type, key,
              attrs_json, confidence, created_at))

        # Get the edge ID
        cursor.execute("""
            SELECT id FROM edges WHERE key = ?
        """, (key,))

        result = cursor.fetchone()
        if not result:
            raise RuntimeError(f"Failed to upsert edge: {key}")

        return result[0]

    def insert_evidence(
        self,
        edge_id: int,
        source_type: str,
        source_ref: str,
        span: Optional[Dict[str, Any]] = None,
        attrs: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Insert evidence for an edge (idempotent via UNIQUE constraint).

        Args:
            edge_id: Edge ID this evidence supports
            source_type: Evidence source type (e.g., 'git', 'doc', 'code')
            source_ref: Source reference (commit hash, file path, etc.)
            span: Location span (line numbers, etc.)
            attrs: Additional attributes

        Returns:
            Evidence ID
        """
        conn = self.connect()
        cursor = conn.cursor()

        span_json = json.dumps(span or {})
        attrs_json = json.dumps(attrs or {})
        created_at = time.time()

        try:
            cursor.execute("""
                INSERT INTO evidence (
                    edge_id, source_type, source_ref,
                    span_json, attrs_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(edge_id, source_type, source_ref, span_json) DO NOTHING
            """, (edge_id, source_type, source_ref, span_json, attrs_json, created_at))

            # Get the evidence ID
            cursor.execute("""
                SELECT id FROM evidence
                WHERE edge_id = ? AND source_type = ? AND source_ref = ? AND span_json = ?
            """, (edge_id, source_type, source_ref, span_json))

            result = cursor.fetchone()
            if not result:
                raise RuntimeError(f"Failed to insert evidence for edge {edge_id}")

            return result[0]

        except sqlite3.IntegrityError as e:
            # Evidence already exists (idempotent)
            cursor.execute("""
                SELECT id FROM evidence
                WHERE edge_id = ? AND source_type = ? AND source_ref = ? AND span_json = ?
            """, (edge_id, source_type, source_ref, span_json))

            result = cursor.fetchone()
            if result:
                return result[0]
            raise

    def get_entity_by_key(self, entity_type: str, key: str) -> Optional[Dict[str, Any]]:
        """
        Get entity by type and key.

        Returns:
            Entity dict or None if not found
        """
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, type, key, name, attrs_json, created_at
            FROM entities
            WHERE type = ? AND key = ?
        """, (entity_type, key))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            'id': row[0],
            'type': row[1],
            'key': row[2],
            'name': row[3],
            'attrs': json.loads(row[4]),
            'created_at': row[5]
        }

    def get_entity_by_id(self, entity_id: int) -> Optional[Dict[str, Any]]:
        """Get entity by ID."""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, type, key, name, attrs_json, created_at
            FROM entities
            WHERE id = ?
        """, (entity_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            'id': row[0],
            'type': row[1],
            'key': row[2],
            'name': row[3],
            'attrs': json.loads(row[4]),
            'created_at': row[5]
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dict with counts and metadata
        """
        conn = self.connect()
        cursor = conn.cursor()

        # Get counts
        cursor.execute("SELECT COUNT(*) FROM entities")
        entity_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM edges")
        edge_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM evidence")
        evidence_count = cursor.fetchone()[0]

        # Get last build metadata
        cursor.execute("""
            SELECT graph_version, source_commit, built_at, duration_ms
            FROM build_metadata
            ORDER BY id DESC
            LIMIT 1
        """)
        last_build_row = cursor.fetchone()

        last_build = None
        if last_build_row:
            last_build = {
                'graph_version': last_build_row[0],
                'source_commit': last_build_row[1],
                'built_at': last_build_row[2],
                'duration_ms': last_build_row[3]
            }

        return {
            'entities': entity_count,
            'edges': edge_count,
            'evidence': evidence_count,
            'last_build': last_build
        }

    def get_last_build_metadata(self) -> Optional[Dict[str, Any]]:
        """Get the most recent build metadata record."""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                graph_version, source_commit, repo_path, built_at,
                duration_ms, entity_count, edge_count, evidence_count,
                enabled_extractors, errors
            FROM build_metadata
            ORDER BY id DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        if not row:
            return None

        return {
            'graph_version': row[0],
            'source_commit': row[1],
            'repo_path': row[2],
            'built_at': row[3],
            'duration_ms': row[4],
            'entity_count': row[5],
            'edge_count': row[6],
            'evidence_count': row[7],
            'enabled_extractors': json.loads(row[8]),
            'errors': json.loads(row[9])
        }

    def save_build_metadata(
        self,
        graph_version: str,
        source_commit: str,
        repo_path: str,
        built_at: float,
        duration_ms: int,
        entity_count: int,
        edge_count: int,
        evidence_count: int,
        enabled_extractors: List[str],
        errors: List[str]
    ) -> int:
        """
        Save build metadata record.

        Returns:
            Metadata record ID
        """
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO build_metadata (
                graph_version, source_commit, repo_path, built_at,
                duration_ms, entity_count, edge_count, evidence_count,
                enabled_extractors, errors
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            graph_version, source_commit, repo_path, built_at,
            duration_ms, entity_count, edge_count, evidence_count,
            json.dumps(enabled_extractors), json.dumps(errors)
        ))

        return cursor.lastrowid

    def insert_fts_commit(self, commit_hash: str, message: str):
        """Insert commit into full-text search index."""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO fts_commits (commit_hash, message)
            VALUES (?, ?)
        """, (commit_hash, message))


def init_db(db_path: str) -> None:
    """
    Initialize BrainOS database.

    Convenience function for schema initialization.

    Args:
        db_path: Path to SQLite database file
    """
    init_schema(db_path)


def get_stats(db_path: str) -> Dict[str, Any]:
    """
    Get statistics from BrainOS database.

    Convenience function for quick stats queries.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Statistics dict
    """
    with SQLiteStore(db_path, auto_init=False) as store:
        return store.get_stats()
