"""CLI health check utilities for database schema validation"""

import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def check_schema_version() -> tuple[bool, Optional[str]]:
    """Check if database schema is up-to-date
    
    This performs a defensive check to ensure the database schema version
    matches the expected version (latest available) for the current CLI.
    
    Returns:
        tuple[bool, Optional[str]]: (is_ok, error_message)
            - (True, None) if schema is up-to-date
            - (False, error_message) if action required
    
    Usage:
        Called at CLI startup to provide early feedback to users about
        database state without blocking operations.
    """
    try:
        from agentos.store import get_db
        from agentos.store.migrations import get_current_version, get_latest_version
        
        # Get current version from database
        conn = get_db()
        current = get_current_version(conn)
        # Do NOT close: get_db() returns shared thread-local connection
        
        # Get latest version from filesystem
        migrations_dir = Path(__file__).parent.parent / "store" / "migrations"
        latest = get_latest_version(migrations_dir)

        if latest is None:
            # If we can't determine latest but current exists, assume OK (defensive)
            # This typically means migrations dir structure differs from expected
            if current is not None:
                logger.debug("Cannot determine latest schema version, but current version exists")
                return True, None
            return False, "Cannot determine latest schema version"

        if current != latest:
            return False, (
                f"Database schema version is {current}, expected {latest}. "
                f"Please run: agentos migrate"
            )

        return True, None
        
    except FileNotFoundError:
        return False, "Database not initialized. Please run: agentos init"
    except Exception as e:
        logger.debug(f"Schema check failed: {e}")
        # Don't block CLI startup for minor issues
        return False, f"Database check failed: {e}"


def print_schema_warning(message: str) -> None:
    """Print a formatted schema warning to the console
    
    Args:
        message: Warning message to display
    """
    from rich.console import Console
    console = Console()
    console.print(f"\n[yellow]⚠️  {message}[/yellow]\n")
