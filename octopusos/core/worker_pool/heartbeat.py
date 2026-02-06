"""Heartbeat Thread - Automatic lease renewal in background

This module provides a background thread that periodically sends heartbeats
to renew work item leases, ensuring that long-running tasks don't lose
their lease due to expiration.

Design:
- Separate thread per work item (lightweight)
- Configurable heartbeat interval (default: 30 seconds)
- Automatic shutdown on completion or error
- Thread-safe operation
"""

import logging
import sqlite3
import threading
import time
from typing import Optional, Callable

from .lease import LeaseManager, LeaseError, LeaseExpiredError

logger = logging.getLogger(__name__)


class HeartbeatThread:
    """Background thread that sends periodic heartbeats to renew a lease

    This thread runs independently and automatically renews the lease
    at regular intervals. It stops when:
    - stop() is called explicitly
    - Lease renewal fails (lease expired or lost)
    - Maximum failures reached

    Example:
        >>> heartbeat = HeartbeatThread(
        ...     lease_manager=manager,
        ...     work_item_id="work-123",
        ...     interval_seconds=30
        ... )
        >>> heartbeat.start()
        >>> # ... do work ...
        >>> heartbeat.stop()
    """

    def __init__(
        self,
        lease_manager: LeaseManager,
        work_item_id: str,
        interval_seconds: int = 30,
        lease_duration_seconds: int = 300,
        max_failures: int = 3,
        on_lease_lost: Optional[Callable[[], None]] = None
    ):
        """Initialize heartbeat thread

        Args:
            lease_manager: LeaseManager instance to use for renewals
            work_item_id: ID of the work item to send heartbeats for
            interval_seconds: How often to send heartbeats (default: 30s)
            lease_duration_seconds: How long to extend lease on each heartbeat (default: 300s)
            max_failures: Maximum consecutive failures before giving up (default: 3)
            on_lease_lost: Optional callback when lease is lost
        """
        self.lease_manager = lease_manager
        self.work_item_id = work_item_id
        self.interval_seconds = interval_seconds
        self.lease_duration_seconds = lease_duration_seconds
        self.max_failures = max_failures
        self.on_lease_lost = on_lease_lost

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._failure_count = 0

    def start(self) -> None:
        """Start the heartbeat thread"""
        if self._running:
            logger.warning(f"Heartbeat already running for {self.work_item_id}")
            return

        self._stop_event.clear()
        self._running = True
        self._failure_count = 0

        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"Heartbeat-{self.work_item_id}",
            daemon=True
        )
        self._thread.start()

        logger.info(
            f"Heartbeat started: work_item={self.work_item_id}, "
            f"interval={self.interval_seconds}s"
        )

    def stop(self, wait: bool = True, timeout: float = 5.0) -> None:
        """Stop the heartbeat thread

        Args:
            wait: Whether to wait for thread to finish (default: True)
            timeout: Maximum time to wait in seconds (default: 5.0)
        """
        if not self._running:
            return

        self._stop_event.set()
        self._running = False

        if wait and self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning(
                    f"Heartbeat thread for {self.work_item_id} did not stop within timeout"
                )

        logger.info(f"Heartbeat stopped: work_item={self.work_item_id}")

    def is_running(self) -> bool:
        """Check if heartbeat thread is running"""
        return self._running and self._thread is not None and self._thread.is_alive()

    def _heartbeat_loop(self) -> None:
        """Main heartbeat loop (runs in separate thread)"""
        logger.debug(f"Heartbeat loop started for {self.work_item_id}")

        try:
            while not self._stop_event.is_set():
                # Wait for interval or stop event
                if self._stop_event.wait(timeout=self.interval_seconds):
                    # Stop event was set
                    break

                # Send heartbeat
                try:
                    success = self.lease_manager.renew_lease(
                        self.work_item_id,
                        lease_duration_seconds=self.lease_duration_seconds
                    )

                    if success:
                        self._failure_count = 0  # Reset failure counter
                        logger.debug(f"Heartbeat sent: work_item={self.work_item_id}")
                    else:
                        self._handle_failure("Renewal returned False")

                except LeaseExpiredError as e:
                    logger.error(f"Lease expired for {self.work_item_id}: {e}")
                    self._handle_lease_lost("Lease expired")
                    break

                except LeaseError as e:
                    logger.error(f"Lease error for {self.work_item_id}: {e}")
                    self._handle_failure(str(e))

                except Exception as e:
                    logger.exception(f"Unexpected error in heartbeat for {self.work_item_id}: {e}")
                    self._handle_failure(str(e))

        finally:
            self._running = False
            logger.debug(f"Heartbeat loop finished for {self.work_item_id}")

    def _handle_failure(self, reason: str) -> None:
        """Handle heartbeat failure

        Args:
            reason: Reason for failure
        """
        self._failure_count += 1
        logger.warning(
            f"Heartbeat failure ({self._failure_count}/{self.max_failures}) "
            f"for {self.work_item_id}: {reason}"
        )

        if self._failure_count >= self.max_failures:
            logger.error(
                f"Max heartbeat failures reached for {self.work_item_id}, "
                f"assuming lease lost"
            )
            self._handle_lease_lost(f"Max failures: {reason}")

    def _handle_lease_lost(self, reason: str) -> None:
        """Handle lease lost scenario

        Args:
            reason: Reason lease was lost
        """
        logger.error(f"Lease lost for {self.work_item_id}: {reason}")
        self._running = False
        self._stop_event.set()

        if self.on_lease_lost:
            try:
                self.on_lease_lost()
            except Exception as e:
                logger.exception(f"Error in lease lost callback: {e}")


def start_heartbeat(
    conn: sqlite3.Connection,
    work_item_id: str,
    worker_id: str,
    interval_seconds: int = 30,
    lease_duration_seconds: int = 300,
    on_lease_lost: Optional[Callable[[], None]] = None
) -> HeartbeatThread:
    """Convenience function to start a heartbeat thread

    Args:
        conn: Database connection
        work_item_id: ID of work item
        worker_id: Worker identifier
        interval_seconds: Heartbeat interval (default: 30s)
        lease_duration_seconds: Lease extension duration (default: 300s)
        on_lease_lost: Optional callback when lease is lost

    Returns:
        HeartbeatThread instance (already started)

    Example:
        >>> heartbeat = start_heartbeat(conn, "work-123", "worker-abc")
        >>> # ... do work ...
        >>> heartbeat.stop()
    """
    lease_manager = LeaseManager(conn, worker_id)
    heartbeat = HeartbeatThread(
        lease_manager=lease_manager,
        work_item_id=work_item_id,
        interval_seconds=interval_seconds,
        lease_duration_seconds=lease_duration_seconds,
        on_lease_lost=on_lease_lost
    )
    heartbeat.start()
    return heartbeat
