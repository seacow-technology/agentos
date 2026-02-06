"""
Log storage with hybrid strategy: memory + optional persistence.

Provides high-performance in-memory storage with thread-safe operations
and optional SQLite persistence for audit trails.

Storage Strategy:
- Primary: collections.deque (bounded, FIFO, thread-safe in CPython)
- Optional: SQLite persistence (async writes via background thread)
- Memory limit: 5000 logs (~25MB estimated)

Performance Targets:
- add(): O(1), < 100μs
- query(): O(n), acceptable for 5000 items
- Persistence: Non-blocking (queued background writes)
"""

import logging
import threading
import queue
import sqlite3
from collections import deque
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pathlib import Path

from agentos.core.logging.models import LogEntry


logger = logging.getLogger(__name__)


class LogStore:
    """
    Thread-safe log storage with bounded memory and optional persistence.

    Features:
    - Bounded in-memory storage (automatic FIFO eviction)
    - Thread-safe operations (RLock)
    - Optional SQLite persistence (background thread)
    - Multi-dimensional filtering
    """

    def __init__(
        self,
        max_size: int = 5000,
        persist: bool = False,
        db_path: Optional[str] = None,
    ):
        """
        Initialize the log store.

        Args:
            max_size: Maximum logs to keep in memory
            persist: Enable SQLite persistence
            db_path: Path to SQLite database (required if persist=True)
        """
        self.max_size = max_size
        self.persist = persist
        self.db_path = db_path

        # In-memory storage (thread-safe deque)
        self._logs: deque = deque(maxlen=max_size)
        self._lock = threading.RLock()

        # Persistence components
        self._persist_queue: Optional[queue.Queue] = None
        self._persist_thread: Optional[threading.Thread] = None
        self._shutdown = threading.Event()

        if persist:
            if not db_path:
                raise ValueError("db_path is required when persist=True")
            self._init_persistence()

    def _init_persistence(self) -> None:
        """Initialize persistence components.

        Note: task_audits table schema is managed by migration scripts.
        See: agentos/store/migrations/schema_v06.sql (initial schema)
              agentos/store/migrations/schema_v24.sql (updates)

        The table must exist before this store is initialized.
        Run migrations first if starting fresh.
        """
        try:
            # Ensure database directory exists
            db_file = Path(self.db_path)
            db_file.parent.mkdir(parents=True, exist_ok=True)

            # Verify schema exists (managed by migrations)
            # If table doesn't exist, fail fast with clear error
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='task_audits'"
            )
            if not cursor.fetchone():
                conn.close()
                raise RuntimeError(
                    "Schema not initialized. task_audits table does not exist. "
                    "Please run migrations first: python -m agentos.store.migrations.run_p0_migration"
                )
            conn.close()

            # Start background persistence worker
            self._persist_queue = queue.Queue(maxsize=1000)
            self._persist_thread = threading.Thread(
                target=self._persistence_worker, daemon=True, name="LogPersistenceWorker"
            )
            self._persist_thread.start()

            logger.info(f"Log persistence initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize log persistence: {e}", exc_info=True)
            self.persist = False

    def _persistence_worker(self) -> None:
        """Background worker for asynchronous log persistence."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            while not self._shutdown.is_set():
                try:
                    # Block with timeout to allow shutdown check
                    log_entry = self._persist_queue.get(timeout=1.0)
                    if log_entry is None:  # Poison pill for shutdown
                        break

                    # Write to database
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO task_audits
                        (id, level, timestamp, task_id, session_id, span_id, message, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            log_entry.id,
                            log_entry.level,
                            log_entry.timestamp,
                            log_entry.task_id,
                            log_entry.session_id,
                            log_entry.span_id,
                            log_entry.message,
                            str(log_entry.metadata) if log_entry.metadata else None,
                        ),
                    )
                    conn.commit()
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error persisting log: {e}")
        except Exception as e:
            logger.error(f"Persistence worker error: {e}", exc_info=True)
        finally:
            if conn:
                conn.close()

    def add(self, log_entry: LogEntry) -> None:
        """
        Add a log entry to the store.

        Thread-safe operation with O(1) complexity.
        If persistence is enabled, queues for async write.

        Args:
            log_entry: The log entry to store
        """
        with self._lock:
            self._logs.append(log_entry)

        # Queue for persistence (non-blocking)
        if self.persist and self._persist_queue:
            try:
                self._persist_queue.put_nowait(log_entry)
            except queue.Full:
                # Drop persistence if queue is full (non-blocking guarantee)
                logger.warning("Log persistence queue full, dropping write")

    def query(
        self,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None,
        level: Optional[str] = None,
        since: Optional[str] = None,
        logger_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[LogEntry]:
        """
        Query logs with filters.

        Args:
            task_id: Filter by task ID
            session_id: Filter by session ID
            level: Filter by log level
            since: Filter logs since timestamp (ISO 8601)
            logger_name: Filter by logger name (in metadata)
            limit: Maximum results

        Returns:
            List of log entries matching filters (newest first)
        """
        with self._lock:
            logs = list(self._logs)

        # Apply filters
        if task_id:
            logs = [log for log in logs if log.task_id == task_id]
        if session_id:
            logs = [log for log in logs if log.session_id == session_id]
        if level:
            logs = [log for log in logs if log.level.lower() == level.lower()]
        if since:
            logs = [log for log in logs if log.timestamp >= since]
        if logger_name:
            logs = [
                log
                for log in logs
                if log.metadata.get("logger") == logger_name
            ]

        # Sort by timestamp (newest first) and limit
        logs = sorted(logs, key=lambda log: log.timestamp, reverse=True)[:limit]

        return logs

    def clear(self) -> None:
        """Clear all logs from memory (persistence not affected)."""
        with self._lock:
            self._logs.clear()

    def shutdown(self) -> None:
        """Gracefully shutdown the log store."""
        if self.persist and self._persist_thread:
            self._shutdown.set()
            if self._persist_queue:
                self._persist_queue.put(None)  # Poison pill
            self._persist_thread.join(timeout=5.0)
            logger.info("Log store shutdown complete")

    def __len__(self) -> int:
        """Return the current number of logs in memory."""
        with self._lock:
            return len(self._logs)
