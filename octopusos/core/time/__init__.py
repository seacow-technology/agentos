"""
AgentOS Time Module

Provides unified time utilities following the Time & Timestamp Contract.

Usage:
    from agentos.core.time import utc_now, utc_now_ms

    now = utc_now()  # aware UTC datetime
    timestamp = utc_now_ms()  # epoch milliseconds
"""

from .clock import (
    utc_now,
    utc_now_ms,
    utc_now_iso,
    from_epoch_ms,
    to_epoch_ms,
    from_epoch_s,
    to_epoch_s,
    ensure_utc,
    iso_z,
    parse_db_time,
)

__all__ = [
    'utc_now',
    'utc_now_ms',
    'utc_now_iso',
    'from_epoch_ms',
    'to_epoch_ms',
    'from_epoch_s',
    'to_epoch_s',
    'ensure_utc',
    'iso_z',
    'parse_db_time',
]
