"""
Classifier Version Manager for OctopusOS v3

This module provides version management for InfoNeedClassifier, including:
- Version number generation (Major.Minor)
- Change log recording
- Version rollback support
- History tracking

Design Philosophy:
- Semantic versioning (v1, v2, v2.1)
- Immutable version history
- Traceable change sources (from ImprovementProposal)
- Rollback safety
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from octopusos.core.storage.migrations import ensure_component_migrations
from octopusos.core.storage.paths import component_db_path
from octopusos.core.time import utc_now, utc_now_iso


logger = logging.getLogger(__name__)


@dataclass
class VersionInfo:
    """Version information for a classifier version."""
    version_id: str  # e.g., "v2", "v2.1"
    version_number: str  # Semantic version: "2.0", "2.1"
    parent_version_id: Optional[str]  # Parent version (for rollback)
    change_log: str  # Description of changes
    source_proposal_id: Optional[str]  # Source ImprovementProposal ID
    is_active: bool  # Is this the currently active version?
    created_at: datetime
    created_by: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "version_id": self.version_id,
            "version_number": self.version_number,
            "parent_version_id": self.parent_version_id,
            "change_log": self.change_log,
            "source_proposal_id": self.source_proposal_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "metadata": self.metadata,
        }


@dataclass
class RollbackInfo:
    """Rollback operation information."""
    rollback_id: str
    from_version_id: str
    to_version_id: str
    reason: str
    performed_by: str
    performed_at: datetime
    metadata: Dict[str, Any]


class ClassifierVersionManager:
    """
    Version manager for InfoNeedClassifier.

    Responsibilities:
    - Generate new version IDs following semantic versioning
    - Record version change logs
    - Manage active version
    - Support version rollback
    - Track version history

    Version Numbering:
    - Major version: v1 -> v2 (breaking changes, major improvements)
    - Minor version: v2 -> v2.1 (incremental improvements)
    - Automatic increment based on change type

    Usage:
        manager = ClassifierVersionManager()

        # Promote a shadow classifier to new version
        new_version = manager.promote_version(
            proposal_id="BP-017",
            change_log="Expand time-sensitive keywords",
            created_by="admin",
            is_major=False  # Minor version bump
        )

        # Rollback to previous version
        manager.rollback_version(
            to_version="v2",
            reason="Performance regression detected",
            performed_by="admin"
        )
    """

    def __init__(self):
        """Initialize version manager."""
        ensure_component_migrations("brainos")
        self.db_path = component_db_path("brainos")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _transaction(self):
        with self._connect() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _query_one(self, sql: str, params: Tuple[Any, ...] = ()) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(sql, params).fetchone()

    def _query_all(self, sql: str, params: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(sql, params).fetchall()

    def _ensure_tables(self) -> None:
        """Ensure version management tables exist."""
        with self._transaction() as conn:
            # Table: classifier_versions
            conn.execute("""
                CREATE TABLE IF NOT EXISTS classifier_versions (
                    version_id TEXT PRIMARY KEY,
                    version_number TEXT NOT NULL,
                    parent_version_id TEXT,
                    version_type TEXT NOT NULL DEFAULT 'active',
                    change_log TEXT NOT NULL,
                    source_proposal_id TEXT,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
            """)

            # Table: version_rollback_history
            conn.execute("""
                CREATE TABLE IF NOT EXISTS version_rollback_history (
                    rollback_id TEXT PRIMARY KEY,
                    from_version_id TEXT NOT NULL,
                    to_version_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    performed_by TEXT NOT NULL,
                    performed_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
            """)

        # Initialize v1 if not exists
        self._initialize_v1()

    def _initialize_v1(self) -> None:
        """Initialize v1 as the first version if no versions exist."""
        existing = self._query_one(
            "SELECT version_id FROM classifier_versions WHERE version_id = 'v1'"
        )

        if not existing:
            with self._transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO classifier_versions (
                        version_id, version_number, parent_version_id,
                        version_type, change_log, source_proposal_id, is_active,
                        created_at, created_by, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "v1",
                        "1.0",
                        None,
                        "active",
                        "Initial production classifier with rule-based and LLM confidence signals",
                        None,
                        1,  # Active by default
                        utc_now_iso(),
                        "system",
                        json.dumps({"initial_version": True}),
                    )
                )
            logger.info("Initialized v1 as first classifier version")

    def get_active_version(self) -> Optional[VersionInfo]:
        """
        Get the currently active classifier version.

        Returns:
            VersionInfo of active version, or None if no active version
        """
        row = self._query_one(
            """
            SELECT version_id, version_number, parent_version_id,
                   change_log, source_proposal_id, is_active,
                   created_at, created_by, metadata
            FROM classifier_versions
            WHERE is_active = 1
            """
        )

        if not row:
            return None

        return self._row_to_version_info(row)

    def get_version(self, version_id: str) -> Optional[VersionInfo]:
        """
        Get version information by version ID.

        Args:
            version_id: Version ID (e.g., "v2", "v2.1")

        Returns:
            VersionInfo if found, None otherwise
        """
        row = self._query_one(
            """
            SELECT version_id, version_number, parent_version_id,
                   change_log, source_proposal_id, is_active,
                   created_at, created_by, metadata
            FROM classifier_versions
            WHERE version_id = ?
            """,
            (version_id,)
        )

        if not row:
            return None

        return self._row_to_version_info(row)

    def list_versions(self, limit: int = 100) -> List[VersionInfo]:
        """
        List all versions in reverse chronological order.

        Args:
            limit: Maximum number of versions to return

        Returns:
            List of VersionInfo
        """
        rows = self._query_all(
            """
            SELECT version_id, version_number, parent_version_id,
                   change_log, source_proposal_id, is_active,
                   created_at, created_by, metadata
            FROM classifier_versions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        )

        return [self._row_to_version_info(row) for row in rows]

    def promote_version(
        self,
        proposal_id: str,
        change_log: str,
        created_by: str,
        is_major: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VersionInfo:
        """
        Promote a shadow classifier to a new version.

        This creates a new version based on an approved ImprovementProposal.
        The version number is automatically incremented (major or minor).

        Args:
            proposal_id: Source ImprovementProposal ID (e.g., "BP-017")
            change_log: Description of changes in this version
            created_by: User who initiated the promotion
            is_major: If True, increment major version (v1->v2); if False, minor (v2->v2.1)
            metadata: Optional metadata

        Returns:
            VersionInfo of the newly created version

        Raises:
            ValueError: If proposal_id is invalid
        """
        # Get current active version
        current = self.get_active_version()
        if not current:
            raise ValueError("No active version found. Cannot promote.")

        # Generate new version ID
        new_version_id, new_version_number = self._generate_next_version(
            current.version_id,
            is_major=is_major
        )

        # Create new version
        now = utc_now()
        version_metadata = metadata or {}
        version_metadata["promoted_from"] = current.version_id
        version_metadata["proposal_id"] = proposal_id

        with self._transaction() as conn:
            # Deactivate current version
            conn.execute(
                "UPDATE classifier_versions SET is_active = 0 WHERE version_id = ?",
                (current.version_id,)
            )

            # Insert new version
            conn.execute(
                """
                INSERT INTO classifier_versions (
                    version_id, version_number, parent_version_id,
                    version_type, change_log, source_proposal_id, is_active,
                    created_at, created_by, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_version_id,
                    new_version_number,
                    current.version_id,
                    "active",
                    change_log,
                    proposal_id,
                    1,  # Active
                    now.isoformat(),
                    created_by,
                    json.dumps(version_metadata),
                )
            )

        logger.info(
            f"Promoted classifier version: {current.version_id} -> {new_version_id} "
            f"(proposal: {proposal_id}, by: {created_by})"
        )

        # Return new version info
        new_version = self.get_version(new_version_id)
        if not new_version:
            raise RuntimeError(f"Failed to retrieve newly created version: {new_version_id}")

        return new_version

    def rollback_version(
        self,
        to_version_id: str,
        reason: str,
        performed_by: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VersionInfo:
        """
        Rollback to a previous version.

        This deactivates the current version and reactivates a previous version.
        The rollback is recorded in the rollback history for audit.

        Args:
            to_version_id: Target version ID to rollback to (e.g., "v2")
            reason: Reason for rollback
            performed_by: User performing the rollback
            metadata: Optional metadata

        Returns:
            VersionInfo of the restored version

        Raises:
            ValueError: If target version doesn't exist or is already active
        """
        # Get current active version
        current = self.get_active_version()
        if not current:
            raise ValueError("No active version found")

        # Check if target version exists
        target = self.get_version(to_version_id)
        if not target:
            raise ValueError(f"Target version not found: {to_version_id}")

        # Check if already active
        if target.is_active:
            raise ValueError(f"Version {to_version_id} is already active")

        # Perform rollback
        now = utc_now()
        rollback_id = f"rollback-{now.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
        rollback_metadata = metadata or {}
        rollback_metadata["reason"] = reason

        with self._transaction() as conn:
            # Deactivate current version
            conn.execute(
                "UPDATE classifier_versions SET is_active = 0 WHERE version_id = ?",
                (current.version_id,)
            )

            # Reactivate target version
            conn.execute(
                "UPDATE classifier_versions SET is_active = 1 WHERE version_id = ?",
                (to_version_id,)
            )

            # Record rollback in history
            conn.execute(
                """
                INSERT INTO version_rollback_history (
                    rollback_id, from_version_id, to_version_id,
                    reason, performed_by, performed_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rollback_id,
                    current.version_id,
                    to_version_id,
                    reason,
                    performed_by,
                    now.isoformat(),
                    json.dumps(rollback_metadata),
                )
            )

        logger.warning(
            f"Rolled back classifier version: {current.version_id} -> {to_version_id} "
            f"(reason: {reason}, by: {performed_by})"
        )

        # Return restored version
        restored = self.get_version(to_version_id)
        if not restored:
            raise RuntimeError(f"Failed to retrieve restored version: {to_version_id}")

        return restored

    def get_rollback_history(self, limit: int = 50) -> List[RollbackInfo]:
        """
        Get rollback history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of RollbackInfo in reverse chronological order
        """
        rows = self._query_all(
            """
            SELECT rollback_id, from_version_id, to_version_id,
                   reason, performed_by, performed_at, metadata
            FROM version_rollback_history
            ORDER BY performed_at DESC
            LIMIT ?
            """,
            (limit,)
        )

        result = []
        for row in rows:
            result.append(RollbackInfo(
                rollback_id=row["rollback_id"],
                from_version_id=row["from_version_id"],
                to_version_id=row["to_version_id"],
                reason=row["reason"],
                performed_by=row["performed_by"],
                performed_at=datetime.fromisoformat(row["performed_at"]),
                metadata=json.loads(row["metadata"]),
            ))

        return result

    def _generate_next_version(
        self,
        current_version_id: str,
        is_major: bool
    ) -> Tuple[str, str]:
        """
        Generate next version ID and number.

        Args:
            current_version_id: Current version ID (e.g., "v2", "v2.1")
            is_major: If True, bump major version; if False, bump minor

        Returns:
            Tuple of (new_version_id, new_version_number)

        Examples:
            v1, major=True -> (v2, 2.0)
            v2, major=False -> (v2.1, 2.1)
            v2.1, major=True -> (v3, 3.0)
            v2.1, major=False -> (v2.2, 2.2)
        """
        # Parse current version
        if current_version_id.startswith("v"):
            version_str = current_version_id[1:]  # Remove 'v' prefix
        else:
            version_str = current_version_id

        # Split into major.minor
        parts = version_str.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0

        if is_major:
            # Bump major version, reset minor
            new_major = major + 1
            new_minor = 0
        else:
            # Bump minor version
            new_major = major
            new_minor = minor + 1

        # Generate new version
        if new_minor == 0:
            new_version_id = f"v{new_major}"
            new_version_number = f"{new_major}.0"
        else:
            new_version_id = f"v{new_major}.{new_minor}"
            new_version_number = f"{new_major}.{new_minor}"

        return new_version_id, new_version_number

    def _row_to_version_info(self, row) -> VersionInfo:
        """Convert database row to VersionInfo."""
        return VersionInfo(
            version_id=row["version_id"],
            version_number=row["version_number"],
            parent_version_id=row["parent_version_id"],
            change_log=row["change_log"],
            source_proposal_id=row["source_proposal_id"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            created_by=row["created_by"],
            metadata=json.loads(row["metadata"]),
        )


# Singleton instance
_manager: Optional[ClassifierVersionManager] = None


def get_version_manager() -> ClassifierVersionManager:
    """Get singleton version manager instance."""
    global _manager
    if _manager is None:
        _manager = ClassifierVersionManager()
    return _manager


def reset_version_manager() -> None:
    """Reset version manager (for testing)."""
    global _manager
    _manager = None
