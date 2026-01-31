"""Network mode management for CommunicationOS.

This module provides network mode control to manage external communication access levels.
Network modes enable users to control when and how the system can access external resources.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
from agentos.core.storage.paths import component_db_path
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


class NetworkMode(str, Enum):
    """Network access modes.

    Modes (from most to least restrictive):
    - OFF: All external communication disabled
    - READONLY: Only read operations (fetch, search) allowed
    - ON: Full communication access (read + write operations)
    """

    OFF = "off"           # All communication disabled
    READONLY = "readonly" # Only read operations (fetch, search)
    ON = "on"             # Full access (read + write)


# Define read-only operations (allowed in READONLY mode)
READONLY_OPERATIONS = {
    "fetch",
    "search",
    "get",
    "read",
    "query",
    "list",
}

# Define write operations (blocked in READONLY mode)
WRITE_OPERATIONS = {
    "send",
    "post",
    "put",
    "delete",
    "create",
    "update",
    "write",
    "publish",
}


class NetworkModeManager:
    """Manager for network mode state and transitions.

    The NetworkModeManager controls the network access level for all
    external communication operations. It provides:
    - Persistent mode state storage
    - Mode validation and enforcement
    - Mode change auditing
    - Operation permission checking
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize network mode manager.

        Args:
            db_path: Path to SQLite database file (defaults to communicationos component db)
        """
        if db_path is None:
            db_path = component_db_path("communicationos")

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # In-memory cache of current mode
        self._current_mode: Optional[NetworkMode] = None

        # Initialize database
        self._init_database()

        # Load current mode from database
        self._load_mode()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection.

        Returns:
            SQLite connection
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self) -> None:
        """Initialize database schema for network mode state."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create network_mode_state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS network_mode_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                mode TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT,
                metadata TEXT
            )
        """)

        # Create network_mode_history table for audit trail
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS network_mode_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                previous_mode TEXT,
                new_mode TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                changed_by TEXT,
                reason TEXT,
                metadata TEXT
            )
        """)

        # Create index on history table
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_network_mode_history_changed_at
            ON network_mode_history(changed_at DESC)
        """)

        # Insert default mode if table is empty
        cursor.execute("SELECT COUNT(*) FROM network_mode_state")
        if cursor.fetchone()[0] == 0:
            default_mode = NetworkMode.ON
            now = utc_now_iso()
            cursor.execute(
                """
                INSERT INTO network_mode_state (id, mode, updated_at, updated_by, metadata)
                VALUES (1, ?, ?, ?, ?)
                """,
                (default_mode.value, now, "system", json.dumps({"initial": True}))
            )
            logger.info(f"Initialized network mode with default: {default_mode.value}")

        conn.commit()
        conn.close()
        logger.info(f"Initialized network mode database at: {self.db_path}")

    def _load_mode(self) -> None:
        """Load current mode from database into memory cache."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT mode FROM network_mode_state WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        if row:
            self._current_mode = NetworkMode(row["mode"])
            logger.debug(f"Loaded network mode: {self._current_mode.value}")
        else:
            # Fallback to default if not found
            self._current_mode = NetworkMode.ON
            logger.warning("Network mode not found in database, using default: ON")

    def get_mode(self) -> NetworkMode:
        """Get current network mode.

        Returns:
            Current network mode
        """
        if self._current_mode is None:
            self._load_mode()
        return self._current_mode

    def set_mode(
        self,
        mode: NetworkMode,
        updated_by: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set network mode.

        Args:
            mode: New network mode
            updated_by: Identifier of who/what changed the mode
            reason: Reason for the mode change
            metadata: Additional metadata for the change

        Returns:
            Dictionary with change information

        Raises:
            ValueError: If mode is invalid
        """
        # Validate mode
        if not isinstance(mode, NetworkMode):
            try:
                mode = NetworkMode(mode)
            except ValueError:
                raise ValueError(
                    f"Invalid network mode: {mode}. "
                    f"Valid modes: {', '.join([m.value for m in NetworkMode])}"
                )

        # Get previous mode
        previous_mode = self.get_mode()

        # Skip if mode hasn't changed
        if previous_mode == mode:
            logger.debug(f"Network mode unchanged: {mode.value}")
            return {
                "previous_mode": previous_mode.value,
                "new_mode": mode.value,
                "changed": False,
                "timestamp": utc_now_iso(),
            }

        # Update database
        conn = self._get_connection()
        cursor = conn.cursor()
        now = utc_now_iso()

        try:
            # Update current state
            cursor.execute(
                """
                UPDATE network_mode_state
                SET mode = ?, updated_at = ?, updated_by = ?, metadata = ?
                WHERE id = 1
                """,
                (mode.value, now, updated_by, json.dumps(metadata or {}))
            )

            # Insert history record
            cursor.execute(
                """
                INSERT INTO network_mode_history
                (previous_mode, new_mode, changed_at, changed_by, reason, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    previous_mode.value,
                    mode.value,
                    now,
                    updated_by,
                    reason,
                    json.dumps(metadata or {})
                )
            )

            conn.commit()

            # Update cache
            self._current_mode = mode

            logger.info(
                f"Network mode changed: {previous_mode.value} -> {mode.value} "
                f"(by: {updated_by or 'unknown'}, reason: {reason or 'none'})"
            )

            return {
                "previous_mode": previous_mode.value,
                "new_mode": mode.value,
                "changed": True,
                "timestamp": now,
                "updated_by": updated_by,
                "reason": reason,
            }

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to set network mode: {str(e)}")
            raise
        finally:
            conn.close()

    def is_operation_allowed(
        self,
        operation: str,
        current_mode: Optional[NetworkMode] = None,
    ) -> tuple[bool, Optional[str]]:
        """Check if an operation is allowed in the current network mode.

        Args:
            operation: Operation name (e.g., "fetch", "send", "search")
            current_mode: Optional mode to check against (defaults to current mode)

        Returns:
            Tuple of (is_allowed, reason_if_denied)
        """
        mode = current_mode or self.get_mode()
        operation_lower = operation.lower()

        # OFF mode: deny everything
        if mode == NetworkMode.OFF:
            return False, f"Network mode is OFF - all operations blocked"

        # READONLY mode: only allow read operations
        if mode == NetworkMode.READONLY:
            # Check if operation is explicitly a write operation
            if operation_lower in WRITE_OPERATIONS:
                return False, f"Network mode is READONLY - write operation '{operation}' blocked"

            # Check if operation is a known read operation
            if operation_lower in READONLY_OPERATIONS:
                return True, None

            # For unknown operations, be conservative and check naming patterns
            if any(write_op in operation_lower for write_op in WRITE_OPERATIONS):
                return False, f"Network mode is READONLY - operation '{operation}' appears to be a write operation"

            # If it doesn't match write patterns, allow it (optimistic for reads)
            return True, None

        # ON mode: allow everything
        return True, None

    def get_mode_info(self) -> Dict[str, Any]:
        """Get detailed information about current network mode.

        Returns:
            Dictionary with mode information, history, and statistics
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get current state
        cursor.execute("SELECT * FROM network_mode_state WHERE id = 1")
        state_row = cursor.fetchone()

        # Get recent history (last 10 changes)
        cursor.execute("""
            SELECT * FROM network_mode_history
            ORDER BY changed_at DESC
            LIMIT 10
        """)
        history_rows = cursor.fetchall()

        conn.close()

        # Format state
        state = {
            "mode": self.get_mode().value,
            "updated_at": state_row["updated_at"] if state_row else None,
            "updated_by": state_row["updated_by"] if state_row else None,
            "metadata": json.loads(state_row["metadata"]) if state_row and state_row["metadata"] else {},
        }

        # Format history
        history = []
        for row in history_rows:
            history.append({
                "previous_mode": row["previous_mode"],
                "new_mode": row["new_mode"],
                "changed_at": row["changed_at"],
                "changed_by": row["changed_by"],
                "reason": row["reason"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            })

        return {
            "current_state": state,
            "recent_history": history,
            "available_modes": [mode.value for mode in NetworkMode],
            "readonly_operations": list(READONLY_OPERATIONS),
            "write_operations": list(WRITE_OPERATIONS),
        }

    def get_history(
        self,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[Dict[str, Any]]:
        """Get network mode change history.

        Args:
            limit: Maximum number of history records to return
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of history records
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM network_mode_history WHERE 1=1"
        params = []

        if start_date:
            query += " AND changed_at >= ?"
            params.append(start_date.isoformat())

        if end_date:
            query += " AND changed_at <= ?"
            params.append(end_date.isoformat())

        query += " ORDER BY changed_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            history.append({
                "id": row["id"],
                "previous_mode": row["previous_mode"],
                "new_mode": row["new_mode"],
                "changed_at": row["changed_at"],
                "changed_by": row["changed_by"],
                "reason": row["reason"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            })

        return history
