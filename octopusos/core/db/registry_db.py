"""Unified database access entry point.

This module provides the single source of truth for all database connections
in OctopusOS. All database access MUST go through this module.

Architecture:
- Thread-local storage for read connections (connection pooling per thread)
- Unified PRAGMA settings for consistency
- Single DB path configuration from environment variable
- Query helpers with consistent error handling

Prohibited:
- Direct use of sqlite3.connect() anywhere else in the codebase
- Direct use of apsw.Connection() anywhere else in the codebase

Exceptions:
- octopusos/core/db/writer.py: Can use sqlite3.connect() for write operations
- Test files: Can use sqlite3.connect() with test fixtures
"""

import os
import sqlite3
import logging
import threading
import atexit
from pathlib import Path
from typing import Any, List, Optional, Tuple, Dict
from contextlib import contextmanager

from octopusos.core.storage.paths import component_db_path

logger = logging.getLogger(__name__)

# Thread-local storage for connections
_thread_local = threading.local()
_CONNECTIONS_BY_THREAD: Dict[int, sqlite3.Connection] = {}
_CONNECTIONS_LOCK = threading.Lock()

# Database path (read once from environment)
_DB_PATH: Optional[str] = None
_DB_PATH_LOCK = threading.Lock()


def _get_db_path() -> str:
    """Get database path (initialized once from environment).

    Priority:
    1. OCTOPUSOS_DB_PATH environment variable (backward compatibility)
    2. Unified path from storage.paths module

    Returns:
        Absolute path to database file
    """
    global _DB_PATH

    if _DB_PATH is None:
        with _DB_PATH_LOCK:
            if _DB_PATH is None:
                # Priority 1: Use environment variable (backward compatibility)
                env_path = os.getenv("OCTOPUSOS_DB_PATH")
                if env_path:
                    _DB_PATH = str(Path(env_path).resolve())
                    logger.info(f"DB path initialized from env: {_DB_PATH}")
                else:
                    # Priority 2: Use unified path management
                    _DB_PATH = str(component_db_path("octopusos").resolve())
                    logger.info(f"DB path initialized from storage.paths: {_DB_PATH}")

    return _DB_PATH


def get_db_path() -> str:
    """Return the resolved database path (public helper).

    This mirrors the internal _get_db_path() and is safe for non-test code that
    needs the active DB path (e.g., initializing SQLiteWriter with the same DB).
    """
    return _get_db_path()


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply standard PRAGMA settings to connection.

    Args:
        conn: SQLite connection to configure
    """
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")


def get_db() -> sqlite3.Connection:
    """Get thread-local database connection.

    This function returns a thread-local connection with proper PRAGMA settings.
    Connections are cached per thread to avoid overhead of repeated connection setup.

    Auto-migration: Automatically runs pending migrations on first connection.

    Returns:
        sqlite3.Connection: Configured database connection

    Thread Safety:
        Each thread gets its own connection. Multiple calls from the same thread
        return the same connection.

    Example:
        >>> conn = get_db()
        >>> cursor = conn.cursor()
        >>> rows = cursor.execute("SELECT * FROM tasks").fetchall()
    """
    if not hasattr(_thread_local, "connection") or _thread_local.connection is None:
        db_path = _get_db_path()

        # Check if database exists
        if not Path(db_path).exists():
            raise FileNotFoundError(
                f"Database not initialized: {db_path}. Run 'octopusos init' first."
            )

        # Auto-migrate (only on first connection per thread)
        try:
            from octopusos.store.migrator import auto_migrate
            migrated = auto_migrate(Path(db_path))
            if migrated > 0:
                logger.info(f"Applied {migrated} pending migrations")
        except Exception as e:
            logger.warning(f"Auto-migration failed: {e}")
            # Don't block connection on migration failure

        # Create new connection
        # Allow deterministic cleanup from non-owner threads (e.g. test teardown
        # and threadpool lifecycles) while keeping per-thread connection usage.
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row

        # Apply standard PRAGMA settings
        _apply_pragmas(conn)

        # 🔍 DEBUG MODE: Wrap connection to trace close() calls
        # Enable this to debug "database is closed" errors
        DEBUG_TRACE_CLOSE = os.getenv("OCTOPUSOS_DEBUG_DB_CLOSE", "false").lower() == "true"
        if DEBUG_TRACE_CLOSE:
            from octopusos.core.db._connection_wrapper import DebugConnection
            conn = DebugConnection(conn)
            logger.warning("🔍 DB close tracing ENABLED (set OCTOPUSOS_DEBUG_DB_CLOSE=false to disable)")

        # Store in thread-local storage
        _thread_local.connection = conn
        with _CONNECTIONS_LOCK:
            _CONNECTIONS_BY_THREAD[threading.get_ident()] = conn

        logger.debug(f"Created DB connection for thread {threading.current_thread().name}")

    return _thread_local.connection


def close_db() -> None:
    """Close the thread-local database connection.

    This is typically called when a thread is shutting down or when you want
    to explicitly release the connection.

    Example:
        >>> close_db()  # Close current thread's connection
    """
    if hasattr(_thread_local, "connection") and _thread_local.connection is not None:
        try:
            _thread_local.connection.close()
            logger.debug(f"Closed DB connection for thread {threading.current_thread().name}")
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")
        finally:
            with _CONNECTIONS_LOCK:
                _CONNECTIONS_BY_THREAD.pop(threading.get_ident(), None)
            _thread_local.connection = None


def close_all_db() -> None:
    """Close all tracked thread-local database connections.

    Primarily used for test cleanup and interpreter shutdown to prevent leaked
    sqlite connections from surfacing as ResourceWarning.
    """
    with _CONNECTIONS_LOCK:
        items = list(_CONNECTIONS_BY_THREAD.items())
        _CONNECTIONS_BY_THREAD.clear()

    for _, conn in items:
        try:
            conn.close()
        except Exception as e:
            logger.warning(f"Error closing tracked connection: {e}")

    if hasattr(_thread_local, "connection"):
        _thread_local.connection = None


def query_one(sql: str, params: Optional[Tuple[Any, ...]] = None) -> Optional[sqlite3.Row]:
    """Execute query and return single row.

    Args:
        sql: SQL query string
        params: Query parameters (optional)

    Returns:
        Single row as sqlite3.Row, or None if no results

    Example:
        >>> row = query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
        >>> if row:
        ...     print(row["name"])
    """
    conn = get_db()
    cursor = conn.cursor()

    if params:
        cursor.execute(sql, params)
    else:
        cursor.execute(sql)

    return cursor.fetchone()


def query_all(sql: str, params: Optional[Tuple[Any, ...]] = None) -> List[sqlite3.Row]:
    """Execute query and return all rows.

    Args:
        sql: SQL query string
        params: Query parameters (optional)

    Returns:
        List of rows as sqlite3.Row objects

    Example:
        >>> rows = query_all("SELECT * FROM tasks WHERE status = ?", ("pending",))
        >>> for row in rows:
        ...     print(row["id"], row["name"])
    """
    conn = get_db()
    cursor = conn.cursor()

    if params:
        cursor.execute(sql, params)
    else:
        cursor.execute(sql)

    return cursor.fetchall()


def execute(sql: str, params: Optional[Tuple[Any, ...]] = None) -> sqlite3.Cursor:
    """Execute SQL statement (INSERT/UPDATE/DELETE).

    Args:
        sql: SQL statement string
        params: Statement parameters (optional)

    Returns:
        sqlite3.Cursor with execution results

    Note:
        This does NOT commit automatically. Use within a transaction() context
        or call conn.commit() explicitly.

    Example:
        >>> with transaction():
        ...     execute("INSERT INTO tasks (id, name) VALUES (?, ?)", (id, name))
        ...     execute("UPDATE sessions SET updated_at = CURRENT_TIMESTAMP")
    """
    conn = get_db()
    cursor = conn.cursor()

    if params:
        cursor.execute(sql, params)
    else:
        cursor.execute(sql)

    return cursor


@contextmanager
def transaction():
    """Context manager for database transactions.

    Automatically commits on success and rolls back on exceptions.

    Yields:
        sqlite3.Connection: Database connection

    Example:
        >>> with transaction() as conn:
        ...     conn.execute("INSERT INTO tasks ...")
        ...     conn.execute("UPDATE sessions ...")
        # Auto-commits here if no exception

        >>> try:
        ...     with transaction() as conn:
        ...         conn.execute("INSERT ...")
        ...         raise ValueError("Oops")
        ... except ValueError:
        ...     pass
        # Auto-rollback happened
    """
    conn = get_db()

    try:
        # Start transaction
        yield conn
        # Commit on success
        conn.commit()
        logger.debug("Transaction committed")

    except Exception as e:
        # Rollback on error
        conn.rollback()
        logger.error(f"Transaction rolled back: {e}")
        raise


# Diagnostic functions

def get_connection_info() -> Dict[str, Any]:
    """Get information about current database connection.

    Returns:
        Dictionary with connection details:
        - db_path: Path to database file
        - thread_name: Current thread name
        - has_connection: Whether thread has active connection
        - pragma_settings: Current PRAGMA values

    Example:
        >>> info = get_connection_info()
        >>> print(f"Connected to: {info['db_path']}")
    """
    info = {
        "db_path": _get_db_path(),
        "thread_name": threading.current_thread().name,
        "has_connection": hasattr(_thread_local, "connection") and _thread_local.connection is not None,
    }

    # Try to get PRAGMA settings if connection exists
    if info["has_connection"]:
        try:
            conn = _thread_local.connection
            cursor = conn.cursor()

            pragmas = {}
            for pragma in ["foreign_keys", "journal_mode", "synchronous", "busy_timeout"]:
                result = cursor.execute(f"PRAGMA {pragma}").fetchone()
                pragmas[pragma] = result[0] if result else None

            info["pragma_settings"] = pragmas
        except Exception as e:
            info["pragma_error"] = str(e)

    return info


def reset_db_path(new_path: Optional[str] = None) -> None:
    """Reset the database path (for testing only).

    Args:
        new_path: New database path, or None to reset to environment default

    Warning:
        This should only be used in test fixtures. Production code should never
        call this function.
    """
    global _DB_PATH

    with _DB_PATH_LOCK:
        # Close all existing connections before path reset
        close_all_db()

        # Reset path
        _DB_PATH = None

        if new_path:
            _DB_PATH = str(Path(new_path).resolve())
            logger.warning(f"DB path reset to: {_DB_PATH} (test mode)")


atexit.register(close_all_db)
