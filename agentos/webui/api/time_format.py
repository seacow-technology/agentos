"""
API Time Formatting Utilities - Unified timestamp format for M-02 API Contract Consistency

This module provides standardized datetime formatting utilities to ensure
all API responses use ISO 8601 UTC timestamps consistently.

Created for BACKLOG M-02: Time Field Format Consistency
"""

from datetime import datetime, timezone, date
from typing import Optional, Union
import logging
from agentos.core.time import utc_now


logger = logging.getLogger(__name__)


def format_datetime(dt: Optional[Union[datetime, str]]) -> Optional[str]:
    """
    Format datetime to ISO 8601 UTC string

    Ensures all timestamps in API responses follow the same format:
    "2024-01-31T12:34:56.789Z"

    Args:
        dt: Datetime object, ISO string, or None

    Returns:
        ISO 8601 formatted string with UTC timezone, or None if input is None

    Example:
        >>> from datetime import datetime
        >>> dt = datetime(2024, 1, 31, 12, 34, 56)
        >>> format_datetime(dt)
        '2024-01-31T12:34:56.000000Z'
    """
    if dt is None:
        return None

    # If already a string, validate and normalize
    if isinstance(dt, str):
        try:
            # Parse ISO format string
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError:
            logger.warning(f"Invalid datetime string: {dt}, returning as-is")
            return dt

    # Ensure timezone awareness
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC if in different timezone
        dt = dt.astimezone(timezone.utc)

    # Format as ISO 8601 with 'Z' suffix
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def format_datetime_short(dt: Optional[Union[datetime, str]]) -> Optional[str]:
    """
    Format datetime to ISO 8601 UTC string without microseconds

    Use this for cleaner timestamps when microsecond precision is not needed.

    Args:
        dt: Datetime object, ISO string, or None

    Returns:
        ISO 8601 formatted string without microseconds, or None if input is None

    Example:
        >>> from datetime import datetime
        >>> dt = datetime(2024, 1, 31, 12, 34, 56)
        >>> format_datetime_short(dt)
        '2024-01-31T12:34:56Z'
    """
    if dt is None:
        return None

    # If already a string, validate and normalize
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError:
            logger.warning(f"Invalid datetime string: {dt}, returning as-is")
            return dt

    # Ensure timezone awareness
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    # Format without microseconds
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def format_date(d: Optional[Union[date, datetime, str]]) -> Optional[str]:
    """
    Format date to ISO 8601 date string (YYYY-MM-DD)

    Args:
        d: Date, datetime object, ISO string, or None

    Returns:
        ISO 8601 date string, or None if input is None

    Example:
        >>> from datetime import date
        >>> d = date(2024, 1, 31)
        >>> format_date(d)
        '2024-01-31'
    """
    if d is None:
        return None

    if isinstance(d, str):
        try:
            # Try parsing as datetime first
            d = datetime.fromisoformat(d.replace('Z', '+00:00'))
        except ValueError:
            # Return as-is if it's already a date string
            return d

    # Extract date part
    if isinstance(d, datetime):
        d = d.date()

    return d.strftime('%Y-%m-%d')


def now_iso() -> str:
    """
    Get current timestamp in ISO 8601 UTC format

    Returns:
        Current timestamp as ISO 8601 string

    Example:
        >>> now_iso()
        '2024-01-31T12:34:56.789012Z'
    """
    return format_datetime(utc_now())


def now_iso_short() -> str:
    """
    Get current timestamp in ISO 8601 UTC format (no microseconds)

    Returns:
        Current timestamp as ISO 8601 string without microseconds

    Example:
        >>> now_iso_short()
        '2024-01-31T12:34:56Z'
    """
    return format_datetime_short(utc_now())


def parse_iso(iso_string: str) -> Optional[datetime]:
    """
    Parse ISO 8601 string to datetime object

    Args:
        iso_string: ISO 8601 formatted string

    Returns:
        Datetime object in UTC, or None if parsing fails

    Example:
        >>> dt = parse_iso('2024-01-31T12:34:56Z')
        >>> dt.year
        2024
    """
    if not iso_string:
        return None

    try:
        # Handle 'Z' suffix
        iso_string = iso_string.replace('Z', '+00:00')
        dt = datetime.fromisoformat(iso_string)

        # Ensure UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

        return dt
    except ValueError as e:
        logger.warning(f"Failed to parse ISO datetime: {iso_string}, error: {e}")
        return None


def format_timestamp(timestamp: Optional[Union[int, float]]) -> Optional[str]:
    """
    Format Unix timestamp to ISO 8601 UTC string

    Args:
        timestamp: Unix timestamp (seconds since epoch)

    Returns:
        ISO 8601 formatted string, or None if input is None

    Example:
        >>> format_timestamp(1706704496)
        '2024-01-31T12:34:56.000000Z'
    """
    if timestamp is None:
        return None

    try:
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return format_datetime(dt)
    except (ValueError, OSError) as e:
        logger.warning(f"Failed to format timestamp: {timestamp}, error: {e}")
        return None


def to_timestamp(dt: Union[datetime, str]) -> Optional[float]:
    """
    Convert datetime to Unix timestamp

    Args:
        dt: Datetime object or ISO string

    Returns:
        Unix timestamp (seconds since epoch), or None if conversion fails

    Example:
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2024, 1, 31, 12, 34, 56, tzinfo=timezone.utc)
        >>> to_timestamp(dt)
        1706704496.0
    """
    if dt is None:
        return None

    if isinstance(dt, str):
        dt = parse_iso(dt)
        if dt is None:
            return None

    try:
        return dt.timestamp()
    except (ValueError, AttributeError) as e:
        logger.warning(f"Failed to convert to timestamp: {dt}, error: {e}")
        return None


# Validation utilities

def is_valid_iso_datetime(value: str) -> bool:
    """
    Check if string is a valid ISO 8601 datetime

    Args:
        value: String to validate

    Returns:
        True if valid ISO 8601 datetime, False otherwise

    Example:
        >>> is_valid_iso_datetime('2024-01-31T12:34:56Z')
        True
        >>> is_valid_iso_datetime('invalid')
        False
    """
    return parse_iso(value) is not None


def normalize_datetime_field(value: Optional[Union[datetime, str, int, float]]) -> Optional[str]:
    """
    Normalize any datetime-like value to ISO 8601 UTC string

    Handles multiple input formats:
    - datetime objects
    - ISO strings
    - Unix timestamps
    - None

    Args:
        value: Datetime-like value

    Returns:
        ISO 8601 formatted string, or None

    Example:
        >>> normalize_datetime_field(datetime(2024, 1, 31, 12, 34, 56))
        '2024-01-31T12:34:56.000000Z'
        >>> normalize_datetime_field('2024-01-31T12:34:56')
        '2024-01-31T12:34:56.000000Z'
        >>> normalize_datetime_field(1706704496)
        '2024-01-31T12:34:56.000000Z'
    """
    if value is None:
        return None

    # Handle datetime objects
    if isinstance(value, datetime):
        return format_datetime(value)

    # Handle ISO strings
    if isinstance(value, str):
        return format_datetime(value)

    # Handle Unix timestamps
    if isinstance(value, (int, float)):
        return format_timestamp(value)

    logger.warning(f"Unknown datetime format: {type(value)}, value: {value}")
    return None


# Hard Contract Functions - Time & Timestamp Contract (ADR-XXXX)

def ensure_utc(dt: Optional[Union[datetime, str]]) -> Optional[datetime]:
    """
    Ensure datetime is timezone-aware UTC

    This is a hard contract function that guarantees the output is always
    a timezone-aware UTC datetime or None. It NEVER returns naive datetime.

    Behavior:
    - None → None
    - naive datetime → attach UTC timezone (declares it as UTC, does not convert)
    - aware non-UTC → convert to UTC
    - aware UTC → return as-is
    - ISO string → parse and convert to UTC

    Args:
        dt: Datetime object (aware/naive), ISO string, or None

    Returns:
        Timezone-aware UTC datetime or None

    Example:
        >>> from datetime import datetime, timezone
        >>> # Naive datetime - declares as UTC
        >>> naive = datetime(2026, 1, 31, 12, 0, 0)
        >>> result = ensure_utc(naive)
        >>> result.tzinfo == timezone.utc
        True
        >>> # Aware non-UTC - converts to UTC
        >>> from datetime import timedelta
        >>> utc8 = datetime(2026, 1, 31, 20, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        >>> result = ensure_utc(utc8)
        >>> result.hour
        12
    """
    if dt is None:
        return None

    # If string, parse first
    if isinstance(dt, str):
        try:
            # Handle 'Z' suffix and various ISO formats
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError as e:
            logger.warning(f"Invalid datetime string: {dt}, error: {e}")
            return None

    # Ensure timezone awareness
    if dt.tzinfo is None:
        # Naive datetime - declare as UTC (do not convert)
        return dt.replace(tzinfo=timezone.utc)
    else:
        # Aware datetime - convert to UTC
        return dt.astimezone(timezone.utc)


def iso_z(dt: Optional[Union[datetime, str]]) -> Optional[str]:
    """
    Convert datetime to ISO 8601 UTC string with Z suffix

    This is a hard contract function that guarantees the output ALWAYS
    ends with 'Z' (or returns None). This prevents frontend timezone
    misinterpretation.

    Output format: YYYY-MM-DDTHH:MM:SS.ffffffZ

    Args:
        dt: Datetime object, ISO string, or None

    Returns:
        ISO 8601 string with Z suffix, or None
        The output ALWAYS matches regex: ^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{6}Z$

    Example:
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2026, 1, 31, 12, 34, 56, 789012, tzinfo=timezone.utc)
        >>> iso_z(dt)
        '2026-01-31T12:34:56.789012Z'
        >>> # Always includes Z suffix
        >>> result = iso_z(dt)
        >>> result.endswith('Z')
        True
    """
    if dt is None:
        return None

    # Ensure UTC first
    utc_dt = ensure_utc(dt)
    if utc_dt is None:
        return None

    # Format with Z suffix (microseconds always included)
    return utc_dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def parse_db_time(value: Optional[Union[str, datetime, int, float]]) -> Optional[datetime]:
    """
    Parse database time value to timezone-aware UTC datetime

    This function handles the messy reality of database storage and
    ensures all time values are normalized to aware UTC datetime.

    Supports multiple formats from database:
    - "2026-01-31 12:34:56" (SQLite CURRENT_TIMESTAMP) → treated as UTC
    - "2026-01-31T12:34:56" (ISO without timezone) → treated as UTC
    - "2026-01-31T12:34:56Z" (ISO with Z) → parsed as UTC
    - "2026-01-31T12:34:56+00:00" (ISO with offset) → converted to UTC
    - epoch_ms (int/float) → converted from milliseconds since epoch
    - datetime naive → attach UTC
    - datetime aware → convert to UTC
    - None → None

    Args:
        value: Value from database (any format)

    Returns:
        Timezone-aware UTC datetime or None

    Example:
        >>> # SQLite naive format
        >>> parse_db_time("2026-01-31 12:34:56")
        datetime.datetime(2026, 1, 31, 12, 34, 56, tzinfo=datetime.timezone.utc)
        >>> # Epoch milliseconds
        >>> parse_db_time(1738329296000)
        datetime.datetime(2026, 1, 31, 12, 34, 56, tzinfo=datetime.timezone.utc)
    """
    if value is None:
        return None

    # Handle datetime objects
    if isinstance(value, datetime):
        return ensure_utc(value)

    # Handle epoch timestamp (milliseconds)
    if isinstance(value, (int, float)):
        try:
            # If value is very large, assume milliseconds; otherwise seconds
            if value > 1e10:  # Likely milliseconds
                dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
            else:  # Likely seconds
                dt = datetime.fromtimestamp(value, tz=timezone.utc)
            return dt
        except (ValueError, OSError) as e:
            logger.warning(f"Invalid timestamp: {value}, error: {e}")
            return None

    # Handle string formats
    if isinstance(value, str):
        # Try various formats

        # 1. ISO format with Z or offset
        if 'T' in value and (value.endswith('Z') or '+' in value or value.count('-') > 2):
            return ensure_utc(value)

        # 2. ISO format without timezone (treat as UTC)
        if 'T' in value:
            try:
                dt = datetime.fromisoformat(value)
                return ensure_utc(dt)
            except ValueError:
                pass

        # 3. SQLite format "YYYY-MM-DD HH:MM:SS" (treat as UTC)
        if ' ' in value and len(value) >= 19:
            try:
                dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        # 4. Try with microseconds
        if ' ' in value and '.' in value:
            try:
                dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S.%f')
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        logger.warning(f"Could not parse datetime string: {value}")
        return None

    logger.warning(f"Unknown datetime type: {type(value)}, value: {value}")
    return None
