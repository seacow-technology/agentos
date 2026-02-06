"""Recovery Sweep - Automatic detection and recovery of expired leases

This module implements a watchdog process that periodically scans for
expired work item leases and recovers them by:
1. Detecting leases that have expired (lease_expires_at < now)
2. Marking them as interrupted
3. Re-queuing them for retry (if retry_count < max_retries)
4. Creating error boundary checkpoints for audit trail

Design:
- Runs as a background thread or daemon process
- Configurable scan interval (default: 60 seconds)
- Respects max_retries limit
- Thread-safe database operations
- Comprehensive logging and metrics
"""

import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import json
from agentos.core.time import utc_now, utc_now_iso


logger = logging.getLogger(__name__)


@dataclass
class RecoveryStats:
    """Statistics from a recovery sweep

    Attributes:
        scan_time: When the scan was performed
        expired_found: Number of expired leases found
        recovered: Number of work items recovered (re-queued)
        failed: Number of work items permanently failed (max retries exceeded)
        checkpoints_created: Number of error boundary checkpoints created
        errors: Number of errors encountered during recovery
        scan_duration_ms: How long the scan took in milliseconds
    """
    scan_time: datetime
    expired_found: int = 0
    recovered: int = 0
    failed: int = 0
    checkpoints_created: int = 0
    errors: int = 0
    scan_duration_ms: float = 0.0
    error_details: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "scan_time": self.scan_time.isoformat(),
            "expired_found": self.expired_found,
            "recovered": self.recovered,
            "failed": self.failed,
            "checkpoints_created": self.checkpoints_created,
            "errors": self.errors,
            "scan_duration_ms": self.scan_duration_ms,
            "error_details": self.error_details,
        }


class RecoverySweep:
    """Automatic recovery of expired work item leases

    This class implements a watchdog that periodically scans for expired
    leases and recovers work items by resetting them to pending status
    (for retry) or marking them as permanently failed.

    Example:
        >>> sweep = RecoverySweep(conn, scan_interval_seconds=60)
        >>> sweep.start()
        >>> # ... system runs ...
        >>> sweep.stop()

    Or for one-time scan:
        >>> sweep = RecoverySweep(conn)
        >>> stats = sweep.scan_and_recover()
        >>> print(f"Recovered {stats.recovered} work items")
    """

    def __init__(
        self,
        conn: Optional[sqlite3.Connection] = None,
        scan_interval_seconds: int = 60,
        create_checkpoints: bool = True,
        cleanup_old_checkpoints: bool = True,
        checkpoint_retention_limit: int = 100
    ):
        """Initialize recovery sweep

        Args:
            conn: Database connection (optional, for backward compatibility)
                  If None, will use thread-local connections from ConnectionFactory
            scan_interval_seconds: How often to scan for expired leases (default: 60s)
            create_checkpoints: Whether to create error boundary checkpoints (default: True)
            cleanup_old_checkpoints: Whether to clean up old checkpoints (default: True)
            checkpoint_retention_limit: Max checkpoints to keep per task (default: 100)
        """
        # Store connection only for backward compatibility with direct scan_and_recover() calls
        # The background thread will create its own connection
        self._provided_conn = conn

        # Extract DB path from connection for background thread usage
        self._db_path: Optional[str] = None
        if conn is not None:
            try:
                # Get database path from connection
                cursor = conn.execute("PRAGMA database_list")
                db_info = cursor.fetchone()
                if db_info:
                    self._db_path = db_info[2]  # Path is in third column
            except Exception as e:
                logger.warning(f"Could not extract DB path from connection: {e}")

        self.scan_interval_seconds = scan_interval_seconds
        self.create_checkpoints = create_checkpoints
        self.cleanup_old_checkpoints = cleanup_old_checkpoints
        self.checkpoint_retention_limit = checkpoint_retention_limit

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

        # Statistics
        self.total_scans = 0
        self.total_recovered = 0
        self.total_failed = 0
        self.last_scan_stats: Optional[RecoveryStats] = None

    def start(self) -> None:
        """Start the recovery sweep background thread"""
        if self._running:
            logger.warning("Recovery sweep already running")
            return

        self._stop_event.clear()
        self._running = True

        self._thread = threading.Thread(
            target=self._sweep_loop,
            name="RecoverySweep",
            daemon=True
        )
        self._thread.start()

        logger.info(
            f"Recovery sweep started: scan_interval={self.scan_interval_seconds}s"
        )

    def stop(self, wait: bool = True, timeout: float = 10.0) -> None:
        """Stop the recovery sweep thread

        Args:
            wait: Whether to wait for thread to finish (default: True)
            timeout: Maximum time to wait in seconds (default: 10.0)
        """
        if not self._running:
            return

        self._stop_event.set()
        self._running = False

        if wait and self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("Recovery sweep thread did not stop within timeout")

        logger.info("Recovery sweep stopped")

    def is_running(self) -> bool:
        """Check if recovery sweep is running"""
        return self._running and self._thread is not None and self._thread.is_alive()

    def scan_and_recover(self, conn: Optional[sqlite3.Connection] = None) -> RecoveryStats:
        """Perform a single scan and recovery of expired leases

        This method:
        1. Finds all work items with expired leases (in_progress + lease_expires_at < now)
        2. For each expired work item:
           a. Increment retry_count
           b. If retry_count < max_retries: reset to 'pending'
           c. Else: mark as 'failed'
           d. Clear lease_holder and lease_expires_at
           e. Create error boundary checkpoint (if enabled)

        Args:
            conn: Database connection (optional). If not provided, uses thread-local connection.

        Returns:
            RecoveryStats with details of the recovery operation

        Raises:
            sqlite3.Error: If database operation fails
        """
        # Get connection: use provided conn, or fallback to thread-local, or use saved conn
        if conn is None:
            try:
                from agentos.store import get_thread_connection
                conn = get_thread_connection()
            except RuntimeError:
                # Fallback to provided connection if factory not initialized
                if self._provided_conn is None:
                    raise RuntimeError(
                        "No database connection available. Either pass conn parameter, "
                        "initialize ConnectionFactory, or provide conn in __init__"
                    )
                conn = self._provided_conn

        start_time = time.time()
        stats = RecoveryStats(scan_time=utc_now())

        try:
            # Find expired leases
            cursor = conn.execute("""
                SELECT
                    work_item_id,
                    task_id,
                    work_type,
                    lease_holder,
                    retry_count,
                    max_retries,
                    lease_acquired_at,
                    lease_expires_at,
                    heartbeat_at
                FROM work_items
                WHERE status = 'in_progress'
                  AND lease_expires_at < CURRENT_TIMESTAMP
                ORDER BY lease_expires_at ASC
            """)

            expired_items = cursor.fetchall()
            stats.expired_found = len(expired_items)

            if stats.expired_found == 0:
                logger.debug("No expired leases found")
            else:
                logger.info(f"Found {stats.expired_found} expired leases, recovering...")

                # PR-V2: Emit recovery_detected event for each task
                task_ids = set(item['task_id'] for item in expired_items)
                for tid in task_ids:
                    try:
                        from agentos.core.task.event_service import TaskEventService
                        service = TaskEventService()
                        expired_for_task = [item for item in expired_items if item['task_id'] == tid]
                        service.emit_event(
                            task_id=tid,
                            event_type="recovery_detected",
                            actor="recovery_sweep",
                            span_id="recovery_sweep",
                            phase="recovery",
                            payload={
                                "expired_count": len(expired_for_task),
                                "work_item_ids": [item['work_item_id'] for item in expired_for_task],
                                "explanation": f"Detected {len(expired_for_task)} expired work items requiring recovery"
                            }
                        )
                    except Exception as e:
                        logger.error(f"Failed to emit recovery_detected event: {e}")

                # Process each expired work item
                for item in expired_items:
                    try:
                        self._recover_work_item(item, stats, conn)
                    except Exception as e:
                        logger.exception(f"Failed to recover work item {item['work_item_id']}: {e}")
                        stats.errors += 1
                        stats.error_details.append(
                            f"{item['work_item_id']}: {str(e)}"
                        )

                # Commit all changes
                conn.commit()

            # Cleanup old checkpoints if enabled (always run, even if no expired items)
            if self.cleanup_old_checkpoints:
                self._cleanup_old_checkpoints(conn)

            stats.scan_duration_ms = (time.time() - start_time) * 1000

            # Update instance statistics
            self.total_scans += 1
            self.total_recovered += stats.recovered
            self.total_failed += stats.failed
            self.last_scan_stats = stats

            logger.info(
                f"Recovery sweep completed: "
                f"expired={stats.expired_found}, "
                f"recovered={stats.recovered}, "
                f"failed={stats.failed}, "
                f"errors={stats.errors}, "
                f"duration={stats.scan_duration_ms:.1f}ms"
            )

            return stats

        except sqlite3.Error as e:
            logger.error(f"Recovery sweep failed: {e}")
            conn.rollback()
            stats.errors += 1
            stats.error_details.append(f"Database error: {str(e)}")
            stats.scan_duration_ms = (time.time() - start_time) * 1000
            return stats

    def _recover_work_item(
        self,
        item: sqlite3.Row,
        stats: RecoveryStats,
        conn: sqlite3.Connection
    ) -> None:
        """Recover a single work item

        Args:
            item: Work item database row
            stats: Stats object to update
            conn: Database connection to use
        """
        work_item_id = item['work_item_id']
        task_id = item['task_id']
        retry_count = item['retry_count']
        max_retries = item['max_retries']

        # Determine new status based on retry count
        new_retry_count = retry_count + 1
        should_retry = new_retry_count < max_retries

        new_status = 'pending' if should_retry else 'failed'
        error_msg = f"Lease expired - no heartbeat received. Retry {new_retry_count}/{max_retries}"

        if not should_retry:
            error_msg = f"Max retries ({max_retries}) exceeded after lease expiration"

        # Update work item
        conn.execute("""
            UPDATE work_items
            SET
                status = ?,
                retry_count = ?,
                lease_holder = NULL,
                lease_expires_at = NULL,
                error_message = ?
            WHERE work_item_id = ?
        """, (new_status, new_retry_count, error_msg, work_item_id))

        # Update stats
        if should_retry:
            stats.recovered += 1
            logger.info(
                f"Work item recovered: {work_item_id} "
                f"(retry {new_retry_count}/{max_retries}, holder: {item['lease_holder']})"
            )

            # PR-V2: Emit recovery_requeued event
            try:
                from agentos.core.task.event_service import TaskEventService
                service = TaskEventService()
                service.emit_event(
                    task_id=task_id,
                    event_type="recovery_requeued",
                    actor="recovery_sweep",
                    span_id="recovery_sweep",
                    phase="recovery",
                    payload={
                        "work_item_id": work_item_id,
                        "previous_holder": item['lease_holder'],
                        "retry_count": new_retry_count,
                        "max_retries": max_retries,
                        "explanation": f"Work item re-queued after lease expiration (retry {new_retry_count}/{max_retries})"
                    }
                )
            except Exception as e:
                logger.error(f"Failed to emit recovery_requeued event: {e}")
        else:
            stats.failed += 1
            logger.warning(
                f"Work item permanently failed: {work_item_id} "
                f"(max retries exceeded, holder: {item['lease_holder']})"
            )

        # Create error boundary checkpoint
        if self.create_checkpoints:
            try:
                self._create_error_checkpoint(item, new_retry_count, should_retry, conn)
                stats.checkpoints_created += 1
            except Exception as e:
                logger.error(f"Failed to create checkpoint for {work_item_id}: {e}")
                # Don't fail recovery if checkpoint creation fails

    def _create_error_checkpoint(
        self,
        item: sqlite3.Row,
        new_retry_count: int,
        should_retry: bool,
        conn: sqlite3.Connection
    ) -> None:
        """Create error boundary checkpoint for audit trail

        Args:
            item: Work item database row
            new_retry_count: Updated retry count
            should_retry: Whether work item will be retried
            conn: Database connection to use
        """
        import uuid

        # Get next sequence number for this task
        cursor = conn.execute("""
            SELECT COALESCE(MAX(sequence_number), 0) + 1 as next_seq
            FROM checkpoints
            WHERE task_id = ?
        """, (item['task_id'],))

        next_seq = cursor.fetchone()[0]

        # Create checkpoint
        checkpoint_id = f"ckpt-{uuid.uuid4().hex[:16]}"
        snapshot_data = {
            "error": "Lease expired",
            "retry_count": new_retry_count,
            "max_retries": item['max_retries'],
            "will_retry": should_retry,
            "expired_lease": {
                "holder": item['lease_holder'],
                "acquired_at": item['lease_acquired_at'],
                "expires_at": item['lease_expires_at'],
                "last_heartbeat": item['heartbeat_at'],
            },
            "timestamp": utc_now_iso(),
        }

        conn.execute("""
            INSERT INTO checkpoints (
                checkpoint_id, task_id, work_item_id,
                checkpoint_type, sequence_number, snapshot_data
            ) VALUES (?, ?, ?, 'error_boundary', ?, ?)
        """, (
            checkpoint_id,
            item['task_id'],
            item['work_item_id'],
            next_seq,
            json.dumps(snapshot_data)
        ))

    def _cleanup_old_checkpoints(self, conn: sqlite3.Connection) -> None:
        """Clean up old checkpoints to prevent unbounded growth

        Args:
            conn: Database connection to use
        """
        try:
            # Get tasks with too many checkpoints
            cursor = conn.execute("""
                SELECT task_id, COUNT(*) as count
                FROM checkpoints
                GROUP BY task_id
                HAVING count > ?
            """, (self.checkpoint_retention_limit,))

            tasks_to_clean = cursor.fetchall()

            if not tasks_to_clean:
                return

            logger.debug(f"Cleaning up old checkpoints for {len(tasks_to_clean)} tasks")

            for task_row in tasks_to_clean:
                task_id = task_row['task_id']

                # Delete old checkpoints, keeping only the most recent N
                conn.execute("""
                    DELETE FROM checkpoints
                    WHERE checkpoint_id IN (
                        SELECT checkpoint_id
                        FROM checkpoints
                        WHERE task_id = ?
                        ORDER BY sequence_number DESC
                        LIMIT -1 OFFSET ?
                    )
                """, (task_id, self.checkpoint_retention_limit))

            conn.commit()

        except Exception as e:
            logger.error(f"Failed to cleanup old checkpoints: {e}")
            # Don't fail sweep if cleanup fails

    def _sweep_loop(self) -> None:
        """Main sweep loop (runs in separate thread)"""
        logger.debug("Recovery sweep loop started")

        # Get thread-local connection for this background thread
        # Note: We cannot use the provided conn from __init__ because that was
        # created in a different thread (SQLite check_same_thread restriction)
        thread_conn = None
        use_thread_factory = False

        try:
            from agentos.store import get_thread_connection
            thread_conn = get_thread_connection()
            use_thread_factory = True
            logger.debug("Recovery sweep using thread-local connection from factory")
        except RuntimeError:
            # Factory not initialized - need to create connection for this thread
            if self._db_path is not None:
                # Create a new connection in this thread using stored DB path
                try:
                    thread_conn = sqlite3.connect(self._db_path)
                    thread_conn.row_factory = sqlite3.Row
                    thread_conn.execute("PRAGMA foreign_keys = ON")
                    thread_conn.execute("PRAGMA journal_mode = WAL")
                    thread_conn.execute("PRAGMA synchronous = NORMAL")
                    thread_conn.execute("PRAGMA busy_timeout = 5000")
                    logger.debug(f"Recovery sweep created new connection in background thread: {self._db_path}")
                except Exception as e:
                    logger.error(f"Failed to create thread connection: {e}")
                    self._running = False
                    return
            else:
                logger.error("No database path or factory available for recovery sweep")
                self._running = False
                return

        try:
            while not self._stop_event.is_set():
                try:
                    # Perform scan and recovery with thread-local connection
                    stats = self.scan_and_recover(conn=thread_conn)
                    self.last_scan_stats = stats
                    self.total_scans += 1
                    self.total_recovered += stats.recovered
                    self.total_failed += stats.failed

                except Exception as e:
                    logger.exception(f"Error in recovery sweep: {e}")

                # Wait for interval or stop event
                if self._stop_event.wait(timeout=self.scan_interval_seconds):
                    # Stop event was set
                    break

        finally:
            self._running = False

            # Close connection
            if use_thread_factory:
                # Close thread-local connection if using factory
                try:
                    from agentos.store import close_thread_connection
                    close_thread_connection()
                    logger.debug("Closed thread-local connection for recovery sweep")
                except Exception as e:
                    logger.debug(f"Could not close thread connection: {e}")
            elif thread_conn is not None:
                # Close manually created connection
                try:
                    thread_conn.close()
                    logger.debug("Closed background thread connection")
                except Exception as e:
                    logger.debug(f"Could not close thread connection: {e}")

            logger.debug("Recovery sweep loop finished")

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics

        Returns:
            Dictionary with sweep statistics
        """
        return {
            "is_running": self.is_running(),
            "total_scans": self.total_scans,
            "total_recovered": self.total_recovered,
            "total_failed": self.total_failed,
            "last_scan": self.last_scan_stats.to_dict() if self.last_scan_stats else None,
        }
