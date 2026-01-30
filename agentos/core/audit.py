"""
Audit System - Unified audit trail for capability operations

This module provides a centralized audit logging system that integrates with
the existing task_audits table in the database.

Key Features:
- Type-safe event constants
- Automatic timestamp management
- JSON metadata serialization
- Integration with task lineage

Design Philosophy:
- Simple: Single function for all audit logging
- Extensible: Easy to add new event types
- Traceable: Links events to tasks, snippets, and preview sessions
"""

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from agentos.store import get_db


# ============================================
# Audit Event Types
# ============================================

# Snippet events
SNIPPET_CREATED = "SNIPPET_CREATED"
SNIPPET_UPDATED = "SNIPPET_UPDATED"
SNIPPET_DELETED = "SNIPPET_DELETED"
SNIPPET_USED_IN_TASK = "SNIPPET_USED_IN_TASK"
SNIPPET_USED_IN_PREVIEW = "SNIPPET_USED_IN_PREVIEW"

# Preview events
PREVIEW_SESSION_CREATED = "PREVIEW_SESSION_CREATED"
PREVIEW_SESSION_OPENED = "PREVIEW_SESSION_OPENED"
PREVIEW_SESSION_EXPIRED = "PREVIEW_SESSION_EXPIRED"
PREVIEW_RUNTIME_SELECTED = "PREVIEW_RUNTIME_SELECTED"
PREVIEW_DEP_INJECTED = "PREVIEW_DEP_INJECTED"

# Task events
TASK_MATERIALIZED_FROM_SNIPPET = "TASK_MATERIALIZED_FROM_SNIPPET"

# Extension events
EXTENSION_STEP_EXECUTED = "EXTENSION_STEP_EXECUTED"
EXTENSION_INSTALLED = "EXTENSION_INSTALLED"
EXTENSION_UNINSTALLED = "EXTENSION_UNINSTALLED"
EXTENSION_INSTALL_FAILED = "EXTENSION_INSTALL_FAILED"

# Task #10: Friction mechanism events
PLANNING_GUARD_SKIPPED = "PLANNING_GUARD_SKIPPED"
SPEC_FROZEN = "SPEC_FROZEN"
SPEC_UNFROZEN = "SPEC_UNFROZEN"
SPEC_FREEZE_DUPLICATE = "SPEC_FREEZE_DUPLICATE"
SPEC_UNFREEZE_DUPLICATE = "SPEC_UNFREEZE_DUPLICATE"

# PR-E3: Extension execution audit events
EXT_CMD_ROUTED = "EXT_CMD_ROUTED"
EXT_RUN_STARTED = "EXT_RUN_STARTED"
EXT_RUN_FINISHED = "EXT_RUN_FINISHED"
EXT_RUN_DENIED = "EXT_RUN_DENIED"
EXT_PERMISSION_CHECK = "EXT_PERMISSION_CHECK"

# P1-7: Budget snapshot audit events
BUDGET_SNAPSHOT_CREATED = "BUDGET_SNAPSHOT_CREATED"
BUDGET_SNAPSHOT_LINKED = "BUDGET_SNAPSHOT_LINKED"

# All valid event types (for validation)
VALID_EVENT_TYPES = {
    SNIPPET_CREATED,
    SNIPPET_UPDATED,
    SNIPPET_DELETED,
    SNIPPET_USED_IN_TASK,
    SNIPPET_USED_IN_PREVIEW,
    PREVIEW_SESSION_CREATED,
    PREVIEW_SESSION_OPENED,
    PREVIEW_SESSION_EXPIRED,
    PREVIEW_RUNTIME_SELECTED,
    PREVIEW_DEP_INJECTED,
    TASK_MATERIALIZED_FROM_SNIPPET,
    EXTENSION_STEP_EXECUTED,
    EXTENSION_INSTALLED,
    EXTENSION_UNINSTALLED,
    EXTENSION_INSTALL_FAILED,
    PLANNING_GUARD_SKIPPED,
    SPEC_FROZEN,
    SPEC_UNFROZEN,
    SPEC_FREEZE_DUPLICATE,
    SPEC_UNFREEZE_DUPLICATE,
    EXT_CMD_ROUTED,
    EXT_RUN_STARTED,
    EXT_RUN_FINISHED,
    EXT_RUN_DENIED,
    EXT_PERMISSION_CHECK,
    BUDGET_SNAPSHOT_CREATED,
    BUDGET_SNAPSHOT_LINKED,
}


# ============================================
# Audit Logging Functions
# ============================================

def log_audit_event(
    event_type: str,
    task_id: Optional[str] = None,
    snippet_id: Optional[str] = None,
    preview_id: Optional[str] = None,
    level: str = "info",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Log audit event to task_audits table

    This function integrates with the existing task_audits table structure:
    - audit_id: Auto-incremented primary key
    - task_id: Task reference (uses ORPHAN task for events not tied to a specific task)
    - level: info|warn|error
    - event_type: Free-form event type string
    - payload: JSON metadata (includes snippet_id, preview_id, and custom metadata)
    - created_at: Unix timestamp (UTC)

    Args:
        event_type: Event type constant (e.g., SNIPPET_CREATED)
        task_id: Optional task ID to associate with this event
        snippet_id: Optional snippet ID (stored in payload)
        preview_id: Optional preview session ID (stored in payload)
        level: Log level (info|warn|error), defaults to "info"
        metadata: Optional additional metadata (merged into payload)

    Returns:
        audit_id: ID of the created audit record

    Raises:
        ValueError: If event_type is not valid
        sqlite3.Error: If database operation fails

    Example:
        >>> log_audit_event(
        ...     event_type=SNIPPET_CREATED,
        ...     snippet_id="snippet-123",
        ...     metadata={"language": "python", "size": 150}
        ... )
        1

        >>> log_audit_event(
        ...     event_type=TASK_MATERIALIZED_FROM_SNIPPET,
        ...     task_id="task-456",
        ...     snippet_id="snippet-123",
        ...     metadata={"auto_run": True}
        ... )
        2
    """
    # Validate event type
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"Invalid event_type: {event_type}. "
            f"Must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}"
        )

    # Validate level
    valid_levels = {"info", "warn", "error"}
    if level not in valid_levels:
        raise ValueError(f"Invalid level: {level}. Must be one of: {', '.join(valid_levels)}")

    # Build payload
    payload = {
        "snippet_id": snippet_id,
        "preview_id": preview_id,
        **(metadata or {}),
    }

    # Remove None values to keep payload clean
    payload = {k: v for k, v in payload.items() if v is not None}

    # Serialize payload to JSON
    payload_json = json.dumps(payload, ensure_ascii=False)

    # Get current timestamp (UTC)
    now = int(datetime.now(timezone.utc).timestamp())

    # Insert audit record
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Handle orphan events: task_audits requires a valid task_id (FK constraint)
        # For events not tied to a specific task, we ensure an ORPHAN task exists
        db_task_id = task_id if task_id else _ensure_orphan_task(cursor)

        cursor.execute(
            """
            INSERT INTO task_audits (
                task_id, level, event_type, payload, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (db_task_id, level, event_type, payload_json, now)
        )

        audit_id = cursor.lastrowid

        conn.commit()

        return audit_id

    finally:
        conn.close()


def _ensure_orphan_task(cursor) -> str:
    """
    Ensure ORPHAN task exists for audit events not tied to a specific task

    This is an internal helper function that creates a special ORPHAN task
    if it doesn't exist yet. This task serves as a container for audit events
    that aren't associated with any specific task (e.g., snippet creation).

    Args:
        cursor: Database cursor (must be from active connection)

    Returns:
        ORPHAN task ID
    """
    orphan_task_id = "ORPHAN"

    # Check if ORPHAN task exists
    cursor.execute("SELECT task_id FROM tasks WHERE task_id = ?", (orphan_task_id,))
    if cursor.fetchone():
        return orphan_task_id

    # Create ORPHAN task
    now = int(datetime.now(timezone.utc).timestamp())
    cursor.execute(
        """
        INSERT INTO tasks (
            task_id, title, status, created_at, updated_at,
            created_by, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            orphan_task_id,
            "Orphan Events Container",
            "orphan",
            now,
            now,
            "system",
            json.dumps({"orphan": True, "description": "Container for audit events not tied to specific tasks"})
        )
    )

    return orphan_task_id


def get_audit_events(
    task_id: Optional[str] = None,
    event_type: Optional[str] = None,
    snippet_id: Optional[str] = None,
    preview_id: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 100,
) -> list[Dict[str, Any]]:
    """
    Query audit events with filters

    Args:
        task_id: Filter by task ID
        event_type: Filter by event type
        snippet_id: Filter by snippet ID (searches in payload JSON)
        preview_id: Filter by preview ID (searches in payload JSON)
        level: Filter by log level
        limit: Maximum number of results (default 100)

    Returns:
        List of audit events as dictionaries

    Example:
        >>> events = get_audit_events(snippet_id="snippet-123")
        >>> for event in events:
        ...     print(f"{event['event_type']}: {event['payload']}")
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Build query
        sql = """
            SELECT audit_id, task_id, level, event_type, payload, created_at
            FROM task_audits
            WHERE 1=1
        """
        params = []

        # Add filters
        if task_id:
            sql += " AND task_id = ?"
            params.append(task_id)

        if event_type:
            sql += " AND event_type = ?"
            params.append(event_type)

        if level:
            sql += " AND level = ?"
            params.append(level)

        # JSON filters (SQLite 3.38+ supports JSON functions)
        if snippet_id:
            sql += " AND json_extract(payload, '$.snippet_id') = ?"
            params.append(snippet_id)

        if preview_id:
            sql += " AND json_extract(payload, '$.preview_id') = ?"
            params.append(preview_id)

        # Order and limit
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # Convert to dictionaries
        events = []
        for row in rows:
            events.append({
                "audit_id": row["audit_id"],
                "task_id": row["task_id"],
                "level": row["level"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload"]) if row["payload"] else {},
                "created_at": row["created_at"],
            })

        return events

    finally:
        conn.close()


def get_snippet_audit_trail(snippet_id: str, limit: int = 50) -> list[Dict[str, Any]]:
    """
    Get complete audit trail for a snippet

    This is a convenience function that fetches all events related to a snippet.

    Args:
        snippet_id: Snippet ID
        limit: Maximum number of events

    Returns:
        List of audit events ordered by timestamp (newest first)

    Example:
        >>> trail = get_snippet_audit_trail("snippet-123")
        >>> print(f"Snippet has {len(trail)} audit events")
    """
    return get_audit_events(snippet_id=snippet_id, limit=limit)


def get_preview_audit_trail(preview_id: str, limit: int = 50) -> list[Dict[str, Any]]:
    """
    Get complete audit trail for a preview session

    Args:
        preview_id: Preview session ID
        limit: Maximum number of events

    Returns:
        List of audit events ordered by timestamp (newest first)
    """
    return get_audit_events(preview_id=preview_id, limit=limit)


def get_task_audits(task_id: str, limit: int = 100) -> list[Dict[str, Any]]:
    """
    Get all audit events for a task

    Args:
        task_id: Task ID
        limit: Maximum number of events

    Returns:
        List of audit events ordered by timestamp (newest first)
    """
    return get_audit_events(task_id=task_id, limit=limit)
