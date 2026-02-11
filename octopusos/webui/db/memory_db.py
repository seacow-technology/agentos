"""Memory DB connection helpers for WebUI APIs."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from octopusos.core.storage.paths import component_db_path

logger = logging.getLogger(__name__)


def memory_db_path() -> Path:
    """Return canonical MemoryOS sqlite path."""
    return component_db_path("memoryos")


def memory_db_connect() -> sqlite3.Connection:
    """Connect to MemoryOS sqlite DB with row factory configured."""
    db_path = memory_db_path()
    if not db_path.exists():
        raise RuntimeError(f"Memory database not initialized: {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    logger.info("memory_entries_db_connect store_path=%s", db_path)
    return conn

