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
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from agentos.store import get_db
from agentos.core.time import utc_now, utc_now_iso


logger = logging.getLogger(__name__)


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

# External Info Declaration events (Task #4)
EXTERNAL_INFO_DECLARED = "EXTERNAL_INFO_DECLARED"

# InfoNeed Classification events (Task #19)
INFO_NEED_CLASSIFICATION = "INFO_NEED_CLASSIFICATION"
INFO_NEED_OUTCOME = "INFO_NEED_OUTCOME"

# Multi-Intent Processing events (Task #25)
MULTI_INTENT_SPLIT = "MULTI_INTENT_SPLIT"

# Memory Context Injection events (Task #8 - Memory Phase)
MEMORY_CONTEXT_INJECTED = "MEMORY_CONTEXT_INJECTED"

# Shadow Evaluation events (Task #30 - v3)
DECISION_SET_CREATED = "DECISION_SET_CREATED"
SHADOW_EVALUATION_COMPLETED = "SHADOW_EVALUATION_COMPLETED"
USER_BEHAVIOR_SIGNAL = "USER_BEHAVIOR_SIGNAL"
DECISION_COMPARISON = "DECISION_COMPARISON"

# Improvement Proposal Review events (Task #9 - v3)
PROPOSAL_APPROVED = "PROPOSAL_APPROVED"
PROPOSAL_REJECTED = "PROPOSAL_REJECTED"
PROPOSAL_DEFERRED = "PROPOSAL_DEFERRED"

# Memory Capability events (Task #16)
MEMORY_CAPABILITY_CHECK = "MEMORY_CAPABILITY_CHECK"
MEMORY_CAPABILITY_GRANTED = "MEMORY_CAPABILITY_GRANTED"
MEMORY_CAPABILITY_REVOKED = "MEMORY_CAPABILITY_REVOKED"

# Voice TTS and Barge-In events (Task #9 - Voice v0.2)
TTS_START = "TTS_START"
TTS_END = "TTS_END"
BARGE_IN_DETECTED = "BARGE_IN_DETECTED"
BARGE_IN_EXECUTED = "BARGE_IN_EXECUTED"

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
    EXTERNAL_INFO_DECLARED,
    INFO_NEED_CLASSIFICATION,
    INFO_NEED_OUTCOME,
    MULTI_INTENT_SPLIT,
    MEMORY_CONTEXT_INJECTED,
    DECISION_SET_CREATED,
    SHADOW_EVALUATION_COMPLETED,
    USER_BEHAVIOR_SIGNAL,
    DECISION_COMPARISON,
    PROPOSAL_APPROVED,
    PROPOSAL_REJECTED,
    PROPOSAL_DEFERRED,
    MEMORY_CAPABILITY_CHECK,
    MEMORY_CAPABILITY_GRANTED,
    MEMORY_CAPABILITY_REVOKED,
    TTS_START,
    TTS_END,
    BARGE_IN_DETECTED,
    BARGE_IN_EXECUTED,
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
    # EXCEPT for InfoNeed events where None is semantically meaningful
    if event_type not in [INFO_NEED_CLASSIFICATION, INFO_NEED_OUTCOME]:
        payload = {k: v for k, v in payload.items() if v is not None}

    # Serialize payload to JSON
    payload_json = json.dumps(payload, ensure_ascii=False)

    # Get current timestamp (UTC)
    now = int(utc_now().timestamp())

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
        # Do NOT close: get_db() returns shared thread-local connection managed by registry_db
        pass


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
    now = int(utc_now().timestamp())
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
        # Do NOT close: get_db() returns shared thread-local connection managed by registry_db
        pass


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


# ============================================
# Async Audit Logging (Task #19)
# ============================================

async def log_audit_event_async(
    event_type: str,
    task_id: Optional[str] = None,
    snippet_id: Optional[str] = None,
    preview_id: Optional[str] = None,
    level: str = "info",
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """
    Async version of log_audit_event for non-blocking audit logging.

    This function is designed for use in async contexts where audit logging
    should not block the main execution flow. If logging fails, it logs a
    warning but does not raise exceptions.

    Args:
        event_type: Event type constant (e.g., INFO_NEED_CLASSIFICATION)
        task_id: Optional task ID to associate with this event
        snippet_id: Optional snippet ID (stored in payload)
        preview_id: Optional preview session ID (stored in payload)
        level: Log level (info|warn|error), defaults to "info"
        metadata: Optional additional metadata (merged into payload)

    Returns:
        audit_id: ID of the created audit record, or None if logging failed

    Example:
        >>> import asyncio
        >>> audit_id = await log_audit_event_async(
        ...     event_type=INFO_NEED_CLASSIFICATION,
        ...     metadata={
        ...         "message_id": "msg-123",
        ...         "question": "What is the latest Python version?",
        ...         "classified_type": "EXTERNAL_FACT_UNCERTAIN"
        ...     }
        ... )
    """
    try:
        # Use synchronous function in a non-blocking way
        # Note: This is still synchronous internally but wrapped for async contexts
        audit_id = log_audit_event(
            event_type=event_type,
            task_id=task_id,
            snippet_id=snippet_id,
            preview_id=preview_id,
            level=level,
            metadata=metadata,
        )
        return audit_id
    except Exception as e:
        # Log warning but don't raise - audit logging should never break main flow
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Async audit logging failed for {event_type}: {e}")
        return None


def find_audit_event_by_metadata(
    event_type: str,
    metadata_key: str,
    metadata_value: str,
) -> Optional[Dict[str, Any]]:
    """
    Find an audit event by searching in JSON metadata.

    This is useful for finding events by custom identifiers like message_id.

    Args:
        event_type: Event type to filter by
        metadata_key: Key to search in JSON payload
        metadata_value: Value to match

    Returns:
        First matching event dictionary, or None if not found

    Example:
        >>> event = find_audit_event_by_metadata(
        ...     event_type=INFO_NEED_CLASSIFICATION,
        ...     metadata_key="message_id",
        ...     metadata_value="msg-123"
        ... )
        >>> if event:
        ...     print(f"Found event: {event['audit_id']}")
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Use SQLite JSON functions to search in payload
        sql = """
            SELECT audit_id, task_id, level, event_type, payload, created_at
            FROM task_audits
            WHERE event_type = ?
            AND json_extract(payload, ?) = ?
            ORDER BY created_at DESC
            LIMIT 1
        """

        # SQLite json_extract uses $ prefix for JSON path
        json_path = f"$.{metadata_key}"

        cursor.execute(sql, (event_type, json_path, metadata_value))
        row = cursor.fetchone()

        if row:
            return {
                "audit_id": row["audit_id"],
                "task_id": row["task_id"],
                "level": row["level"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload"]) if row["payload"] else {},
                "created_at": row["created_at"],
            }

        return None

    finally:
        # Do NOT close: get_db() returns shared thread-local connection
        pass


# ============================================
# InfoNeed Classification Audit Helpers (Task #19)
# ============================================

async def log_info_need_classification(
    message_id: str,
    session_id: str,
    question: str,
    classified_type: str,
    confidence: str,
    decision: str,
    signals: Dict[str, Any],
    rule_matches: list[str],
    llm_confidence: Optional[Dict[str, Any]] = None,
    latency_ms: float = 0.0,
) -> Optional[int]:
    """
    Log InfoNeed classification event to audit trail.

    This function records the classification decision made by InfoNeedClassifier,
    including all the signals and reasoning that led to the decision.

    Args:
        message_id: Unique message identifier (for correlation with outcome)
        session_id: Session ID where classification occurred
        question: User's original question text
        classified_type: Classified InfoNeedType (e.g., "EXTERNAL_FACT_UNCERTAIN")
        confidence: Confidence level ("high", "medium", "low")
        decision: Decision action (e.g., "REQUIRE_COMM", "LOCAL_CAPABILITY")
        signals: Dictionary of rule-based signals
        rule_matches: List of matched rule keywords
        llm_confidence: Optional LLM confidence assessment result
        latency_ms: Classification latency in milliseconds

    Returns:
        audit_id: ID of the created audit record, or None if logging failed

    Example:
        >>> audit_id = await log_info_need_classification(
        ...     message_id="msg-abc123",
        ...     session_id="session-456",
        ...     question="What is the latest AI policy?",
        ...     classified_type="EXTERNAL_FACT_UNCERTAIN",
        ...     confidence="low",
        ...     decision="REQUIRE_COMM",
        ...     signals={
        ...         "time_sensitive": True,
        ...         "authoritative": True,
        ...         "ambient": False,
        ...         "signal_strength": 0.85
        ...     },
        ...     rule_matches=["latest", "policy"],
        ...     llm_confidence={"confidence": "low", "reason": "time-sensitive"},
        ...     latency_ms=45.3
        ... )
    """
    # Build metadata with explicit None values preserved
    metadata = {
        "message_id": message_id,
        "session_id": session_id,
        "question": question,
        "classified_type": classified_type,
        "confidence": confidence,
        "decision": decision,
        "signals": signals,
        "rule_matches": rule_matches,
        "timestamp": utc_now_iso() + "Z",
        "latency_ms": latency_ms,
    }

    # Explicitly include llm_confidence even if None (for consistency)
    metadata["llm_confidence"] = llm_confidence

    return await log_audit_event_async(
        event_type=INFO_NEED_CLASSIFICATION,
        level="info",
        metadata=metadata,
    )


async def log_info_need_outcome(
    message_id: str,
    outcome: str,
    user_action: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[int]:
    """
    Log InfoNeed outcome event to audit trail.

    This function records the actual outcome of an InfoNeed classification,
    allowing us to validate whether the classification was correct.

    Key principle: We record whether the judgment was validated/contradicted by
    user behavior, NOT whether the answer content was correct.

    Args:
        message_id: Message ID to correlate with classification event
        outcome: Outcome type - one of:
            - "validated": User executed the suggested action (e.g., ran /comm)
            - "unnecessary_comm": System suggested REQUIRE_COMM but user indicated not needed
            - "user_corrected": User corrected the classification ("you should search")
            - "user_cancelled": User cancelled the operation
        user_action: Optional user action that was executed (e.g., "/comm search ...")
        notes: Optional notes about the outcome

    Returns:
        audit_id: ID of the created audit record, or None if logging failed

    Raises:
        ValueError: If outcome is not one of the valid types

    Example:
        >>> # User executed the suggested /comm command
        >>> audit_id = await log_info_need_outcome(
        ...     message_id="msg-abc123",
        ...     outcome="validated",
        ...     user_action="/comm search latest AI policy",
        ...     notes="User followed suggestion immediately"
        ... )

        >>> # User corrected the system's decision
        >>> audit_id = await log_info_need_outcome(
        ...     message_id="msg-xyz789",
        ...     outcome="user_corrected",
        ...     user_action="User said: 'You should search for that'",
        ...     notes="System chose DIRECT_ANSWER but should have used REQUIRE_COMM"
        ... )
    """
    # Validate outcome type
    valid_outcomes = {"validated", "unnecessary_comm", "user_corrected", "user_cancelled"}
    if outcome not in valid_outcomes:
        raise ValueError(
            f"Invalid outcome: {outcome}. "
            f"Must be one of: {', '.join(sorted(valid_outcomes))}"
        )

    # Calculate latency from original classification event
    original_event = find_audit_event_by_metadata(
        event_type=INFO_NEED_CLASSIFICATION,
        metadata_key="message_id",
        metadata_value=message_id,
    )

    latency_ms = None
    if original_event:
        try:
            # Parse timestamp from original event
            original_ts_str = original_event["payload"].get("timestamp", "")
            if original_ts_str:
                # Remove 'Z' suffix and parse
                original_ts = datetime.fromisoformat(original_ts_str.rstrip("Z"))
                # Calculate latency
                now = utc_now()
                latency_ms = (now - original_ts.replace(tzinfo=timezone.utc)).total_seconds() * 1000
        except Exception as e:
            # If timestamp parsing fails, log but continue
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to calculate latency for message_id={message_id}: {e}")

    # Build metadata with explicit None values preserved
    metadata = {
        "message_id": message_id,
        "outcome": outcome,
        "timestamp": utc_now_iso() + "Z",
    }

    # Explicitly include optional fields even if None (for consistency)
    metadata["user_action"] = user_action
    metadata["latency_ms"] = latency_ms
    metadata["notes"] = notes

    return await log_audit_event_async(
        event_type=INFO_NEED_OUTCOME,
        level="info",
        metadata=metadata,
    )


def get_info_need_classification_events(
    session_id: Optional[str] = None,
    classified_type: Optional[str] = None,
    decision: Optional[str] = None,
    limit: int = 100,
) -> list[Dict[str, Any]]:
    """
    Query InfoNeed classification events with filters.

    Args:
        session_id: Filter by session ID
        classified_type: Filter by classified type (e.g., "EXTERNAL_FACT_UNCERTAIN")
        decision: Filter by decision action (e.g., "REQUIRE_COMM")
        limit: Maximum number of results (default 100)

    Returns:
        List of classification events ordered by timestamp (newest first)

    Example:
        >>> # Get all REQUIRE_COMM decisions
        >>> events = get_info_need_classification_events(
        ...     decision="REQUIRE_COMM",
        ...     limit=50
        ... )
        >>> print(f"Found {len(events)} REQUIRE_COMM decisions")
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Build query
        sql = """
            SELECT audit_id, task_id, level, event_type, payload, created_at
            FROM task_audits
            WHERE event_type = ?
        """
        params = [INFO_NEED_CLASSIFICATION]

        # Add JSON filters
        if session_id:
            sql += " AND json_extract(payload, '$.session_id') = ?"
            params.append(session_id)

        if classified_type:
            sql += " AND json_extract(payload, '$.classified_type') = ?"
            params.append(classified_type)

        if decision:
            sql += " AND json_extract(payload, '$.decision') = ?"
            params.append(decision)

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
        # Do NOT close: get_db() returns shared thread-local connection
        pass


def get_info_need_outcomes_for_message(message_id: str) -> list[Dict[str, Any]]:
    """
    Get all outcome events for a specific message.

    This is useful for tracking the complete history of outcomes for a
    classification decision.

    Args:
        message_id: Message ID to query

    Returns:
        List of outcome events ordered by timestamp

    Example:
        >>> outcomes = get_info_need_outcomes_for_message("msg-123")
        >>> for outcome in outcomes:
        ...     print(f"{outcome['payload']['outcome']}: {outcome['payload'].get('notes', '')}")
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        sql = """
            SELECT audit_id, task_id, level, event_type, payload, created_at
            FROM task_audits
            WHERE event_type = ?
            AND json_extract(payload, '$.message_id') = ?
            ORDER BY created_at ASC
        """

        cursor.execute(sql, (INFO_NEED_OUTCOME, message_id))
        rows = cursor.fetchall()

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
        # Do NOT close: get_db() returns shared thread-local connection
        pass


# ============================================
# Shadow Evaluation Audit Helpers (Task #30 - v3)
# ============================================

async def log_decision_set(
    decision_set_id: str,
    message_id: str,
    session_id: str,
    question_text: str,
    active_version: str,
    shadow_versions: List[str],
    active_decision: Dict[str, Any],
    shadow_decisions: List[Dict[str, Any]],
    context_snapshot: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """
    Log decision set (active + shadow) to audit trail.

    This function records the complete decision set created during InfoNeed
    classification, including both the active decision (v1) and shadow
    decisions (v2.a, v2.b, etc.) for later comparison and evaluation.

    CRITICAL: This function only RECORDS decisions. It does not:
    - Compute Reality Alignment Scores
    - Compare decisions
    - Generate improvement proposals

    These operations are performed later by Shadow Evaluation System.

    Args:
        decision_set_id: Unique decision set identifier (for correlation)
        message_id: Message ID (for user behavior signal correlation)
        session_id: Session ID where classification occurred
        question_text: User's original question
        active_version: Active classifier version ID (e.g., "v1.0.0")
        shadow_versions: List of shadow classifier version IDs
        active_decision: Active classification decision (full ClassificationResult dict)
        shadow_decisions: List of shadow classification decisions
        context_snapshot: Optional context data captured at classification time

    Returns:
        audit_id: ID of the created audit record, or None if logging failed

    Example:
        >>> audit_id = await log_decision_set(
        ...     decision_set_id="ds-abc123",
        ...     message_id="msg-456",
        ...     session_id="session-789",
        ...     question_text="What is the latest Python version?",
        ...     active_version="v1.0.0",
        ...     shadow_versions=["v2.0-alpha", "v2.0-beta"],
        ...     active_decision={
        ...         "info_need_type": "EXTERNAL_FACT_UNCERTAIN",
        ...         "decision_action": "REQUIRE_COMM",
        ...         "confidence_level": "low",
        ...         "reasoning": "Time-sensitive query requires current data"
        ...     },
        ...     shadow_decisions=[
        ...         {
        ...             "info_need_type": "LOCAL_KNOWLEDGE",
        ...             "decision_action": "DIRECT_ANSWER",
        ...             "confidence_level": "high",
        ...             "reasoning": "Python versioning is well-established"
        ...         }
        ...     ]
        ... )
    """
    # Build metadata
    metadata = {
        "decision_set_id": decision_set_id,
        "message_id": message_id,
        "session_id": session_id,
        "question_text": question_text,
        "question_hash": hash(question_text),  # For duplicate detection
        "active_version": active_version,
        "shadow_versions": shadow_versions,
        "active_decision": active_decision,
        "shadow_decisions": shadow_decisions,
        "timestamp": utc_now_iso() + "Z",
    }

    # Include context snapshot if provided
    if context_snapshot:
        metadata["context_snapshot"] = context_snapshot

    return await log_audit_event_async(
        event_type=DECISION_SET_CREATED,
        level="info",
        metadata=metadata,
    )


async def log_user_behavior_signal(
    message_id: str,
    session_id: str,
    signal_type: str,
    signal_data: Dict[str, Any],
    timestamp: Optional[datetime] = None,
) -> Optional[int]:
    """
    Log user behavior signal to audit trail.

    User behavior signals are used to compute Reality Alignment Scores for
    shadow evaluation. These signals capture how users interact with the
    system's responses and provide ground truth for evaluating decisions.

    Signal Types (for Reality Alignment Score):
    - user_followup_override: User immediately corrected/contradicted the decision
    - delayed_comm_request: User later manually requested communication
    - abandoned_response: User interrupted or abandoned the interaction
    - reask_same_question: User re-asked the same question (dissatisfied)
    - phase_violation: Decision caused phase conflict or error
    - smooth_completion: Interaction completed successfully without friction
    - explicit_feedback: User provided explicit feedback (thumbs up/down)

    CRITICAL: This function only RECORDS signals. It does not:
    - Compute scores
    - Make judgments about decision quality
    - Trigger any actions

    Scoring is performed later by Shadow Evaluation System.

    Args:
        message_id: Message ID to correlate with decision set
        session_id: Session ID where signal occurred
        signal_type: Type of user behavior signal (see list above)
        signal_data: Detailed signal data (context-specific)
        timestamp: Optional signal timestamp (defaults to now)

    Returns:
        audit_id: ID of the created audit record, or None if logging failed

    Example:
        >>> # User immediately asked to use /comm after getting direct answer
        >>> audit_id = await log_user_behavior_signal(
        ...     message_id="msg-456",
        ...     session_id="session-789",
        ...     signal_type="user_followup_override",
        ...     signal_data={
        ...         "user_action": "/comm search Python latest version",
        ...         "delay_seconds": 5,
        ...         "override_reason": "wanted current info"
        ...     }
        ... )

        >>> # User completed interaction smoothly
        >>> audit_id = await log_user_behavior_signal(
        ...     message_id="msg-123",
        ...     session_id="session-789",
        ...     signal_type="smooth_completion",
        ...     signal_data={
        ...         "interaction_duration_seconds": 30,
        ...         "followup_questions": 0
        ...     }
        ... )
    """
    # Validate signal type
    valid_signal_types = {
        "user_followup_override",
        "delayed_comm_request",
        "abandoned_response",
        "reask_same_question",
        "phase_violation",
        "smooth_completion",
        "explicit_feedback",
    }

    if signal_type not in valid_signal_types:
        logger.warning(
            f"Unknown signal_type: {signal_type}. "
            f"Valid types: {', '.join(sorted(valid_signal_types))}"
        )

    # Build metadata
    metadata = {
        "message_id": message_id,
        "session_id": session_id,
        "signal_type": signal_type,
        "signal_data": signal_data,
        "timestamp": (timestamp or utc_now()).isoformat() + "Z",
    }

    return await log_audit_event_async(
        event_type=USER_BEHAVIOR_SIGNAL,
        level="info",
        metadata=metadata,
    )


async def log_shadow_evaluation(
    evaluation_id: str,
    decision_set_id: str,
    message_id: str,
    session_id: str,
    active_score: float,
    shadow_scores: Dict[str, float],
    signals_used: List[str],
    evaluation_time_ms: float,
    evaluation_method: str = "reality_alignment",
) -> Optional[int]:
    """
    Log shadow evaluation result to audit trail.

    This function records the computed Reality Alignment Scores for both
    active and shadow decisions. These scores are computed by the Shadow
    Evaluation System based on user behavior signals.

    CRITICAL: This function only RECORDS evaluation results. It does not:
    - Compute the scores (done by Shadow Score Calculator)
    - Generate improvement proposals
    - Trigger migration decisions

    These operations are performed by other components.

    Args:
        evaluation_id: Unique evaluation identifier
        decision_set_id: Decision set ID (for correlation)
        message_id: Message ID (for correlation)
        session_id: Session ID where evaluation occurred
        active_score: Reality Alignment Score for active decision (0.0-1.0)
        shadow_scores: Reality Alignment Scores for shadow decisions {version_id: score}
        signals_used: List of signal types used in scoring
        evaluation_time_ms: Time taken to compute scores (milliseconds)
        evaluation_method: Scoring method used (default: "reality_alignment")

    Returns:
        audit_id: ID of the created audit record, or None if logging failed

    Example:
        >>> audit_id = await log_shadow_evaluation(
        ...     evaluation_id="eval-xyz",
        ...     decision_set_id="ds-abc123",
        ...     message_id="msg-456",
        ...     session_id="session-789",
        ...     active_score=0.65,  # Active decision had moderate alignment
        ...     shadow_scores={
        ...         "v2.0-alpha": 0.85,  # Shadow performed better
        ...         "v2.0-beta": 0.90    # This shadow performed even better
        ...     },
        ...     signals_used=["user_followup_override", "delayed_comm_request"],
        ...     evaluation_time_ms=45.2
        ... )
    """
    # Validate scores are in valid range
    all_scores = [active_score] + list(shadow_scores.values())
    for score in all_scores:
        if not 0.0 <= score <= 1.0:
            logger.warning(f"Score {score} outside valid range [0.0, 1.0]")

    # Build metadata
    metadata = {
        "evaluation_id": evaluation_id,
        "decision_set_id": decision_set_id,
        "message_id": message_id,
        "session_id": session_id,
        "active_score": active_score,
        "shadow_scores": shadow_scores,
        "signals_used": signals_used,
        "evaluation_time_ms": evaluation_time_ms,
        "evaluation_method": evaluation_method,
        "timestamp": utc_now_iso() + "Z",
    }

    return await log_audit_event_async(
        event_type=SHADOW_EVALUATION_COMPLETED,
        level="info",
        metadata=metadata,
    )


async def log_decision_comparison(
    comparison_id: str,
    decision_set_id: str,
    active_version: str,
    shadow_version: str,
    comparison_result: Dict[str, Any],
    comparison_type: str = "decision_divergence",
) -> Optional[int]:
    """
    Log decision comparison result to audit trail.

    This function records the comparison between active and shadow decisions,
    capturing divergences and differences in classification outcomes.

    CRITICAL: This function only RECORDS comparison results. It does not:
    - Compute scores
    - Generate improvement proposals
    - Make migration decisions

    These operations are performed by Comparison Engine and Review Queue.

    Args:
        comparison_id: Unique comparison identifier
        decision_set_id: Decision set ID (for correlation)
        active_version: Active classifier version ID
        shadow_version: Shadow classifier version ID
        comparison_result: Comparison data structure containing:
            - decision_diverged: bool (did decisions differ?)
            - action_diverged: bool (did recommended actions differ?)
            - confidence_delta: float (difference in confidence levels)
            - reasoning_similarity: float (similarity of reasoning)
        comparison_type: Type of comparison performed

    Returns:
        audit_id: ID of the created audit record, or None if logging failed

    Example:
        >>> audit_id = await log_decision_comparison(
        ...     comparison_id="cmp-123",
        ...     decision_set_id="ds-abc123",
        ...     active_version="v1.0.0",
        ...     shadow_version="v2.0-alpha",
        ...     comparison_result={
        ...         "decision_diverged": True,
        ...         "action_diverged": True,
        ...         "active_action": "REQUIRE_COMM",
        ...         "shadow_action": "DIRECT_ANSWER",
        ...         "confidence_delta": 0.4,
        ...         "reasoning_similarity": 0.3,
        ...         "divergence_severity": "high"
        ...     }
        ... )
    """
    # Build metadata
    metadata = {
        "comparison_id": comparison_id,
        "decision_set_id": decision_set_id,
        "active_version": active_version,
        "shadow_version": shadow_version,
        "comparison_result": comparison_result,
        "comparison_type": comparison_type,
        "timestamp": utc_now_iso() + "Z",
    }

    return await log_audit_event_async(
        event_type=DECISION_COMPARISON,
        level="info",
        metadata=metadata,
    )


def get_decision_sets(
    session_id: Optional[str] = None,
    active_version: Optional[str] = None,
    has_shadow: Optional[bool] = None,
    limit: int = 100,
) -> list[Dict[str, Any]]:
    """
    Query decision set events with filters.

    Args:
        session_id: Filter by session ID
        active_version: Filter by active classifier version
        has_shadow: Filter for decision sets with/without shadow decisions.
                    - True: only sets with shadow decisions
                    - False: only sets without shadow decisions
                    - None (default): all decision sets
        limit: Maximum number of results (default 100)

    Returns:
        List of decision set events ordered by timestamp (newest first)

    Example:
        >>> # Get all decision sets with shadow decisions
        >>> decision_sets = get_decision_sets(has_shadow=True, limit=50)
        >>> for ds in decision_sets:
        ...     print(f"Decision set {ds['payload']['decision_set_id']}: "
        ...           f"{len(ds['payload']['shadow_decisions'])} shadows")
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Build query
        sql = """
            SELECT audit_id, task_id, level, event_type, payload, created_at
            FROM task_audits
            WHERE event_type = ?
        """
        params = [DECISION_SET_CREATED]

        # Add filters
        if session_id:
            sql += " AND json_extract(payload, '$.session_id') = ?"
            params.append(session_id)

        if active_version:
            sql += " AND json_extract(payload, '$.active_version') = ?"
            params.append(active_version)

        if has_shadow is not None:
            if has_shadow:
                # Filter for decision sets that have at least one shadow decision
                sql += " AND json_array_length(json_extract(payload, '$.shadow_decisions')) > 0"
            else:
                # Filter for decision sets that have no shadow decisions
                sql += " AND (json_array_length(json_extract(payload, '$.shadow_decisions')) = 0 OR json_extract(payload, '$.shadow_decisions') IS NULL)"

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
        # Do NOT close: get_db() returns shared thread-local connection
        pass


def get_user_behavior_signals_for_message(
    message_id: str,
    signal_type: Optional[str] = None,
) -> list[Dict[str, Any]]:
    """
    Get all user behavior signals for a specific message.

    Args:
        message_id: Message ID to query
        signal_type: Optional filter for specific signal type

    Returns:
        List of user behavior signal events ordered by timestamp

    Example:
        >>> signals = get_user_behavior_signals_for_message("msg-123")
        >>> for signal in signals:
        ...     print(f"{signal['payload']['signal_type']}: "
        ...           f"{signal['payload']['signal_data']}")
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        sql = """
            SELECT audit_id, task_id, level, event_type, payload, created_at
            FROM task_audits
            WHERE event_type = ?
            AND json_extract(payload, '$.message_id') = ?
        """
        params = [USER_BEHAVIOR_SIGNAL, message_id]

        if signal_type:
            sql += " AND json_extract(payload, '$.signal_type') = ?"
            params.append(signal_type)

        sql += " ORDER BY created_at ASC"

        cursor.execute(sql, params)
        rows = cursor.fetchall()

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
        # Do NOT close: get_db() returns shared thread-local connection
        pass


def get_shadow_evaluations_for_decision_set(
    decision_set_id: str,
) -> list[Dict[str, Any]]:
    """
    Get all shadow evaluation events for a specific decision set.

    Args:
        decision_set_id: Decision set ID to query

    Returns:
        List of shadow evaluation events ordered by timestamp

    Example:
        >>> evaluations = get_shadow_evaluations_for_decision_set("ds-abc123")
        >>> for eval in evaluations:
        ...     payload = eval['payload']
        ...     print(f"Active score: {payload['active_score']}")
        ...     print(f"Shadow scores: {payload['shadow_scores']}")
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        sql = """
            SELECT audit_id, task_id, level, event_type, payload, created_at
            FROM task_audits
            WHERE event_type = ?
            AND json_extract(payload, '$.decision_set_id') = ?
            ORDER BY created_at ASC
        """

        cursor.execute(sql, (SHADOW_EVALUATION_COMPLETED, decision_set_id))
        rows = cursor.fetchall()

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
        # Do NOT close: get_db() returns shared thread-local connection
        pass


def get_decision_set_by_id(decision_set_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific decision set by its ID.

    Args:
        decision_set_id: Decision set ID to retrieve

    Returns:
        Decision set event dictionary if found, None otherwise

    Example:
        >>> decision_set = get_decision_set_by_id("ds-abc123")
        >>> if decision_set:
        ...     print(f"Question: {decision_set['payload']['question_text']}")
        ...     print(f"Active version: {decision_set['payload']['active_version']}")
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        sql = """
            SELECT audit_id, task_id, level, event_type, payload, created_at
            FROM task_audits
            WHERE event_type = ?
            AND json_extract(payload, '$.decision_set_id') = ?
            LIMIT 1
        """

        cursor.execute(sql, (DECISION_SET_CREATED, decision_set_id))
        row = cursor.fetchone()

        if not row:
            return None

        return {
            "audit_id": row["audit_id"],
            "task_id": row["task_id"],
            "level": row["level"],
            "event_type": row["event_type"],
            "payload": json.loads(row["payload"]) if row["payload"] else {},
            "created_at": row["created_at"],
        }

    finally:
        # Do NOT close: get_db() returns shared thread-local connection
        pass


def get_decision_set_by_message_id(message_id: str) -> Optional[Dict[str, Any]]:
    """
    Get decision set by message ID.

    Args:
        message_id: Message ID to query

    Returns:
        Decision set event dictionary if found, None otherwise

    Example:
        >>> decision_set = get_decision_set_by_message_id("msg-123")
        >>> if decision_set:
        ...     print(f"Decision set ID: {decision_set['payload']['decision_set_id']}")
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        sql = """
            SELECT audit_id, task_id, level, event_type, payload, created_at
            FROM task_audits
            WHERE event_type = ?
            AND json_extract(payload, '$.message_id') = ?
            ORDER BY created_at DESC
            LIMIT 1
        """

        cursor.execute(sql, (DECISION_SET_CREATED, message_id))
        row = cursor.fetchone()

        if not row:
            return None

        return {
            "audit_id": row["audit_id"],
            "task_id": row["task_id"],
            "level": row["level"],
            "event_type": row["event_type"],
            "payload": json.loads(row["payload"]) if row["payload"] else {},
            "created_at": row["created_at"],
        }

    finally:
        # Do NOT close: get_db() returns shared thread-local connection
        pass


def get_decision_comparisons_for_decision_set(
    decision_set_id: str,
) -> list[Dict[str, Any]]:
    """
    Get all decision comparison events for a specific decision set.

    Args:
        decision_set_id: Decision set ID to query

    Returns:
        List of decision comparison events ordered by timestamp

    Example:
        >>> comparisons = get_decision_comparisons_for_decision_set("ds-abc123")
        >>> for cmp in comparisons:
        ...     result = cmp['payload']['comparison_result']
        ...     if result['decision_diverged']:
        ...         print(f"Divergence detected: {result['active_action']} vs {result['shadow_action']}")
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        sql = """
            SELECT audit_id, task_id, level, event_type, payload, created_at
            FROM task_audits
            WHERE event_type = ?
            AND json_extract(payload, '$.decision_set_id') = ?
            ORDER BY created_at ASC
        """

        cursor.execute(sql, (DECISION_COMPARISON, decision_set_id))
        rows = cursor.fetchall()

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
        # Do NOT close: get_db() returns shared thread-local connection
        pass


# ============================================
# Convenience Alias
# ============================================

# Alias for compatibility with other modules
emit_audit_event = log_audit_event
