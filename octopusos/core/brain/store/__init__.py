"""
BrainOS Store Module

Handles persistent storage for the knowledge graph.

Storage backend (M1):
- SQLite database
- Tables: entities, edges, evidence, build_metadata, fts_commits

Features:
1. Full-text search (FTS5): commit messages
2. Indexes: entity key, edge (src, dst, type)
3. Build metadata tracking

Contracts:
- Read-only principle: Original repo is read-only, only BrainOS index is writable
- Idempotence: Same data can be written multiple times with same result
- Integrity: All edge src/dst must reference existing entities
"""

from .sqlite_store import SQLiteStore, init_db, get_stats
from .sqlite_schema import init_schema, verify_schema, SCHEMA_VERSION
from .manifest import (
    BuildManifest,
    save_manifest,
    load_manifest,
    create_graph_version,
    get_iso_timestamp
)
from . import query_helpers

__all__ = [
    # Store
    "SQLiteStore",
    "init_db",
    "get_stats",

    # Schema
    "init_schema",
    "verify_schema",
    "SCHEMA_VERSION",

    # Manifest
    "BuildManifest",
    "save_manifest",
    "load_manifest",
    "create_graph_version",
    "get_iso_timestamp",

    # Query Helpers
    "query_helpers",
]
