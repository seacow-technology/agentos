"""Content Registry - manages content metadata and lifecycle.

🚨 RED LINE #1: This class does NOT execute content.
Only stores metadata, validates schema, and manages status.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agentos.core.content.schema_loader import ContentSchemaLoader
from agentos.core.content.types import ContentTypeRegistry
from agentos.store import get_db_path
from agentos.core.time import utc_now_iso



class ContentRegistry:
    """Content Registry - manages content metadata and lifecycle.

    This class is responsible for:
    - Registering content (storing metadata)
    - Validating content schema
    - Managing content status (draft/active/deprecated/frozen)
    - Recording audit logs

    🚨 RED LINE #1: This class does NOT execute content.
    Methods like execute(), run(), apply() MUST NOT exist here.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize content registry.

        Args:
            db_path: Path to database file (defaults to component_db_path("agentos"))
        """
        self.db_path = db_path or get_db_path()
        self.schema_loader = ContentSchemaLoader()
        self.type_registry = ContentTypeRegistry()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Database not initialized. Run 'agentos init' and 'agentos migrate --to 0.5.0' first."
            )
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _calculate_checksum(self, content: dict) -> str:
        """Calculate SHA-256 checksum of content.

        Args:
            content: Content dict

        Returns:
            Hex-encoded SHA-256 checksum
        """
        # Serialize content deterministically (sorted keys)
        content_str = json.dumps(content, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(content_str.encode()).hexdigest()

    def _log_audit(self, event: str, content_id: str, version: str, metadata: Optional[dict] = None):
        """Log audit event.

        Args:
            event: Event type (registered, activated, deprecated, frozen, unfrozen, superseded)
            content_id: Content ID
            version: Content version
            metadata: Optional additional metadata
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO content_audit_log (event, content_id, version, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (event, content_id, version, json.dumps(metadata) if metadata else None),
        )

        conn.commit()
        conn.close()

    def register(self, content: dict) -> str:
        """Register content (metadata storage, does NOT execute).

        Args:
            content: Content dict (must conform to content_base.schema.json)

        Returns:
            Content ID

        Raises:
            ValueError: If validation fails or content already registered
        """
        # Validate base schema
        is_valid, errors = self.schema_loader.validate_content_base(content)
        if not is_valid:
            raise ValueError(f"Content validation failed:\n" + "\n".join(errors))

        # Validate type exists and is not placeholder
        content_type = content["type"]
        self.type_registry.validate_type_exists(content_type)

        # Validate type-specific schema
        type_descriptor = self.type_registry.get_type(content_type)
        is_valid_type, type_errors = self.schema_loader.validate_content_type(
            content, type_descriptor.schema_ref
        )
        if not is_valid_type:
            raise ValueError(f"Type schema validation failed:\n" + "\n".join(type_errors))

        # Calculate checksum
        checksum = self._calculate_checksum(content)
        if "metadata" not in content:
            content["metadata"] = {}
        content["metadata"]["checksum"] = checksum

        # Extract fields
        content_id = content["id"]
        version = content["version"]
        status = content.get("status", "draft")
        parent_version = content["metadata"].get("parent_version")
        change_reason = content["metadata"].get("change_reason")
        is_root = 1 if content["metadata"].get("is_root", False) else 0
        metadata = json.dumps(content.get("metadata", {}))
        spec = json.dumps(content.get("spec", {}))

        # Check if already registered
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM content_registry WHERE id = ? AND version = ?", (content_id, version)
        )
        if cursor.fetchone():
            conn.close()
            raise ValueError(f"Content already registered: {content_id} v{version}")

        # Insert
        try:
            cursor.execute(
                """
                INSERT INTO content_registry (
                    id, type, version, status, checksum,
                    parent_version, change_reason, is_root,
                    metadata, spec
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    content_id,
                    content_type,
                    version,
                    status,
                    checksum,
                    parent_version,
                    change_reason,
                    is_root,
                    metadata,
                    spec,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            conn.close()
            if "CHECK constraint failed" in str(e):
                raise ValueError(
                    f"Lineage constraint violated: content must be either root (is_root=1, no parent) "
                    f"or evolved (is_root=0, parent_version + change_reason required)"
                )
            raise ValueError(f"Database constraint violated: {e}")

        conn.close()

        # Log audit
        self._log_audit("registered", content_id, version, {"type": content_type, "status": status})

        return content_id

    def get(self, content_id: str, version: Optional[str] = None) -> Optional[dict]:
        """Get content by ID and version (read metadata, does NOT execute).

        Args:
            content_id: Content ID
            version: Content version (if None, returns active version or latest draft)

        Returns:
            Content dict or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if version:
            cursor.execute(
                "SELECT * FROM content_registry WHERE id = ? AND version = ?", (content_id, version)
            )
        else:
            # Get active version, or latest draft if no active
            cursor.execute(
                """
                SELECT * FROM content_registry 
                WHERE id = ? 
                ORDER BY 
                    CASE status WHEN 'active' THEN 1 ELSE 2 END,
                    created_at DESC
                LIMIT 1
                """,
                (content_id,),
            )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        # Reconstruct content dict
        return {
            "id": row["id"],
            "type": row["type"],
            "version": row["version"],
            "status": row["status"],
            "metadata": {
                **json.loads(row["metadata"]),
                "checksum": row["checksum"],
                "parent_version": row["parent_version"],
                "change_reason": row["change_reason"],
                "is_root": bool(row["is_root"]),
                "created_at": row["created_at"],
                "activated_at": row["activated_at"],
                "deprecated_at": row["deprecated_at"],
                "frozen_at": row["frozen_at"],
            },
            "spec": json.loads(row["spec"]),
        }

    def list(
        self, type_: Optional[str] = None, status: Optional[str] = None, limit: int = 100
    ) -> list[dict]:
        """List content (read metadata, does NOT execute).

        Args:
            type_: Filter by content type
            status: Filter by status
            limit: Maximum number of results

        Returns:
            List of content dicts
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM content_registry WHERE 1=1"
        params: list[Any] = []

        if type_:
            query += " AND type = ?"
            params.append(type_)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row["id"],
                "type": row["type"],
                "version": row["version"],
                "status": row["status"],
                "metadata": {
                    **json.loads(row["metadata"]),
                    "checksum": row["checksum"],
                    "parent_version": row["parent_version"],
                    "change_reason": row["change_reason"],
                    "is_root": bool(row["is_root"]),
                    "created_at": row["created_at"],
                },
                "spec": json.loads(row["spec"]),
            }
            for row in rows
        ]

    def update_status(self, content_id: str, version: str, new_status: str) -> bool:
        """Update content status (state management, does NOT execute).

        Args:
            content_id: Content ID
            version: Content version
            new_status: New status (draft/active/deprecated/frozen)

        Returns:
            True if updated

        Raises:
            ValueError: If content not found or invalid status
        """
        valid_statuses = ["draft", "active", "deprecated", "frozen"]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status} (must be one of {valid_statuses})")

        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if exists
        cursor.execute(
            "SELECT status FROM content_registry WHERE id = ? AND version = ?", (content_id, version)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Content not found: {content_id} v{version}")

        old_status = row["status"]

        # Update status and timestamp
        now = utc_now_iso()
        timestamp_field = None

        if new_status == "active":
            timestamp_field = "activated_at"
        elif new_status == "deprecated":
            timestamp_field = "deprecated_at"
        elif new_status == "frozen":
            timestamp_field = "frozen_at"

        if timestamp_field:
            cursor.execute(
                f"""
                UPDATE content_registry 
                SET status = ?, {timestamp_field} = ?
                WHERE id = ? AND version = ?
                """,
                (new_status, now, content_id, version),
            )
        else:
            cursor.execute(
                "UPDATE content_registry SET status = ? WHERE id = ? AND version = ?",
                (new_status, content_id, version),
            )

        conn.commit()
        conn.close()

        # Log audit
        self._log_audit(
            new_status,
            content_id,
            version,
            {"old_status": old_status, "new_status": new_status},
        )

        return True

    # 🚨 RED LINE #1: The following methods MUST NOT exist in this class
    #
    # def execute(self, content_id: str, *args, **kwargs) -> Any:
    #     raise NotImplementedError("ContentRegistry does not execute content")
    #
    # def run(self, content_id: str, *args, **kwargs) -> Any:
    #     raise NotImplementedError("ContentRegistry does not run content")
    #
    # def apply(self, content_id: str, *args, **kwargs) -> Any:
    #     raise NotImplementedError("ContentRegistry does not apply content")
    #
    # Execution belongs in separate orchestrator/scheduler modules, not in the registry.
