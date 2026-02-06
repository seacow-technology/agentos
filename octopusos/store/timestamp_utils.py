"""
Timestamp utility functions for AgentOS Store
Part of Time & Timestamp Contract (ADR-XXXX)

This module provides utilities for working with epoch millisecond timestamps
in a timezone-safe manner.

Key Principles:
1. Always store timestamps as INTEGER epoch_ms (UTC)
2. Convert to local time only for display
3. Never do arithmetic on TIMESTAMP strings
4. Use epoch_ms for all comparisons and sorting
"""

import time
from datetime import datetime, timezone
from typing import Optional, Union


def now_ms() -> int:
    """
    Get current UTC timestamp in epoch milliseconds.

    Returns:
        Current UTC timestamp as integer epoch milliseconds

    Example:
        >>> ts = now_ms()
        >>> print(ts)
        1705320000000
    """
    return int(time.time() * 1000)


def to_epoch_ms(dt: Optional[Union[datetime, str]]) -> Optional[int]:
    """
    Convert datetime or ISO string to epoch milliseconds.

    Args:
        dt: datetime object (timezone-aware or naive) or ISO format string
            - If naive datetime, assumes UTC
            - If string, attempts to parse as ISO format

    Returns:
        Epoch milliseconds (int) or None if input is None

    Raises:
        ValueError: If string cannot be parsed as datetime

    Examples:
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        >>> to_epoch_ms(dt)
        1705320000000

        >>> to_epoch_ms("2024-01-15T12:00:00Z")
        1705320000000

        >>> to_epoch_ms(None)
        None
    """
    if dt is None:
        return None

    if isinstance(dt, str):
        # Parse ISO format string
        # Handle both with and without 'Z' suffix
        dt_str = dt.rstrip('Z')
        try:
            dt = datetime.fromisoformat(dt_str)
        except ValueError as e:
            raise ValueError(f"Cannot parse datetime string '{dt}': {e}")

    # If datetime is naive, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Convert to UTC if not already
    dt_utc = dt.astimezone(timezone.utc)

    # Return epoch milliseconds
    return int(dt_utc.timestamp() * 1000)


def from_epoch_ms(epoch_ms: Optional[int], tz: Optional[timezone] = None) -> Optional[datetime]:
    """
    Convert epoch milliseconds to datetime object.

    Args:
        epoch_ms: Epoch milliseconds (integer)
        tz: Target timezone (defaults to UTC)

    Returns:
        Timezone-aware datetime object or None if input is None

    Examples:
        >>> dt = from_epoch_ms(1705320000000)
        >>> dt.isoformat()
        '2024-01-15T12:00:00+00:00'

        >>> from_epoch_ms(None)
        None
    """
    if epoch_ms is None:
        return None

    # Convert milliseconds to seconds
    epoch_seconds = epoch_ms / 1000.0

    # Create UTC datetime
    dt_utc = datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)

    # Convert to target timezone if specified
    if tz is not None:
        return dt_utc.astimezone(tz)

    return dt_utc


def format_timestamp(epoch_ms: Optional[int], fmt: str = "%Y-%m-%d %H:%M:%S UTC") -> str:
    """
    Format epoch milliseconds as human-readable string.

    Args:
        epoch_ms: Epoch milliseconds (integer)
        fmt: strftime format string (default: "YYYY-MM-DD HH:MM:SS UTC")

    Returns:
        Formatted timestamp string or empty string if input is None

    Examples:
        >>> format_timestamp(1705320000000)
        '2024-01-15 12:00:00 UTC'

        >>> format_timestamp(1705320000000, fmt="%Y-%m-%d")
        '2024-01-15'

        >>> format_timestamp(None)
        ''
    """
    if epoch_ms is None:
        return ""

    dt = from_epoch_ms(epoch_ms)
    return dt.strftime(fmt)


def sqlite_timestamp_to_epoch_ms(sqlite_timestamp: Optional[str]) -> Optional[int]:
    """
    Convert SQLite TIMESTAMP string to epoch milliseconds.

    This function is used during migration to convert existing TIMESTAMP
    columns to epoch_ms format.

    Args:
        sqlite_timestamp: SQLite TIMESTAMP string (e.g., "2024-01-15 12:00:00")

    Returns:
        Epoch milliseconds (int) or None if input is None

    Note:
        SQLite TIMESTAMP strings are assumed to be in UTC.

    Examples:
        >>> sqlite_timestamp_to_epoch_ms("2024-01-15 12:00:00")
        1705320000000

        >>> sqlite_timestamp_to_epoch_ms(None)
        None
    """
    if sqlite_timestamp is None:
        return None

    # Parse SQLite timestamp (format: "YYYY-MM-DD HH:MM:SS")
    try:
        dt = datetime.strptime(sqlite_timestamp, "%Y-%m-%d %H:%M:%S")
        # Assume UTC
        dt = dt.replace(tzinfo=timezone.utc)
        return to_epoch_ms(dt)
    except ValueError:
        # Try ISO format as fallback
        return to_epoch_ms(sqlite_timestamp)


def epoch_ms_to_sqlite_timestamp(epoch_ms: Optional[int]) -> Optional[str]:
    """
    Convert epoch milliseconds to SQLite TIMESTAMP string.

    This function is used for backward compatibility with code that
    expects SQLite TIMESTAMP format.

    Args:
        epoch_ms: Epoch milliseconds (integer)

    Returns:
        SQLite TIMESTAMP string (e.g., "2024-01-15 12:00:00") or None

    Examples:
        >>> epoch_ms_to_sqlite_timestamp(1705320000000)
        '2024-01-15 12:00:00'

        >>> epoch_ms_to_sqlite_timestamp(None)
        None
    """
    if epoch_ms is None:
        return None

    dt = from_epoch_ms(epoch_ms)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def is_recent(epoch_ms: Optional[int], seconds_ago: int = 3600) -> bool:
    """
    Check if a timestamp is within the last N seconds.

    Args:
        epoch_ms: Epoch milliseconds (integer)
        seconds_ago: Number of seconds to look back (default: 3600 = 1 hour)

    Returns:
        True if timestamp is within the last N seconds, False otherwise

    Examples:
        >>> # Check if timestamp is within last hour
        >>> is_recent(now_ms() - 30*60*1000)  # 30 minutes ago
        True

        >>> is_recent(now_ms() - 2*3600*1000)  # 2 hours ago
        False

        >>> is_recent(None)
        False
    """
    if epoch_ms is None:
        return False

    current_ms = now_ms()
    threshold_ms = seconds_ago * 1000

    return (current_ms - epoch_ms) <= threshold_ms


def time_ago(epoch_ms: Optional[int]) -> str:
    """
    Format timestamp as relative time (e.g., "2 hours ago").

    Args:
        epoch_ms: Epoch milliseconds (integer)

    Returns:
        Human-readable relative time string

    Examples:
        >>> time_ago(now_ms() - 30*1000)
        '30 seconds ago'

        >>> time_ago(now_ms() - 5*60*1000)
        '5 minutes ago'

        >>> time_ago(None)
        'never'
    """
    if epoch_ms is None:
        return "never"

    current_ms = now_ms()
    diff_ms = current_ms - epoch_ms

    if diff_ms < 0:
        return "in the future"

    diff_seconds = diff_ms // 1000

    if diff_seconds < 60:
        return f"{diff_seconds} seconds ago"

    diff_minutes = diff_seconds // 60
    if diff_minutes < 60:
        return f"{diff_minutes} minutes ago"

    diff_hours = diff_minutes // 60
    if diff_hours < 24:
        return f"{diff_hours} hours ago"

    diff_days = diff_hours // 24
    if diff_days < 30:
        return f"{diff_days} days ago"

    diff_months = diff_days // 30
    if diff_months < 12:
        return f"{diff_months} months ago"

    diff_years = diff_months // 12
    return f"{diff_years} years ago"


# Migration helper: SQL formula for converting TIMESTAMP to epoch_ms
# This can be used in UPDATE statements during migration
SQLITE_TIMESTAMP_TO_EPOCH_MS_FORMULA = "(julianday(?) - 2440587.5) * 86400000"

# Validation constants (for testing)
EPOCH_2020_MS = 1577836800000  # 2020-01-01 00:00:00 UTC
EPOCH_2030_MS = 1893456000000  # 2030-01-01 00:00:00 UTC


def validate_epoch_ms(epoch_ms: Optional[int],
                      min_ms: int = EPOCH_2020_MS,
                      max_ms: int = EPOCH_2030_MS) -> bool:
    """
    Validate that epoch_ms is within reasonable range.

    This is useful for detecting conversion errors during migration.

    Args:
        epoch_ms: Epoch milliseconds to validate
        min_ms: Minimum valid timestamp (default: 2020-01-01)
        max_ms: Maximum valid timestamp (default: 2030-01-01)

    Returns:
        True if valid, False otherwise

    Examples:
        >>> validate_epoch_ms(1705320000000)  # 2024-01-15
        True

        >>> validate_epoch_ms(946684800000)  # 2000-01-01 (too old)
        False

        >>> validate_epoch_ms(None)
        True  # NULL is valid
    """
    if epoch_ms is None:
        return True

    return min_ms <= epoch_ms <= max_ms


# Example usage in store operations:
#
# # Creating new record:
# conn.execute(
#     "INSERT INTO chat_sessions (session_id, created_at_ms) VALUES (?, ?)",
#     (session_id, now_ms())
# )
#
# # Querying recent sessions:
# threshold = now_ms() - 3600*1000  # 1 hour ago
# conn.execute(
#     "SELECT * FROM chat_sessions WHERE created_at_ms > ? ORDER BY created_at_ms DESC",
#     (threshold,)
# )
#
# # Display formatting:
# for row in results:
#     print(f"Session created: {format_timestamp(row['created_at_ms'])}")
#     print(f"  ({time_ago(row['created_at_ms'])})")
