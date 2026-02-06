"""
Knowledge Source Repository - Persistent storage for RAG data sources

This module provides CRUD operations for knowledge data sources with:
- Persistent storage in SQLite
- Audit logging for all changes
- Thread-safe operations via SQLiteWriter
- Type-safe query methods
"""

import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional
from pathlib import Path

from agentos.core.time import utc_now_ms
from agentos.store import get_db, get_writer

logger = logging.getLogger(__name__)

# Valid status values per schema constraint
VALID_STATUSES = {"active", "inactive", "error", "pending", "indexed", "failed"}


class KnowledgeSourceRepo:
    """Repository for managing knowledge data sources"""

    def __init__(self):
        """Initialize repository"""
        self.writer = get_writer()

    def list(
        self,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List knowledge data sources with optional filtering

        Args:
            source_type: Filter by source type (local, web, api, database, etc)
            status: Filter by status (active, inactive, error, pending, indexed, failed)
            limit: Maximum number of results (default: 100)

        Returns:
            List of source dictionaries

        Example:
            >>> repo = KnowledgeSourceRepo()
            >>> sources = repo.list(source_type='local', status='active')
        """
        conn = get_db()
        cursor = conn.cursor()

        # Build query with filters
        query = "SELECT * FROM knowledge_sources WHERE 1=1"
        params = []

        if source_type:
            query += " AND source_type = ?"
            params.append(source_type)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        try:
            rows = cursor.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to list knowledge sources: {e}")
            return []

    def get(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single knowledge source by ID

        Args:
            source_id: Source ID

        Returns:
            Source dictionary or None if not found

        Example:
            >>> repo = KnowledgeSourceRepo()
            >>> source = repo.get('source-123')
        """
        conn = get_db()
        cursor = conn.cursor()

        try:
            row = cursor.execute(
                "SELECT * FROM knowledge_sources WHERE id = ?", (source_id,)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get knowledge source {source_id}: {e}")
            return None

    def create(self, source: Dict[str, Any]) -> str:
        """
        Create a new knowledge source

        Args:
            source: Source data dictionary with fields:
                - id: Source ID (required)
                - name: Display name
                - source_type: Type (local, web, api, database, etc)
                - uri: Source URI/path
                - auth_config: Authentication config (JSON)
                - options: Additional options (JSON)
                - status: Status (default: 'pending')
                - metadata: Additional metadata (JSON)

        Returns:
            Source ID

        Raises:
            ValueError: If required fields are missing
            sqlite3.Error: If database operation fails

        Example:
            >>> repo = KnowledgeSourceRepo()
            >>> source_id = repo.create({
            ...     'id': 'source-123',
            ...     'name': 'My Docs',
            ...     'source_type': 'local',
            ...     'uri': '/path/to/docs',
            ...     'options': {'recursive': True}
            ... })
        """
        # Validate required fields
        required_fields = ["id", "name", "source_type", "uri"]
        for field in required_fields:
            if field not in source:
                raise ValueError(f"Missing required field: {field}")

        source_id = source["id"]
        now_ms = utc_now_ms()

        # Prepare insert data
        insert_data = {
            "id": source_id,
            "name": source["name"],
            "source_type": source["source_type"],
            "uri": source["uri"],
            "auth_config": json.dumps(source.get("auth_config")) if source.get("auth_config") else None,
            "options": json.dumps(source.get("options")) if source.get("options") else None,
            "status": source.get("status", "pending"),
            "created_at": now_ms,
            "updated_at": now_ms,
            "last_indexed_at": source.get("last_indexed_at"),
            "chunk_count": source.get("chunk_count", 0),
            "metadata": json.dumps(source.get("metadata")) if source.get("metadata") else None,
        }

        def _insert(conn: sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO knowledge_sources (
                    id, name, source_type, uri, auth_config, options,
                    status, created_at, updated_at, last_indexed_at,
                    chunk_count, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    insert_data["id"],
                    insert_data["name"],
                    insert_data["source_type"],
                    insert_data["uri"],
                    insert_data["auth_config"],
                    insert_data["options"],
                    insert_data["status"],
                    insert_data["created_at"],
                    insert_data["updated_at"],
                    insert_data["last_indexed_at"],
                    insert_data["chunk_count"],
                    insert_data["metadata"],
                ),
            )
            conn.commit()

            # Log audit entry
            self._log_audit(
                conn,
                source_id=source_id,
                action="create",
                old_values=None,
                new_values=insert_data,
            )

        try:
            self.writer.submit(_insert, timeout=10.0)
            logger.info(f"Created knowledge source: {source_id}")
            return source_id
        except Exception as e:
            logger.error(f"Failed to create knowledge source: {e}")
            raise

    def update(self, source_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing knowledge source

        Supports updating status, last_indexed_at, chunk_count, metadata, and other fields.
        Automatically updates updated_at timestamp.

        Args:
            source_id: Source ID
            updates: Dictionary of fields to update. Supported fields:
                - status: One of {pending, active, indexed, inactive, error, failed}
                - last_indexed_at: Unix timestamp in milliseconds
                - chunk_count: Number of indexed chunks
                - metadata: Additional metadata dict
                - Other fields: name, uri, auth_config, options, etc.

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If status value is not valid

        Example:
            >>> repo = KnowledgeSourceRepo()
            >>> repo.update('source-123', {
            ...     'status': 'indexed',
            ...     'chunk_count': 150,
            ...     'last_indexed_at': 1738416000000
            ... })
        """
        # Get current values for audit log
        old_source = self.get(source_id)
        if not old_source:
            logger.warning(f"Source not found: {source_id}")
            return False

        # Validate status if provided
        if "status" in updates:
            status = updates["status"]
            if status not in VALID_STATUSES:
                raise ValueError(
                    f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
                )

        now_ms = utc_now_ms()
        updates["updated_at"] = now_ms

        # Build UPDATE query dynamically
        set_clauses = []
        values = []
        changed_fields = []

        for field, value in updates.items():
            if field == "id":  # Don't allow ID updates
                continue

            # Convert dicts to JSON strings for storage
            if field in ["auth_config", "options", "metadata"] and isinstance(value, dict):
                value = json.dumps(value)

            set_clauses.append(f"{field} = ?")
            values.append(value)
            changed_fields.append(field)

        if not set_clauses:
            logger.warning("No valid fields to update")
            return False

        values.append(source_id)  # For WHERE clause

        def _update(conn: sqlite3.Connection):
            cursor = conn.cursor()
            query = f"UPDATE knowledge_sources SET {', '.join(set_clauses)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()

            # Log audit entry
            self._log_audit(
                conn,
                source_id=source_id,
                action="update",
                old_values={k: old_source.get(k) for k in changed_fields},
                new_values={k: updates.get(k) for k in changed_fields},
                changed_fields=changed_fields,
            )

        try:
            self.writer.submit(_update, timeout=10.0)
            logger.info(f"Updated knowledge source: {source_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update knowledge source: {e}")
            return False

    def update_status(
        self,
        source_id: str,
        status: str,
        error: Optional[str] = None,
        chunk_count: Optional[int] = None,
        last_indexed_at: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Update source status with optional error and indexing metadata

        Specialized method for SourceBridge to update status synchronously.
        Combines status, error, chunk_count, and last_indexed_at updates.

        Args:
            source_id: Source ID
            status: New status (pending|active|indexed|inactive|error|failed)
            error: Optional error message to store in metadata.last_error
            chunk_count: Optional chunk count to update
            last_indexed_at: Optional last indexed time (Unix timestamp ms)

        Returns:
            Updated source dict or empty dict if failed

        Raises:
            ValueError: If status is invalid

        Example:
            >>> repo = KnowledgeSourceRepo()
            >>> repo.update_status(
            ...     'source-123',
            ...     status='indexed',
            ...     chunk_count=100,
            ...     last_indexed_at=1738416000000
            ... )
            >>> repo.update_status(
            ...     'source-123',
            ...     status='error',
            ...     error='File not found: /path/to/docs'
            ... )
        """
        # Validate status
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
            )

        updates = {"status": status}

        # Update indexing metadata if provided
        if chunk_count is not None:
            updates["chunk_count"] = chunk_count

        if last_indexed_at is not None:
            updates["last_indexed_at"] = last_indexed_at

        # Store error in metadata if provided
        if error is not None:
            current_source = self.get(source_id)
            if current_source:
                metadata = current_source.get("metadata", {}) or {}
                if not isinstance(metadata, dict):
                    metadata = {}
                metadata["last_error"] = error
                updates["metadata"] = metadata

        # Perform update
        success = self.update(source_id, updates)

        if success:
            # Return updated source
            updated = self.get(source_id)
            return updated if updated else {}
        else:
            return {}

    def delete(self, source_id: str) -> bool:
        """
        Delete a knowledge source

        Note: Audit entries are preserved even after deletion (no cascade).

        Args:
            source_id: Source ID

        Returns:
            True if successful, False otherwise

        Example:
            >>> repo = KnowledgeSourceRepo()
            >>> repo.delete('source-123')
        """
        # Get current values for audit log
        old_source = self.get(source_id)
        if not old_source:
            logger.warning(f"Source not found: {source_id}")
            return False

        def _delete(conn: sqlite3.Connection):
            cursor = conn.cursor()

            # Log audit entry before deletion
            self._log_audit(
                conn,
                source_id=source_id,
                action="delete",
                old_values=old_source,
                new_values=None,
            )

            # Delete source (audit entries will NOT cascade due to schema change)
            cursor.execute("DELETE FROM knowledge_sources WHERE id = ?", (source_id,))
            conn.commit()

        try:
            self.writer.submit(_delete, timeout=10.0)
            logger.info(f"Deleted knowledge source: {source_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete knowledge source: {e}")
            return False

    def get_audit_log(
        self, source_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit log entries

        Args:
            source_id: Filter by source ID (optional)
            limit: Maximum number of entries (default: 100)

        Returns:
            List of audit log entries

        Example:
            >>> repo = KnowledgeSourceRepo()
            >>> log = repo.get_audit_log(source_id='source-123')
        """
        conn = get_db()
        cursor = conn.cursor()

        query = "SELECT * FROM knowledge_source_audit WHERE 1=1"
        params = []

        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        try:
            rows = cursor.execute(query, params).fetchall()
            result = []
            for row in rows:
                entry = dict(row)
                # Parse JSON fields
                for field in ["changed_fields", "old_values", "new_values", "metadata"]:
                    if entry.get(field):
                        try:
                            entry[field] = json.loads(entry[field])
                        except json.JSONDecodeError:
                            pass
                result.append(entry)
            return result
        except sqlite3.Error as e:
            logger.error(f"Failed to get audit log: {e}")
            return []

    def _log_audit(
        self,
        conn: sqlite3.Connection,
        source_id: str,
        action: str,
        old_values: Optional[Dict[str, Any]],
        new_values: Optional[Dict[str, Any]],
        changed_fields: Optional[List[str]] = None,
    ):
        """
        Log an audit entry for a source change

        Args:
            conn: Database connection
            source_id: Source ID
            action: Action type (create, update, delete)
            old_values: Old values snapshot
            new_values: New values snapshot
            changed_fields: List of changed field names
        """
        import uuid

        audit_id = str(uuid.uuid4())
        now_ms = utc_now_ms()

        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO knowledge_source_audit (
                id, source_id, action, changed_fields, old_values, new_values, timestamp, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                source_id,
                action,
                json.dumps(changed_fields) if changed_fields else None,
                json.dumps(old_values) if old_values else None,
                json.dumps(new_values) if new_values else None,
                now_ms,
                None,  # metadata - can be extended later
            ),
        )

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """
        Convert SQLite row to dictionary with JSON parsing

        Args:
            row: SQLite row object

        Returns:
            Dictionary representation
        """
        result = dict(row)

        # Parse JSON fields
        for field in ["auth_config", "options", "metadata"]:
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except json.JSONDecodeError:
                    # Keep as string if not valid JSON
                    pass

        return result
