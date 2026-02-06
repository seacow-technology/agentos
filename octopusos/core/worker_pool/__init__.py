"""Worker Pool - Lease-based work item management

This module provides lease-based concurrency control for work items,
enabling distributed worker pools with automatic recovery from failures.

Components:
- LeaseManager: Acquire, renew, and release work item leases
- HeartbeatThread: Automatic lease renewal in background
"""

from .lease import LeaseManager, Lease, LeaseError, LeaseExpiredError
from .heartbeat import HeartbeatThread, start_heartbeat

__all__ = [
    "LeaseManager",
    "Lease",
    "LeaseError",
    "LeaseExpiredError",
    "HeartbeatThread",
    "start_heartbeat",
]
