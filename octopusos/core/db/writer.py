"""Single-threaded SQLite write serializer with retry logic.

This module provides SQLiteWriter, a singleton class that serializes all write
operations to a SQLite database through a dedicated background thread. It handles
database locking gracefully with exponential backoff retry logic.

Design Goals:
1. Eliminate "database is locked" errors in multi-threaded applications
2. Provide predictable, linearized write ordering
3. Gracefully handle transient SQLite locking with automatic retries
4. Minimize caller complexity with simple submit() interface

Usage Example:
    from agentos.core.db import SQLiteWriter
    from agentos.core.storage.paths import component_db_path

    # Initialize writer (singleton pattern)
    writer = SQLiteWriter(db_path=str(component_db_path("agentos")))

    # Submit write operations
    def insert_task(conn):
        conn.execute(
            "INSERT INTO tasks (id, name) VALUES (?, ?)",
            ("task-1", "Process data")
        )
        return conn.lastrowid

    # Submit returns the result of the write function
    task_id = writer.submit(insert_task, timeout=10.0)

    # Clean shutdown
    writer.stop()

Thread Safety:
    - All write operations are serialized through a single background thread
    - Multiple threads can safely call submit() concurrently
    - The writer uses thread-safe Queue for coordination

Error Handling:
    - Transient errors (locked/busy) trigger automatic retry with exponential backoff
    - Non-transient errors are propagated to the caller
    - Timeout errors raise TimeoutError after the specified duration
"""

import logging
import queue
import sqlite3
import threading
import time
from dataclasses import dataclass
from sqlite3 import Connection
from typing import Any, Callable, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class WriteJob:
    """Represents a write operation to be executed by the background thread.

    Attributes:
        fn: Callable that accepts a Connection and performs write operations
        result_q: Queue to receive execution result as (success, result) tuple
    """
    fn: Callable[[Connection], Any]
    result_q: queue.Queue[Tuple[bool, Any]]


class SQLiteWriter:
    """Single-threaded SQLite write serializer.

    Serializes all write operations through a dedicated background thread to
    eliminate database locking issues. Implements singleton pattern to ensure
    only one writer exists per database path in the process.

    Key Features:
    - Background thread processes writes from a queue
    - BEGIN IMMEDIATE for early write lock acquisition
    - Exponential backoff retry for transient lock errors
    - Graceful timeout handling with error propagation

    Parameters:
        db_path: Path to the SQLite database file
        busy_timeout: SQLite busy timeout in milliseconds (default: 30000)
        max_retry: Maximum retry attempts for locked operations (default: 8)
        initial_delay: Initial retry delay in seconds (default: 0.02)
        max_delay: Maximum retry delay in seconds (default: 0.5)
    """

    # Class-level registry for singleton pattern
    _instances: dict[str, "SQLiteWriter"] = {}
    _lock = threading.Lock()

    def __new__(cls, db_path: str, **kwargs):
        """Ensure singleton per db_path."""
        with cls._lock:
            if db_path not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[db_path] = instance
            return cls._instances[db_path]

    def __init__(
        self,
        db_path: str,
        busy_timeout: int = 30000,
        max_retry: int = 8,
        initial_delay: float = 0.02,
        max_delay: float = 0.5,
    ):
        """Initialize the SQLiteWriter.

        Note: Due to singleton pattern, __init__ may be called multiple times
        but only the first call will perform initialization.

        Args:
            db_path: Path to SQLite database
            busy_timeout: Busy timeout in milliseconds
            max_retry: Maximum retry attempts
            initial_delay: Initial retry delay in seconds
            max_delay: Maximum retry delay in seconds
        """
        # Avoid re-initialization for singleton
        if hasattr(self, "_initialized"):
            return

        self.db_path = db_path
        self.busy_timeout = busy_timeout
        self.max_retry = max_retry
        self.initial_delay = initial_delay
        self.max_delay = max_delay

        self._queue: queue.Queue[Optional[WriteJob]] = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._conn: Optional[Connection] = None

        # Monitoring metrics
        self._total_writes = 0
        self._total_retries = 0
        self._failed_writes = 0
        self._total_write_time = 0.0
        self._high_water_mark = 0  # Historical max queue length
        self._start_time = time.time()

        # Start background thread
        self._start()
        self._initialized = True

        logger.info(
            f"SQLiteWriter initialized: db_path={db_path}, "
            f"busy_timeout={busy_timeout}ms, max_retry={max_retry}"
        )

    def _open(self) -> Connection:
        """Open database connection with optimized PRAGMA settings.

        Returns:
            sqlite3.Connection configured for write operations
        """
        conn = sqlite3.connect(self.db_path)

        # Configure row_factory for dict-style access (needed for some read-after-write scenarios)
        conn.row_factory = sqlite3.Row

        # Configure for optimal write performance and concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(f"PRAGMA busy_timeout={self.busy_timeout}")

        logger.debug(f"Database connection opened: {self.db_path}")
        return conn

    def _start(self):
        """Start the background writer thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Background writer thread started")

    def _run(self):
        """Background thread main loop - processes write jobs from queue."""
        try:
            self._conn = self._open()

            while not self._stop_flag.is_set():
                try:
                    # Update high water mark
                    current_size = self._queue.qsize()
                    if current_size > self._high_water_mark:
                        self._high_water_mark = current_size

                    # Queue backlog alerts
                    if current_size > 100:
                        logger.error(
                            f"SQLiteWriter queue critical: {current_size} items. "
                            f"Performance degradation likely. Immediate action required."
                        )
                    elif current_size > 50:
                        logger.warning(
                            f"SQLiteWriter queue backlog: {current_size} items. "
                            f"Consider optimizing write patterns or migrating to PostgreSQL."
                        )

                    # Use timeout to periodically check stop flag
                    job = self._queue.get(timeout=0.5)

                    if job is None:  # Sentinel for shutdown
                        break

                    # Execute with retry logic
                    success, result = self._exec_with_retry(
                        self._conn, job.fn, self.max_retry
                    )

                    # Send result back to caller
                    job.result_q.put((success, result))

                except queue.Empty:
                    continue

        except Exception as e:
            logger.error(f"Fatal error in writer thread: {e}", exc_info=True)
        finally:
            if self._conn:
                self._conn.close()
                logger.debug("Database connection closed")

    def _exec_with_retry(
        self,
        conn: Connection,
        fn: Callable[[Connection], Any],
        max_retry: int,
    ) -> Tuple[bool, Any]:
        """Execute write function with exponential backoff retry.

        Wraps the user function in a transaction with BEGIN IMMEDIATE to
        acquire write lock early. Retries on transient lock errors.

        Args:
            conn: Database connection
            fn: User function to execute
            max_retry: Maximum retry attempts

        Returns:
            Tuple of (success: bool, result: Any)
            - If successful, returns (True, function_result)
            - If failed, returns (False, exception)
        """
        delay = self.initial_delay
        start_time = time.time()

        for attempt in range(max_retry):
            try:
                # Track retries (after first attempt)
                if attempt > 0:
                    self._total_retries += 1

                # Acquire write lock immediately
                conn.execute("BEGIN IMMEDIATE")

                try:
                    result = fn(conn)
                    conn.commit()

                    # Update metrics on success
                    self._total_writes += 1
                    self._total_write_time += (time.time() - start_time)

                    # Periodic stats logging
                    if self._total_writes % 100 == 0:
                        logger.info(
                            f"SQLiteWriter stats: "
                            f"queue={self.queue_size}, "
                            f"high_water={self.queue_high_water_mark}, "
                            f"retries={self.total_retries}, "
                            f"failed={self.failed_writes}, "
                            f"latency={self.avg_write_latency_ms:.2f}ms, "
                            f"throughput={self.throughput_per_second:.2f}/s"
                        )

                    return (True, result)
                except Exception as e:
                    conn.rollback()
                    raise

            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()

                # Check if it's a transient lock error
                if "locked" in error_msg or "busy" in error_msg:
                    if attempt < max_retry - 1:
                        logger.warning(
                            f"Database locked, retry {attempt + 1}/{max_retry} "
                            f"after {delay:.3f}s: {e}"
                        )
                        time.sleep(delay)
                        # Exponential backoff with cap
                        delay = min(delay * 2, self.max_delay)
                        continue
                    else:
                        logger.error(
                            f"Database locked after {max_retry} retries: {e}"
                        )
                        self._failed_writes += 1
                        self._total_write_time += (time.time() - start_time)
                        return (False, e)
                else:
                    # Non-transient operational error
                    logger.error(f"SQLite operational error: {e}", exc_info=True)
                    self._failed_writes += 1
                    self._total_write_time += (time.time() - start_time)
                    return (False, e)

            except Exception as e:
                # Any other exception
                logger.error(f"Write operation failed: {e}", exc_info=True)
                self._failed_writes += 1
                self._total_write_time += (time.time() - start_time)
                return (False, e)

        # Should not reach here
        error = RuntimeError("Unexpected: exceeded max retry without returning")
        logger.error(str(error))
        self._failed_writes += 1
        self._total_write_time += (time.time() - start_time)
        return (False, error)

    def submit(
        self,
        fn: Callable[[Connection], Any],
        timeout: float = 10.0,
    ) -> Any:
        """Submit a write operation for execution.

        The function will be executed in the background thread with automatic
        retry logic. This method blocks until the operation completes or timeout.

        Args:
            fn: Callable that accepts a Connection and performs write operations
            timeout: Maximum time to wait for completion in seconds

        Returns:
            The return value of fn() if successful

        Raises:
            TimeoutError: If operation doesn't complete within timeout
            Exception: Any exception raised by fn() is re-raised here

        Example:
            def my_write(conn):
                conn.execute("INSERT INTO logs (msg) VALUES (?)", ("test",))
                return conn.lastrowid

            log_id = writer.submit(my_write, timeout=5.0)
        """
        result_q: queue.Queue[Tuple[bool, Any]] = queue.Queue()
        job = WriteJob(fn=fn, result_q=result_q)

        # Enqueue the job
        self._queue.put(job)

        # Wait for result
        try:
            success, result = result_q.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError(
                f"Write operation timed out after {timeout}s"
            )

        # Propagate errors to caller
        if not success:
            raise result  # result is the exception

        return result

    def stop(self, timeout: float = 5.0):
        """Gracefully stop the background writer thread.

        Sends a sentinel value to the queue and waits for the thread to exit.

        Args:
            timeout: Maximum time to wait for thread shutdown in seconds
        """
        if self._thread is None or not self._thread.is_alive():
            return

        logger.info("Stopping writer thread...")
        self._stop_flag.set()
        self._queue.put(None)  # Sentinel to unblock queue.get()

        self._thread.join(timeout=timeout)

        if self._thread.is_alive():
            logger.warning(f"Writer thread did not stop within {timeout}s")
        else:
            logger.info("Writer thread stopped successfully")

    @classmethod
    def get_instance(cls, db_path: str) -> Optional["SQLiteWriter"]:
        """Get existing writer instance for a database path.

        Args:
            db_path: Database path to lookup

        Returns:
            SQLiteWriter instance if exists, None otherwise
        """
        with cls._lock:
            return cls._instances.get(db_path)

    @classmethod
    def shutdown_all(cls, timeout: float = 5.0):
        """Shutdown all writer instances.

        Useful for graceful application shutdown.

        Args:
            timeout: Maximum time to wait for each writer to stop
        """
        with cls._lock:
            instances = list(cls._instances.values())

        for writer in instances:
            writer.stop(timeout=timeout)

        logger.info(f"Shutdown {len(instances)} writer instance(s)")

    # Monitoring Properties

    @property
    def queue_size(self) -> int:
        """Current queue length."""
        return self._queue.qsize()

    @property
    def queue_high_water_mark(self) -> int:
        """Historical maximum queue length."""
        return self._high_water_mark

    @property
    def total_writes(self) -> int:
        """Total number of successful write operations."""
        return self._total_writes

    @property
    def total_retries(self) -> int:
        """Total number of retry attempts."""
        return self._total_retries

    @property
    def failed_writes(self) -> int:
        """Number of failed write operations."""
        return self._failed_writes

    @property
    def avg_write_latency_ms(self) -> float:
        """Average write latency in milliseconds."""
        if self._total_writes == 0:
            return 0.0
        return (self._total_write_time / self._total_writes) * 1000

    @property
    def throughput_per_second(self) -> float:
        """Write operations per second."""
        uptime = time.time() - self._start_time
        return self._total_writes / uptime if uptime > 0 else 0.0

    def get_stats(self) -> dict:
        """Get all monitoring statistics.

        Returns:
            Dictionary containing all monitoring metrics:
            - queue_size: Current queue length
            - queue_high_water_mark: Historical max queue length
            - total_writes: Total successful writes
            - total_retries: Total retry attempts
            - failed_writes: Total failed writes
            - avg_write_latency_ms: Average latency in milliseconds
            - throughput_per_second: Operations per second
            - uptime_seconds: Time since writer started

        Example:
            stats = writer.get_stats()
            print(f"Queue size: {stats['queue_size']}")
            print(f"Throughput: {stats['throughput_per_second']:.2f} ops/s")
        """
        return {
            "queue_size": self.queue_size,
            "queue_high_water_mark": self.queue_high_water_mark,
            "total_writes": self.total_writes,
            "total_retries": self.total_retries,
            "failed_writes": self.failed_writes,
            "avg_write_latency_ms": self.avg_write_latency_ms,
            "throughput_per_second": self.throughput_per_second,
            "uptime_seconds": time.time() - self._start_time,
        }
