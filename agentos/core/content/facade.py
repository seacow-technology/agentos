"""Unified Content Facade - provides unified interface for all content types.

🚨 RED LINE #2: This class is READ-ONLY for policy_lineage and memory_items.
Any write operations to these tables will break backward compatibility.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from agentos.core.content.registry import ContentRegistry
from agentos.store import get_db_path


class FacadePermissionError(PermissionError):
    """RED LINE VIOLATION: Facade attempted to write to read-only tables."""

    pass


class UnifiedContentFacade:
    """Unified Content Facade - provides unified interface for all content types.

    This facade provides a single interface to read content from:
    - content_registry (new content)
    - policy_lineage (existing policy content)
    - memory_items (existing memory content)

    🚨 RED LINE #2: This class is READ-ONLY for policy_lineage and memory_items.
    Write operations to these tables are strictly forbidden.
    """

    # 🚨 RED LINE #2: Read-only tables (write forbidden)
    _READONLY_TABLES = frozenset(["policy_lineage", "memory_items", "memory_audit_log"])

    def __init__(self, registry: Optional[ContentRegistry] = None, db_path: Optional[Path] = None):
        """Initialize facade.

        Args:
            registry: ContentRegistry instance (creates new if None)
            db_path: Path to database file (defaults to component_db_path("agentos"))
        """
        self.registry = registry or ContentRegistry()
        self.db_path = db_path or get_db_path()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Database not initialized. Run 'agentos init' and 'agentos migrate --to 0.5.0' first."
            )
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _execute_query(self, table: str, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Internal query executor (with write operation detection).

        Args:
            table: Table name
            query: SQL query
            params: Query parameters

        Returns:
            List of rows

        Raises:
            FacadePermissionError: If attempting to write to read-only table (RED LINE #2)
        """
        # 🚨 RED LINE #2: Detect write operations
        if table in self._READONLY_TABLES:
            write_keywords = ["INSERT", "UPDATE", "DELETE", "ALTER", "DROP", "TRUNCATE", "REPLACE"]
            query_upper = query.upper()
            if any(kw in query_upper for kw in write_keywords):
                raise FacadePermissionError(
                    f"RED LINE VIOLATION: Facade cannot modify {table}. "
                    f"Content Registry must not write to existing policy/memory stores. "
                    f"Attempted query: {query[:100]}..."
                )

        # Execute query
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return rows

    def get_content(self, type_: str, id_: str, version: Optional[str] = None) -> Optional[dict]:
        """Get content by type, ID, and version (unified interface).

        Args:
            type_: Content type (policy, memory, agent, workflow, etc.)
            id_: Content ID
            version: Content version (optional, for versioned types)

        Returns:
            Content dict or None if not found
        """
        # Route to appropriate storage
        if type_ == "policy":
            return self._get_from_policy_lineage(id_, version)
        elif type_ == "memory":
            return self._get_from_memory_items(id_)
        else:
            # New content types (agent, workflow, command, rule, etc.)
            return self.registry.get(id_, version)

    def list_content(
        self, type_: str, filters: Optional[dict[str, Any]] = None, limit: int = 100
    ) -> list[dict]:
        """List content by type (unified interface).

        Args:
            type_: Content type (policy, memory, agent, workflow, etc.)
            filters: Optional filters (status, scope, etc.)
            limit: Maximum number of results

        Returns:
            List of content dicts
        """
        filters = filters or {}

        # Route to appropriate storage
        if type_ == "policy":
            return self._list_from_policy_lineage(filters, limit)
        elif type_ == "memory":
            return self._list_from_memory_items(filters, limit)
        else:
            # New content types
            return self.registry.list(
                type_=type_, status=filters.get("status"), limit=limit
            )

    def _get_from_policy_lineage(self, policy_id: str, version: Optional[str]) -> Optional[dict]:
        """Get policy from policy_lineage table (READ-ONLY).

        Args:
            policy_id: Policy ID
            version: Policy version (optional)

        Returns:
            Policy dict or None
        """
        if version:
            query = "SELECT * FROM policy_lineage WHERE policy_id = ?"
            params = (policy_id,)
        else:
            # Get active policy
            query = """
                SELECT * FROM policy_lineage 
                WHERE policy_id = ? AND status = 'active'
                LIMIT 1
            """
            params = (policy_id,)

        try:
            rows = self._execute_query("policy_lineage", query, params)
        except sqlite3.OperationalError:
            # Table doesn't exist (pre-v0.3)
            return None

        if not rows:
            return None

        row = rows[0]

        # Map to unified content format
        return {
            "id": row["policy_id"],
            "type": "policy",
            "version": "1.0.0",  # policy_lineage doesn't have explicit versions
            "status": row.get("status", "active"),
            "metadata": {
                "created_at": row.get("created_at"),
                "parent_version": row.get("parent_policy_id"),
                "source": "policy_lineage",
            },
            "spec": {
                "diff": json.loads(row["diff"]) if row.get("diff") else None,
                "rollback_conditions": (
                    json.loads(row["rollback_conditions"]) if row.get("rollback_conditions") else None
                ),
                "applied_to": json.loads(row["applied_to"]) if row.get("applied_to") else None,
            },
        }

    def _list_from_policy_lineage(self, filters: dict, limit: int) -> list[dict]:
        """List policies from policy_lineage table (READ-ONLY).

        Args:
            filters: Filters (status, etc.)
            limit: Maximum results

        Returns:
            List of policy dicts
        """
        query = "SELECT * FROM policy_lineage WHERE 1=1"
        params: list[Any] = []

        if filters.get("status"):
            query += " AND status = ?"
            params.append(filters["status"])

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        try:
            rows = self._execute_query("policy_lineage", query, tuple(params))
        except sqlite3.OperationalError:
            # Table doesn't exist
            return []

        return [
            {
                "id": row["policy_id"],
                "type": "policy",
                "version": "1.0.0",
                "status": row.get("status", "active"),
                "metadata": {
                    "created_at": row.get("created_at"),
                    "source": "policy_lineage",
                },
                "spec": {},
            }
            for row in rows
        ]

    def _get_from_memory_items(self, memory_id: str) -> Optional[dict]:
        """Get memory from memory_items table (READ-ONLY).

        Args:
            memory_id: Memory ID

        Returns:
            Memory dict or None
        """
        query = "SELECT * FROM memory_items WHERE id = ?"
        params = (memory_id,)

        try:
            rows = self._execute_query("memory_items", query, params)
        except sqlite3.OperationalError:
            # Table doesn't exist (pre-v0.2)
            return None

        if not rows:
            return None

        row = rows[0]

        # Map to unified content format
        return {
            "id": row["id"],
            "type": "memory",
            "version": "1.0.0",  # memory_items doesn't have versions
            "status": "active",
            "metadata": {
                "created_at": row.get("created_at"),
                "scope": row.get("scope"),
                "source": "memory_items",
            },
            "spec": {
                "memory_type": row.get("type"),
                "content": json.loads(row["content"]) if row.get("content") else None,
                "tags": json.loads(row["tags"]) if row.get("tags") else None,
                "confidence": row.get("confidence"),
            },
        }

    def _list_from_memory_items(self, filters: dict, limit: int) -> list[dict]:
        """List memories from memory_items table (READ-ONLY).

        Args:
            filters: Filters (scope, type, etc.)
            limit: Maximum results

        Returns:
            List of memory dicts
        """
        query = "SELECT * FROM memory_items WHERE 1=1"
        params: list[Any] = []

        if filters.get("scope"):
            query += " AND scope = ?"
            params.append(filters["scope"])

        if filters.get("memory_type"):
            query += " AND type = ?"
            params.append(filters["memory_type"])

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        try:
            rows = self._execute_query("memory_items", query, tuple(params))
        except sqlite3.OperationalError:
            # Table doesn't exist
            return []

        return [
            {
                "id": row["id"],
                "type": "memory",
                "version": "1.0.0",
                "status": "active",
                "metadata": {
                    "created_at": row.get("created_at"),
                    "scope": row.get("scope"),
                    "source": "memory_items",
                },
                "spec": {
                    "memory_type": row.get("type"),
                    "content": json.loads(row["content"]) if row.get("content") else None,
                },
            }
            for row in rows
        ]

    # 🚨 RED LINE #2: The following methods MUST NOT exist in this class
    #
    # def _write_to_policy_lineage(...):
    #     raise NotImplementedError("Facade is read-only for policy_lineage")
    #
    # def _update_memory_items(...):
    #     raise NotImplementedError("Facade is read-only for memory_items")
    #
    # Write operations belong in their original services (PolicyEvolutionEngine, MemoryService),
    # not in the facade.
