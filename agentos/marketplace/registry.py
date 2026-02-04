"""Marketplace Registry - Capability Registration and Discovery.

The MarketplaceRegistry is a capability LEDGER that records:
1. WHO published the capability (publisher identity)
2. WHAT was published (complete manifest)
3. WHERE it came from (source/signature)

Key Design Principles:
- Registry is IMMUTABLE: versions cannot be overwritten
- Registry is TRANSPARENT: publisher identity always visible
- Registry is NEUTRAL: no trust scoring, no recommendations
- Registry is AUDITABLE: all operations logged

Trust decisions are made by downstream systems (Phase F3),
not by the Registry itself.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from agentos.marketplace.manifest import (
    CapabilityManifest,
    load_manifest,
    normalize_manifest,
    validate_manifest,
)

logger = logging.getLogger(__name__)


class RegistryError(Exception):
    """Base exception for registry errors."""
    pass


class VersionConflictError(RegistryError):
    """Raised when attempting to register a capability version that already exists."""
    pass


class PublisherNotFoundError(RegistryError):
    """Raised when a publisher does not exist."""
    pass


class CapabilityNotFoundError(RegistryError):
    """Raised when a capability is not found."""
    pass


class MarketplaceRegistry:
    """Marketplace Registry for capability registration and discovery.

    This class provides a minimal, transparent ledger for capability registration.
    It does NOT make trust decisions or recommendations - it only records facts:
    - Who published what
    - When it was published
    - What the manifest contains

    All operations are audited to the database for complete traceability.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        """Initialize the Marketplace Registry.

        Args:
            db_path: Path to SQLite database. If None, uses default AgentOS database.
        """
        if db_path is None:
            from agentos.core.storage.paths import component_db_path
            db_path = component_db_path("agentos")

        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise RegistryError(f"Database not found: {self.db_path}. Run 'agentos init' first.")

        logger.info(f"MarketplaceRegistry initialized with database: {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Access columns by name
        return conn

    def _audit_log(
        self,
        capability_id: str,
        publisher_id: str,
        action: str,
        actor: str = "system",
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log an audit event.

        Args:
            capability_id: Capability ID
            publisher_id: Publisher ID
            action: Action performed (register, deprecate, remove, restore)
            actor: Who performed the action
            reason: Human-readable reason
            metadata: Additional metadata
        """
        conn = self._get_connection()
        try:
            timestamp_ms = int(time.time() * 1000)
            metadata_json = json.dumps(metadata) if metadata else None

            conn.execute(
                """
                INSERT INTO marketplace_audit_log
                (capability_id, publisher_id, action, actor, timestamp_ms, reason, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (capability_id, publisher_id, action, actor, timestamp_ms, reason, metadata_json),
            )
            conn.commit()
        finally:
            conn.close()

    def register_publisher(
        self,
        publisher_id: str,
        name: str,
        contact: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Register a new publisher.

        Publishers must be registered before they can publish capabilities.

        Args:
            publisher_id: Unique publisher ID (e.g., "official", "community.john")
            name: Publisher display name
            contact: Contact email or URL
            metadata: Additional metadata (website, description, etc.)

        Returns:
            The publisher_id

        Raises:
            RegistryError: If publisher already exists
        """
        conn = self._get_connection()
        try:
            # Check if publisher already exists
            existing = conn.execute(
                "SELECT publisher_id FROM marketplace_publishers WHERE publisher_id = ?",
                (publisher_id,),
            ).fetchone()

            if existing:
                raise RegistryError(f"Publisher already exists: {publisher_id}")

            # Insert publisher
            timestamp_ms = int(time.time() * 1000)
            metadata_json = json.dumps(metadata) if metadata else None

            conn.execute(
                """
                INSERT INTO marketplace_publishers
                (publisher_id, name, contact, verified, registered_at_ms, metadata)
                VALUES (?, ?, ?, 0, ?, ?)
                """,
                (publisher_id, name, contact, timestamp_ms, metadata_json),
            )
            conn.commit()

            logger.info(f"Registered publisher: {publisher_id} ({name})")
            return publisher_id

        finally:
            conn.close()

    def register_capability(
        self,
        manifest_path: Union[str, Path],
        actor: str = "system",
        force: bool = False,
    ) -> str:
        """Register a capability from a manifest file.

        This is the primary method for adding capabilities to the registry.
        The manifest is validated, and if valid, registered with complete history.

        Args:
            manifest_path: Path to capability manifest YAML file
            actor: Who is registering (for audit trail)
            force: If True, allow re-registration (NOT RECOMMENDED - breaks immutability)

        Returns:
            Full capability_id (e.g., "official.web_scraper.v1.0.0")

        Raises:
            VersionConflictError: If version already exists (and force=False)
            PublisherNotFoundError: If publisher is not registered
            ValueError: If manifest is invalid
        """
        # Load and validate manifest
        manifest = load_manifest(manifest_path)
        is_valid, errors = validate_manifest(manifest)

        if not is_valid:
            error_msg = "Manifest validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)

        # Check publisher exists
        conn = self._get_connection()
        try:
            publisher = conn.execute(
                "SELECT publisher_id, name FROM marketplace_publishers WHERE publisher_id = ?",
                (manifest.publisher.publisher_id,),
            ).fetchone()

            if not publisher:
                raise PublisherNotFoundError(
                    f"Publisher not found: {manifest.publisher.publisher_id}. "
                    "Register the publisher first with register_publisher()."
                )

            # Build capability IDs
            capability_name = f"{manifest.publisher.publisher_id}.{manifest.metadata.name}"
            capability_id = f"{capability_name}.v{manifest.capability_version}"

            # Check for version conflict
            existing = conn.execute(
                "SELECT capability_id FROM marketplace_capabilities WHERE capability_id = ?",
                (capability_id,),
            ).fetchone()

            if existing and not force:
                raise VersionConflictError(
                    f"Capability version already exists: {capability_id}. "
                    "Versions are immutable and cannot be overwritten. "
                    "To publish a new version, increment the capability_version in the manifest."
                )

            if existing and force:
                logger.warning(f"FORCE mode: Overwriting existing capability: {capability_id}")

            # Normalize manifest to JSON
            manifest_json = json.dumps(normalize_manifest(manifest))
            timestamp_ms = int(time.time() * 1000)

            # Insert or replace capability
            if force and existing:
                conn.execute(
                    """
                    UPDATE marketplace_capabilities
                    SET manifest_json = ?, published_at_ms = ?
                    WHERE capability_id = ?
                    """,
                    (manifest_json, timestamp_ms, capability_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO marketplace_capabilities
                    (capability_id, capability_name, publisher_id, capability_type,
                     version, manifest_json, signature, status, published_at_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
                    """,
                    (
                        capability_id,
                        capability_name,
                        manifest.publisher.publisher_id,
                        manifest.metadata.category or "general",
                        manifest.capability_version,
                        manifest_json,
                        manifest.signature,
                        timestamp_ms,
                    ),
                )

            conn.commit()

            # Audit log
            self._audit_log(
                capability_id=capability_id,
                publisher_id=manifest.publisher.publisher_id,
                action="register",
                actor=actor,
                reason=f"Registered from {manifest_path}",
            )

            logger.info(f"Registered capability: {capability_id}")
            return capability_id

        finally:
            conn.close()

    def query_capability(self, capability_id: str) -> Dict[str, Any]:
        """Query a capability by its full ID.

        Args:
            capability_id: Full capability ID (e.g., "official.web_scraper.v1.0.0")

        Returns:
            Dictionary containing:
            - capability_id
            - capability_name
            - publisher_id
            - publisher_name
            - publisher_verified
            - capability_type
            - version
            - manifest (full manifest as dict)
            - status
            - published_at_ms
            - published_at_iso

        Raises:
            CapabilityNotFoundError: If capability does not exist
        """
        conn = self._get_connection()
        try:
            row = conn.execute(
                """
                SELECT
                    c.capability_id,
                    c.capability_name,
                    c.publisher_id,
                    p.name as publisher_name,
                    p.verified as publisher_verified,
                    c.capability_type,
                    c.version,
                    c.manifest_json,
                    c.status,
                    c.published_at_ms,
                    datetime(c.published_at_ms / 1000, 'unixepoch') as published_at_iso
                FROM marketplace_capabilities c
                JOIN marketplace_publishers p ON c.publisher_id = p.publisher_id
                WHERE c.capability_id = ?
                """,
                (capability_id,),
            ).fetchone()

            if not row:
                raise CapabilityNotFoundError(f"Capability not found: {capability_id}")

            return {
                "capability_id": row["capability_id"],
                "capability_name": row["capability_name"],
                "publisher_id": row["publisher_id"],
                "publisher_name": row["publisher_name"],
                "publisher_verified": bool(row["publisher_verified"]),
                "capability_type": row["capability_type"],
                "version": row["version"],
                "manifest": json.loads(row["manifest_json"]),
                "status": row["status"],
                "published_at_ms": row["published_at_ms"],
                "published_at_iso": row["published_at_iso"],
            }

        finally:
            conn.close()

    def list_by_publisher(self, publisher_id: str) -> List[Dict[str, Any]]:
        """List all capabilities published by a publisher.

        Args:
            publisher_id: Publisher ID

        Returns:
            List of capability summaries (without full manifest)

        Raises:
            PublisherNotFoundError: If publisher does not exist
        """
        conn = self._get_connection()
        try:
            # Verify publisher exists
            publisher = conn.execute(
                "SELECT publisher_id FROM marketplace_publishers WHERE publisher_id = ?",
                (publisher_id,),
            ).fetchone()

            if not publisher:
                raise PublisherNotFoundError(f"Publisher not found: {publisher_id}")

            # Query capabilities
            rows = conn.execute(
                """
                SELECT
                    capability_id,
                    capability_name,
                    capability_type,
                    version,
                    status,
                    published_at_ms,
                    datetime(published_at_ms / 1000, 'unixepoch') as published_at_iso
                FROM marketplace_capabilities
                WHERE publisher_id = ?
                ORDER BY capability_name, published_at_ms DESC
                """,
                (publisher_id,),
            ).fetchall()

            return [
                {
                    "capability_id": row["capability_id"],
                    "capability_name": row["capability_name"],
                    "capability_type": row["capability_type"],
                    "version": row["version"],
                    "status": row["status"],
                    "published_at_ms": row["published_at_ms"],
                    "published_at_iso": row["published_at_iso"],
                }
                for row in rows
            ]

        finally:
            conn.close()

    def get_version_history(self, capability_name: str) -> List[Dict[str, Any]]:
        """Get all versions of a capability.

        Args:
            capability_name: Base capability name (e.g., "official.web_scraper")

        Returns:
            List of versions, ordered newest first

        Raises:
            CapabilityNotFoundError: If no versions exist
        """
        conn = self._get_connection()
        try:
            rows = conn.execute(
                """
                SELECT
                    capability_id,
                    version,
                    status,
                    published_at_ms,
                    datetime(published_at_ms / 1000, 'unixepoch') as published_at_iso
                FROM marketplace_capabilities
                WHERE capability_name = ?
                ORDER BY published_at_ms DESC
                """,
                (capability_name,),
            ).fetchall()

            if not rows:
                raise CapabilityNotFoundError(f"No versions found for: {capability_name}")

            return [
                {
                    "capability_id": row["capability_id"],
                    "version": row["version"],
                    "status": row["status"],
                    "published_at_ms": row["published_at_ms"],
                    "published_at_iso": row["published_at_iso"],
                }
                for row in rows
            ]

        finally:
            conn.close()

    def verify_manifest(self, manifest_path: Union[str, Path]) -> Tuple[bool, List[str]]:
        """Verify a manifest file without registering it.

        Useful for pre-flight checks before registration.

        Args:
            manifest_path: Path to manifest file

        Returns:
            Tuple of (is_valid, error_messages)
        """
        try:
            manifest = load_manifest(manifest_path)
            return validate_manifest(manifest)
        except Exception as e:
            return False, [str(e)]

    def deprecate_capability(
        self,
        capability_id: str,
        actor: str = "system",
        reason: Optional[str] = None,
    ):
        """Mark a capability as deprecated.

        Deprecated capabilities remain in the registry but are marked for users
        to migrate away from them.

        Args:
            capability_id: Full capability ID
            actor: Who performed the deprecation
            reason: Reason for deprecation

        Raises:
            CapabilityNotFoundError: If capability does not exist
        """
        conn = self._get_connection()
        try:
            # Check capability exists
            row = conn.execute(
                "SELECT capability_id, publisher_id FROM marketplace_capabilities WHERE capability_id = ?",
                (capability_id,),
            ).fetchone()

            if not row:
                raise CapabilityNotFoundError(f"Capability not found: {capability_id}")

            # Update status
            timestamp_ms = int(time.time() * 1000)
            conn.execute(
                """
                UPDATE marketplace_capabilities
                SET status = 'deprecated', deprecated_at_ms = ?
                WHERE capability_id = ?
                """,
                (timestamp_ms, capability_id),
            )
            conn.commit()

            # Audit log
            self._audit_log(
                capability_id=capability_id,
                publisher_id=row["publisher_id"],
                action="deprecate",
                actor=actor,
                reason=reason,
            )

            logger.info(f"Deprecated capability: {capability_id}")

        finally:
            conn.close()

    def list_publishers(self) -> List[Dict[str, Any]]:
        """List all registered publishers.

        Returns:
            List of publisher information
        """
        conn = self._get_connection()
        try:
            rows = conn.execute(
                """
                SELECT
                    publisher_id,
                    name,
                    contact,
                    verified,
                    registered_at_ms,
                    datetime(registered_at_ms / 1000, 'unixepoch') as registered_at_iso
                FROM marketplace_publishers
                ORDER BY verified DESC, publisher_id
                """
            ).fetchall()

            return [
                {
                    "publisher_id": row["publisher_id"],
                    "name": row["name"],
                    "contact": row["contact"],
                    "verified": bool(row["verified"]),
                    "registered_at_ms": row["registered_at_ms"],
                    "registered_at_iso": row["registered_at_iso"],
                }
                for row in rows
            ]

        finally:
            conn.close()


__all__ = [
    "MarketplaceRegistry",
    "RegistryError",
    "VersionConflictError",
    "PublisherNotFoundError",
    "CapabilityNotFoundError",
]
