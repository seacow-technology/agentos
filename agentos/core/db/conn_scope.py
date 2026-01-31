"""Database connection scope manager.

This module provides a unified context manager for managing database connection
lifecycles with support for both private connections and shared connections.

Key Features:
- Automatic connection lifecycle management (create/close)
- Support for private connections (db_path provided)
- Support for shared connections (db_path=None, uses get_db())
- Proper error handling and resource cleanup
- Type-safe API with comprehensive documentation

Usage Pattern:
    Private connection (automatically closed):
        >>> with db_conn_scope("/path/to/db.sqlite") as conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT * FROM tasks")
        # Connection automatically closed here

    Shared connection (managed by get_db()):
        >>> with db_conn_scope(None) as conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT * FROM tasks")
        # Connection remains open (managed by get_db())

Architecture:
- Private connections: Created with sqlite3.connect(), closed on exit
- Shared connections: Retrieved via get_db(), not closed on exit
- Consistent PRAGMA settings via _apply_pragmas()
- Comprehensive error handling with logging

Thread Safety:
- Private connections are thread-safe (check_same_thread=False)
- Shared connections use thread-local storage (see registry_db.py)
"""

import sqlite3
import logging
from contextlib import contextmanager
from typing import Optional, Generator

from agentos.core.db.registry_db import get_db, _apply_pragmas

logger = logging.getLogger(__name__)


class ConnectionScopeError(Exception):
    """Base exception for connection scope errors."""
    pass


class ConnectionCreationError(ConnectionScopeError):
    """Raised when connection creation fails."""
    pass


class ConnectionCloseError(ConnectionScopeError):
    """Raised when connection close fails."""
    pass


@contextmanager
def db_conn_scope(db_path: Optional[str]) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connection lifecycle management.

    This function provides a unified interface for managing database connections
    with automatic cleanup. It supports two modes:

    1. Private Connection Mode (db_path provided):
       - Creates a new sqlite3 connection to the specified database
       - Applies standard PRAGMA settings for consistency
       - Automatically closes connection on context exit
       - Use this when you need an isolated connection or specific database

    2. Shared Connection Mode (db_path=None):
       - Uses the thread-local shared connection from get_db()
       - Does NOT close connection on exit (managed by get_db())
       - Use this for normal operations using the default database

    Args:
        db_path: Path to SQLite database file, or None for shared connection
                 - str: Create private connection to specified database
                 - None: Use shared connection from get_db()

    Yields:
        sqlite3.Connection: Configured database connection
            - Private mode: New connection with row_factory and PRAGMAs
            - Shared mode: Thread-local connection from get_db()

    Raises:
        ConnectionCreationError: If database connection fails
        ConnectionCloseError: If closing private connection fails
        FileNotFoundError: If db_path points to non-existent database
        sqlite3.Error: For other database-related errors

    Example - Private Connection:
        >>> # Create isolated connection for specific database
        >>> with db_conn_scope("/data/archive.sqlite") as conn:
        ...     rows = conn.execute("SELECT * FROM logs").fetchall()
        ...     print(f"Found {len(rows)} log entries")
        # Connection automatically closed

    Example - Shared Connection:
        >>> # Use default database with shared connection pool
        >>> with db_conn_scope(None) as conn:
        ...     rows = conn.execute("SELECT * FROM tasks").fetchall()
        ...     print(f"Found {len(rows)} tasks")
        # Connection remains open for reuse

    Example - Transaction with Private Connection:
        >>> with db_conn_scope("/data/temp.sqlite") as conn:
        ...     try:
        ...         conn.execute("INSERT INTO items VALUES (?)", ("test",))
        ...         conn.commit()
        ...     except sqlite3.Error as e:
        ...         conn.rollback()
        ...         raise

    Example - Error Handling:
        >>> try:
        ...     with db_conn_scope("/nonexistent/db.sqlite") as conn:
        ...         pass
        ... except ConnectionCreationError as e:
        ...     print(f"Failed to connect: {e}")

    Implementation Notes:
        - Private connections use timeout=30 to handle busy databases
        - Private connections use check_same_thread=False for flexibility
        - PRAGMA settings ensure consistency across all connections
        - Shared connections benefit from thread-local caching
        - Close errors in private mode are logged but don't propagate

    Performance Considerations:
        - Private mode: Connection overhead on each context entry
        - Shared mode: Reuses cached connection (faster for repeated use)
        - Prefer shared mode unless isolation is required

    Thread Safety:
        - Private connections: Safe to pass between threads (check_same_thread=False)
        - Shared connections: Thread-local (don't share between threads)
    """
    if db_path:
        # Private Connection Mode: Create new connection, clean up on exit
        conn = None
        try:
            logger.debug(f"Creating private connection to: {db_path}")

            # Create new SQLite connection with reasonable defaults
            conn = sqlite3.connect(
                db_path,
                timeout=30,  # Wait up to 30s for database lock
                check_same_thread=False  # Allow connection sharing between threads
            )

            # Configure connection for usability and consistency
            conn.row_factory = sqlite3.Row  # Enable column access by name

            # Apply standard PRAGMA settings
            try:
                _apply_pragmas(conn)
                logger.debug(f"Applied PRAGMA settings to private connection: {db_path}")
            except Exception as pragma_error:
                logger.warning(f"Failed to apply PRAGMAs to {db_path}: {pragma_error}")
                # Continue anyway - PRAGMAs are optimizations, not critical

        except sqlite3.Error as e:
            error_msg = f"Failed to create connection to {db_path}: {e}"
            logger.error(error_msg)
            raise ConnectionCreationError(error_msg) from e

        except Exception as e:
            error_msg = f"Unexpected error creating connection to {db_path}: {e}"
            logger.error(error_msg)
            raise ConnectionCreationError(error_msg) from e

        try:
            # Yield connection to caller
            yield conn

        finally:
            # Cleanup: Always attempt to close connection
            if conn:
                try:
                    conn.close()
                    logger.debug(f"Closed private connection to: {db_path}")

                except sqlite3.Error as e:
                    # Log but don't propagate close errors (cleanup is best-effort)
                    error_msg = f"Error closing connection to {db_path}: {e}"
                    logger.warning(error_msg)
                    # Note: We don't raise here because:
                    # 1. Connection cleanup is best-effort
                    # 2. Context exit may already be handling an exception
                    # 3. SQLite will clean up on process exit anyway

                except Exception as e:
                    # Unexpected error during close
                    logger.error(f"Unexpected error closing connection to {db_path}: {e}")

    else:
        # Shared Connection Mode: Use get_db(), do NOT close on exit
        logger.debug("Using shared connection from get_db()")

        try:
            # Get shared thread-local connection
            conn = get_db()

            # Yield to caller (no cleanup needed)
            yield conn

        except FileNotFoundError as e:
            # Database not initialized
            error_msg = f"Database not found: {e}"
            logger.error(error_msg)
            raise ConnectionCreationError(error_msg) from e

        except Exception as e:
            # Other errors from get_db()
            error_msg = f"Failed to get shared connection: {e}"
            logger.error(error_msg)
            raise ConnectionCreationError(error_msg) from e

        # No finally block: shared connections are managed by get_db()
        # Closing them here would break thread-local caching


# Convenience functions for common patterns

def with_private_connection(db_path: str, func, *args, **kwargs):
    """Execute function with a private database connection.

    This is a convenience wrapper around db_conn_scope() for functional-style
    code that needs a private connection.

    Args:
        db_path: Path to SQLite database file
        func: Function to call with connection as first argument
        *args: Additional positional arguments for func
        **kwargs: Additional keyword arguments for func

    Returns:
        Return value from func

    Example:
        >>> def count_rows(conn, table_name):
        ...     cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        ...     return cursor.fetchone()[0]
        >>>
        >>> count = with_private_connection("/data/db.sqlite", count_rows, "tasks")
        >>> print(f"Task count: {count}")
    """
    with db_conn_scope(db_path) as conn:
        return func(conn, *args, **kwargs)


def with_shared_connection(func, *args, **kwargs):
    """Execute function with the shared database connection.

    This is a convenience wrapper around db_conn_scope(None) for functional-style
    code that needs the shared connection.

    Args:
        func: Function to call with connection as first argument
        *args: Additional positional arguments for func
        **kwargs: Additional keyword arguments for func

    Returns:
        Return value from func

    Example:
        >>> def get_task_count(conn):
        ...     cursor = conn.execute("SELECT COUNT(*) FROM tasks")
        ...     return cursor.fetchone()[0]
        >>>
        >>> count = with_shared_connection(get_task_count)
        >>> print(f"Task count: {count}")
    """
    with db_conn_scope(None) as conn:
        return func(conn, *args, **kwargs)
