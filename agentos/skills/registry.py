"""Skill Registry - Database-backed storage for skill management.

This module provides:
- SkillRegistry class for skill CRUD operations
- SQLite database with WAL mode for concurrent access
- Status management (imported_disabled | enabled | disabled)
- Trust level tracking (local | reviewed | verified)
- Error tracking and timestamps

Database Schema:
- skills table with full metadata
- Indexes on status and source_type for fast queries
- Epoch milliseconds for all timestamps (ADR-011 compliance)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentos.core.storage.paths import component_db_path, ensure_db_exists

logger = logging.getLogger(__name__)


# SQL statements
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS skills (
    skill_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL,  -- imported_disabled | enabled | disabled
    source_type TEXT NOT NULL,  -- local | github
    source_ref TEXT NOT NULL,  -- path or repo@ref:subdir
    manifest_json TEXT NOT NULL,  -- normalized JSON
    repo_hash TEXT NOT NULL,  -- import content hash
    trust_level TEXT DEFAULT 'local',  -- local | reviewed | verified
    created_at INTEGER NOT NULL,  -- epoch ms
    updated_at INTEGER NOT NULL,  -- epoch ms
    last_error TEXT
)
"""

CREATE_INDEX_STATUS_SQL = """
CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status)
"""

CREATE_INDEX_SOURCE_SQL = """
CREATE INDEX IF NOT EXISTS idx_skills_source ON skills(source_type)
"""


class SkillRegistry:
    """Skill registry with SQLite backend.

    Manages skill lifecycle:
    - Import: Register skills from local or GitHub sources
    - Enable/Disable: Toggle skill availability
    - Query: List and filter skills
    - Delete: Remove skills from registry

    Database location: ~/.agentos/store/skill/db.sqlite
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize skill registry.

        Args:
            db_path: Optional custom database path.
                     If None, uses component_db_path("skill").
        """
        if db_path is None:
            # Use standardized component database path
            self.db_path = str(ensure_db_exists("skill"))
        else:
            self.db_path = db_path
            # Ensure parent directory exists
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"SkillRegistry initialized at: {self.db_path}")
        self.init_db()

    def init_db(self):
        """Initialize database schema and enable WAL mode.

        Creates:
        - skills table with all required fields
        - Indexes on status and source_type
        - WAL journal mode for concurrent access
        """
        try:
            conn = sqlite3.connect(self.db_path)

            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=30000")

            # Create table
            conn.execute(CREATE_TABLE_SQL)

            # Create indexes
            conn.execute(CREATE_INDEX_STATUS_SQL)
            conn.execute(CREATE_INDEX_SOURCE_SQL)

            conn.commit()
            logger.info("Database schema initialized successfully")

        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
        finally:
            conn.close()

    def upsert_skill(
        self,
        skill_id: str,
        manifest: Dict[str, Any],
        source_type: str,
        source_ref: str,
        repo_hash: str,
    ) -> None:
        """Insert or update skill in registry.

        New skills default to status=imported_disabled.
        Updates preserve status and update timestamp.

        Args:
            skill_id: Unique skill identifier
            manifest: Normalized manifest dictionary (from normalize_manifest)
            source_type: 'local' or 'github'
            source_ref: Source location (path or repo@ref:subdir)
            repo_hash: Content hash for deduplication

        Raises:
            sqlite3.Error: If database operation fails
        """
        now_ms = int(time.time() * 1000)
        manifest_json = json.dumps(manifest, ensure_ascii=False)

        try:
            conn = sqlite3.connect(self.db_path)

            # Check if skill exists
            cursor = conn.execute(
                "SELECT skill_id, status FROM skills WHERE skill_id = ?",
                (skill_id,)
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing skill, preserve status
                existing_status = existing[1]
                conn.execute(
                    """
                    UPDATE skills SET
                        name = ?,
                        version = ?,
                        status = ?,
                        source_type = ?,
                        source_ref = ?,
                        manifest_json = ?,
                        repo_hash = ?,
                        updated_at = ?
                    WHERE skill_id = ?
                    """,
                    (
                        manifest["name"],
                        manifest["version"],
                        existing_status,  # Preserve status
                        source_type,
                        source_ref,
                        manifest_json,
                        repo_hash,
                        now_ms,
                        skill_id,
                    )
                )
                logger.info(f"Updated skill: {skill_id}")
            else:
                # Insert new skill with imported_disabled status
                conn.execute(
                    """
                    INSERT INTO skills (
                        skill_id, name, version, status,
                        source_type, source_ref, manifest_json, repo_hash,
                        trust_level, created_at, updated_at, last_error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        skill_id,
                        manifest["name"],
                        manifest["version"],
                        "imported_disabled",  # Default status
                        source_type,
                        source_ref,
                        manifest_json,
                        repo_hash,
                        "local",  # Default trust level
                        now_ms,
                        now_ms,
                        None,
                    )
                )
                logger.info(f"Inserted new skill: {skill_id}")

            conn.commit()

        except sqlite3.Error as e:
            logger.error(f"Failed to upsert skill {skill_id}: {e}")
            raise
        finally:
            conn.close()

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve skill by ID.

        Args:
            skill_id: Skill identifier

        Returns:
            Dictionary with all skill fields, or None if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            cursor = conn.execute(
                "SELECT * FROM skills WHERE skill_id = ?",
                (skill_id,)
            )
            row = cursor.fetchone()

            if row:
                result = dict(row)
                # Parse JSON manifest
                result["manifest_json"] = json.loads(result["manifest_json"])
                return result

            return None

        except sqlite3.Error as e:
            logger.error(f"Failed to get skill {skill_id}: {e}")
            raise
        finally:
            conn.close()

    def list_skills(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all skills, optionally filtered by status.

        Args:
            status: Optional status filter (imported_disabled | enabled | disabled)

        Returns:
            List of skill dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            if status:
                cursor = conn.execute(
                    "SELECT * FROM skills WHERE status = ? ORDER BY created_at DESC",
                    (status,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM skills ORDER BY created_at DESC"
                )

            skills = []
            for row in cursor:
                skill = dict(row)
                # Parse JSON manifest
                skill["manifest_json"] = json.loads(skill["manifest_json"])
                skills.append(skill)

            return skills

        except sqlite3.Error as e:
            logger.error(f"Failed to list skills: {e}")
            raise
        finally:
            conn.close()

    def set_status(self, skill_id: str, status: str) -> None:
        """Update skill status.

        Args:
            skill_id: Skill identifier
            status: New status (imported_disabled | enabled | disabled)

        Raises:
            ValueError: If status is invalid
            sqlite3.Error: If database operation fails
        """
        valid_statuses = ["imported_disabled", "enabled", "disabled"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

        now_ms = int(time.time() * 1000)

        try:
            conn = sqlite3.connect(self.db_path)

            conn.execute(
                "UPDATE skills SET status = ?, updated_at = ? WHERE skill_id = ?",
                (status, now_ms, skill_id)
            )

            if conn.total_changes == 0:
                logger.warning(f"Skill {skill_id} not found for status update")
            else:
                logger.info(f"Updated skill {skill_id} status to {status}")

            conn.commit()

        except sqlite3.Error as e:
            logger.error(f"Failed to update status for {skill_id}: {e}")
            raise
        finally:
            conn.close()

    def set_error(self, skill_id: str, error: str) -> None:
        """Record error message for skill.

        Args:
            skill_id: Skill identifier
            error: Error message

        Raises:
            sqlite3.Error: If database operation fails
        """
        now_ms = int(time.time() * 1000)

        try:
            conn = sqlite3.connect(self.db_path)

            conn.execute(
                "UPDATE skills SET last_error = ?, updated_at = ? WHERE skill_id = ?",
                (error, now_ms, skill_id)
            )

            if conn.total_changes == 0:
                logger.warning(f"Skill {skill_id} not found for error update")
            else:
                logger.info(f"Recorded error for skill {skill_id}")

            conn.commit()

        except sqlite3.Error as e:
            logger.error(f"Failed to update error for {skill_id}: {e}")
            raise
        finally:
            conn.close()

    def delete_skill(self, skill_id: str) -> None:
        """Delete skill from registry.

        Args:
            skill_id: Skill identifier

        Raises:
            sqlite3.Error: If database operation fails
        """
        try:
            conn = sqlite3.connect(self.db_path)

            conn.execute(
                "DELETE FROM skills WHERE skill_id = ?",
                (skill_id,)
            )

            if conn.total_changes == 0:
                logger.warning(f"Skill {skill_id} not found for deletion")
            else:
                logger.info(f"Deleted skill {skill_id}")

            conn.commit()

        except sqlite3.Error as e:
            logger.error(f"Failed to delete skill {skill_id}: {e}")
            raise
        finally:
            conn.close()


__all__ = ["SkillRegistry"]
