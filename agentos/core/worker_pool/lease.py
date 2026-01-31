"""Lease Manager - Distributed work item lease management

This module implements Compare-and-Swap (CAS) based lease acquisition
for work items, ensuring that only one worker can process a work item
at a time, with automatic expiration and recovery.

Design:
- Atomic lease acquisition using SQLite UPDATE + subquery
- Heartbeat-based lease renewal
- Automatic expiration detection
- Support for graceful release and forced takeover
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import json
from agentos.core.time import utc_now


logger = logging.getLogger(__name__)


class LeaseError(Exception):
    """Base exception for lease operations"""
    pass


class LeaseExpiredError(LeaseError):
    """Raised when attempting to operate on an expired lease"""
    pass


class LeaseConflictError(LeaseError):
    """Raised when lease is held by another worker"""
    pass


@dataclass
class Lease:
    """Represents a lease on a work item

    Attributes:
        work_item_id: ID of the work item
        task_id: ID of the parent task
        lease_holder: Worker ID holding the lease
        lease_acquired_at: When the lease was acquired
        lease_expires_at: When the lease will expire
        heartbeat_at: Last heartbeat timestamp
        input_data: Work item input data (JSON)
        work_type: Type of work (e.g., 'tool_execution', 'llm_call')
        priority: Work item priority
    """
    work_item_id: str
    task_id: str
    lease_holder: str
    lease_acquired_at: datetime
    lease_expires_at: datetime
    heartbeat_at: datetime
    input_data: Optional[Dict[str, Any]] = None
    work_type: str = "unknown"
    priority: int = 0

    def is_expired(self) -> bool:
        """Check if lease has expired"""
        return utc_now() >= self.lease_expires_at

    def time_until_expiry(self) -> timedelta:
        """Get time remaining until expiry"""
        return self.lease_expires_at - utc_now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "work_item_id": self.work_item_id,
            "task_id": self.task_id,
            "lease_holder": self.lease_holder,
            "lease_acquired_at": self.lease_acquired_at.isoformat(),
            "lease_expires_at": self.lease_expires_at.isoformat(),
            "heartbeat_at": self.heartbeat_at.isoformat(),
            "input_data": self.input_data,
            "work_type": self.work_type,
            "priority": self.priority,
        }


class LeaseManager:
    """Manages work item leases with Compare-and-Swap semantics

    This class provides atomic lease acquisition and renewal operations
    to ensure that work items are processed by exactly one worker at a time.

    Design principles:
    - Atomic operations using SQLite transactions
    - Compare-and-Swap for conflict-free acquisition
    - Heartbeat-based lease renewal
    - Graceful handling of expired leases

    Example:
        >>> manager = LeaseManager(conn, worker_id="worker-123")
        >>> lease = manager.acquire_lease(lease_duration_seconds=300)
        >>> if lease:
        ...     try:
        ...         # Process work item
        ...         manager.renew_lease(lease.work_item_id)
        ...         # Complete work
        ...         manager.release_lease(lease.work_item_id, success=True)
        ...     except Exception as e:
        ...         manager.release_lease(lease.work_item_id, success=False, error=str(e))
    """

    def __init__(self, conn: sqlite3.Connection, worker_id: str):
        """Initialize lease manager

        Args:
            conn: SQLite database connection
            worker_id: Unique identifier for this worker
        """
        self.conn = conn
        self.worker_id = worker_id
        self.conn.row_factory = sqlite3.Row

    def acquire_lease(
        self,
        lease_duration_seconds: int = 300,
        work_type_filter: Optional[str] = None,
        task_id_filter: Optional[str] = None
    ) -> Optional[Lease]:
        """Atomically acquire a lease on the next available work item

        Uses Compare-and-Swap (CAS) pattern:
        1. SELECT work_item_id WHERE status='pending' (with filters)
        2. UPDATE work_item SET lease_holder=worker_id WHERE work_item_id=... AND status='pending'
        3. If rows affected == 1: success, else: conflict (retry)

        Args:
            lease_duration_seconds: How long the lease is valid (default: 300s / 5 minutes)
            work_type_filter: Optional filter by work_type
            task_id_filter: Optional filter by task_id

        Returns:
            Lease object if acquired, None if no work available

        Raises:
            LeaseError: If database operation fails
        """
        try:
            # Build query with optional filters
            where_clauses = ["status = 'pending'"]
            params = [self.worker_id]

            if work_type_filter:
                where_clauses.append("work_type = ?")
                params.append(work_type_filter)

            if task_id_filter:
                where_clauses.append("task_id = ?")
                params.append(task_id_filter)

            where_clause = " AND ".join(where_clauses)

            # Atomic claim using UPDATE + subquery with RETURNING
            query = f"""
                UPDATE work_items
                SET
                    status = 'in_progress',
                    lease_holder = ?,
                    lease_acquired_at = CURRENT_TIMESTAMP,
                    lease_expires_at = datetime(CURRENT_TIMESTAMP, '+{lease_duration_seconds} seconds'),
                    heartbeat_at = CURRENT_TIMESTAMP,
                    started_at = CASE WHEN started_at IS NULL THEN CURRENT_TIMESTAMP ELSE started_at END
                WHERE work_item_id = (
                    SELECT work_item_id
                    FROM work_items
                    WHERE {where_clause}
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                )
                RETURNING work_item_id, task_id, lease_holder,
                          lease_acquired_at, lease_expires_at, heartbeat_at,
                          input_data, work_type, priority
            """

            cursor = self.conn.execute(query, params)
            row = cursor.fetchone()
            self.conn.commit()

            if not row:
                logger.debug(f"No available work items for worker {self.worker_id}")
                return None

            # Parse timestamps
            lease_acquired = datetime.fromisoformat(row['lease_acquired_at'].replace(' ', 'T'))
            lease_expires = datetime.fromisoformat(row['lease_expires_at'].replace(' ', 'T'))
            heartbeat = datetime.fromisoformat(row['heartbeat_at'].replace(' ', 'T'))

            # Ensure timezone awareness
            if lease_acquired.tzinfo is None:
                lease_acquired = lease_acquired.replace(tzinfo=timezone.utc)
            if lease_expires.tzinfo is None:
                lease_expires = lease_expires.replace(tzinfo=timezone.utc)
            if heartbeat.tzinfo is None:
                heartbeat = heartbeat.replace(tzinfo=timezone.utc)

            # Parse input data
            input_data = None
            if row['input_data']:
                try:
                    input_data = json.loads(row['input_data'])
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse input_data for work_item {row['work_item_id']}")

            lease = Lease(
                work_item_id=row['work_item_id'],
                task_id=row['task_id'],
                lease_holder=row['lease_holder'],
                lease_acquired_at=lease_acquired,
                lease_expires_at=lease_expires,
                heartbeat_at=heartbeat,
                input_data=input_data,
                work_type=row['work_type'],
                priority=row['priority'],
            )

            logger.info(
                f"Lease acquired: work_item={lease.work_item_id}, "
                f"worker={self.worker_id}, expires_in={lease_duration_seconds}s"
            )

            # PR-V2: Emit lease_acquired event
            try:
                from agentos.core.task.event_service import TaskEventService
                service = TaskEventService()
                service.emit_event(
                    task_id=lease.task_id,
                    event_type="lease_acquired",
                    actor="lease_manager",
                    span_id=f"work_{lease.work_item_id}",
                    parent_span_id="main",
                    phase="executing",
                    payload={
                        "work_item_id": lease.work_item_id,
                        "lease_holder": self.worker_id,
                        "lease_duration_seconds": lease_duration_seconds,
                        "explanation": f"Lease acquired by {self.worker_id}"
                    }
                )
            except Exception as e:
                logger.error(f"Failed to emit lease_acquired event: {e}")

            return lease

        except sqlite3.Error as e:
            logger.error(f"Failed to acquire lease: {e}")
            self.conn.rollback()
            raise LeaseError(f"Failed to acquire lease: {e}") from e

    def renew_lease(
        self,
        work_item_id: str,
        lease_duration_seconds: int = 300
    ) -> bool:
        """Renew lease by sending heartbeat and extending expiry time

        This should be called periodically (e.g., every 30-60 seconds) to
        keep the lease alive while work is in progress.

        Args:
            work_item_id: ID of the work item
            lease_duration_seconds: How long to extend the lease (default: 300s)

        Returns:
            True if renewed successfully, False if lease lost

        Raises:
            LeaseExpiredError: If lease has already expired
            LeaseConflictError: If lease is held by another worker
        """
        try:
            # Update heartbeat and extend lease
            cursor = self.conn.execute("""
                UPDATE work_items
                SET
                    heartbeat_at = CURRENT_TIMESTAMP,
                    lease_expires_at = datetime(CURRENT_TIMESTAMP, ? || ' seconds')
                WHERE work_item_id = ?
                  AND lease_holder = ?
                  AND status = 'in_progress'
            """, (lease_duration_seconds, work_item_id, self.worker_id))

            self.conn.commit()

            if cursor.rowcount == 0:
                # Check why renewal failed
                cursor = self.conn.execute("""
                    SELECT status, lease_holder, lease_expires_at
                    FROM work_items
                    WHERE work_item_id = ?
                """, (work_item_id,))

                row = cursor.fetchone()
                if not row:
                    raise LeaseError(f"Work item {work_item_id} not found")

                if row['lease_holder'] != self.worker_id:
                    raise LeaseConflictError(
                        f"Lease held by another worker: {row['lease_holder']}"
                    )

                if row['status'] != 'in_progress':
                    raise LeaseExpiredError(
                        f"Work item {work_item_id} is no longer in progress (status: {row['status']})"
                    )

                return False

            logger.debug(
                f"Lease renewed: work_item={work_item_id}, worker={self.worker_id}, "
                f"extended_by={lease_duration_seconds}s"
            )

            # PR-V2: Emit lease_renewed event
            try:
                from agentos.core.task.event_service import TaskEventService
                service = TaskEventService()
                # Get task_id from work_items table
                cursor = self.conn.execute("SELECT task_id FROM work_items WHERE work_item_id = ?", (work_item_id,))
                row = cursor.fetchone()
                if row:
                    service.emit_event(
                        task_id=row['task_id'],
                        event_type="lease_renewed",
                        actor="lease_manager",
                        span_id=f"work_{work_item_id}",
                        parent_span_id="main",
                        phase="executing",
                        payload={
                            "work_item_id": work_item_id,
                            "lease_holder": self.worker_id,
                            "extended_by_seconds": lease_duration_seconds,
                            "explanation": f"Lease renewed by {self.worker_id}"
                        }
                    )
            except Exception as e:
                logger.error(f"Failed to emit lease_renewed event: {e}")

            return True

        except sqlite3.Error as e:
            logger.error(f"Failed to renew lease for {work_item_id}: {e}")
            self.conn.rollback()
            raise LeaseError(f"Failed to renew lease: {e}") from e

    def release_lease(
        self,
        work_item_id: str,
        success: bool = True,
        output_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """Release lease and mark work item as completed or failed

        Args:
            work_item_id: ID of the work item
            success: Whether work completed successfully
            output_data: Result data (if successful)
            error: Error message (if failed)

        Returns:
            True if released successfully

        Raises:
            LeaseError: If database operation fails
        """
        try:
            if success:
                # Mark as completed
                self.conn.execute("""
                    UPDATE work_items
                    SET
                        status = 'completed',
                        output_data = ?,
                        completed_at = CURRENT_TIMESTAMP,
                        lease_holder = NULL,
                        lease_expires_at = NULL
                    WHERE work_item_id = ?
                      AND lease_holder = ?
                """, (
                    json.dumps(output_data) if output_data else None,
                    work_item_id,
                    self.worker_id
                ))
            else:
                # Mark as failed
                self.conn.execute("""
                    UPDATE work_items
                    SET
                        status = 'failed',
                        error_message = ?,
                        completed_at = CURRENT_TIMESTAMP,
                        lease_holder = NULL,
                        lease_expires_at = NULL
                    WHERE work_item_id = ?
                      AND lease_holder = ?
                """, (error, work_item_id, self.worker_id))

            self.conn.commit()

            status = "completed" if success else "failed"
            logger.info(
                f"Lease released: work_item={work_item_id}, worker={self.worker_id}, "
                f"status={status}"
            )

            return True

        except sqlite3.Error as e:
            logger.error(f"Failed to release lease for {work_item_id}: {e}")
            self.conn.rollback()
            raise LeaseError(f"Failed to release lease: {e}") from e

    def check_lease_status(self, work_item_id: str) -> Dict[str, Any]:
        """Check current lease status for a work item

        Args:
            work_item_id: ID of the work item

        Returns:
            Dictionary with lease status information
        """
        try:
            cursor = self.conn.execute("""
                SELECT
                    work_item_id,
                    status,
                    lease_holder,
                    lease_acquired_at,
                    lease_expires_at,
                    heartbeat_at,
                    CASE
                        WHEN lease_expires_at IS NULL THEN 0
                        WHEN lease_expires_at < CURRENT_TIMESTAMP THEN 1
                        ELSE 0
                    END as is_expired
                FROM work_items
                WHERE work_item_id = ?
            """, (work_item_id,))

            row = cursor.fetchone()
            if not row:
                return {"exists": False}

            return {
                "exists": True,
                "work_item_id": row['work_item_id'],
                "status": row['status'],
                "lease_holder": row['lease_holder'],
                "lease_acquired_at": row['lease_acquired_at'],
                "lease_expires_at": row['lease_expires_at'],
                "heartbeat_at": row['heartbeat_at'],
                "is_expired": bool(row['is_expired']),
                "held_by_me": row['lease_holder'] == self.worker_id,
            }

        except sqlite3.Error as e:
            logger.error(f"Failed to check lease status for {work_item_id}: {e}")
            raise LeaseError(f"Failed to check lease status: {e}") from e

    def get_my_leases(self) -> list[Dict[str, Any]]:
        """Get all active leases held by this worker

        Returns:
            List of lease information dictionaries
        """
        try:
            cursor = self.conn.execute("""
                SELECT
                    work_item_id,
                    task_id,
                    work_type,
                    status,
                    lease_acquired_at,
                    lease_expires_at,
                    heartbeat_at,
                    CASE
                        WHEN lease_expires_at < CURRENT_TIMESTAMP THEN 1
                        ELSE 0
                    END as is_expired
                FROM work_items
                WHERE lease_holder = ?
                  AND status = 'in_progress'
                ORDER BY lease_acquired_at ASC
            """, (self.worker_id,))

            return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"Failed to get leases for worker {self.worker_id}: {e}")
            raise LeaseError(f"Failed to get leases: {e}") from e
