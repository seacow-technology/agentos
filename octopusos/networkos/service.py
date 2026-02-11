"""Snapshot-safe NetworkOS service stub.

This module keeps imports stable when full NetworkOS implementation
is not included in the public open-source snapshot.
"""

from __future__ import annotations


class NetworkOSService:
    """Fallback stub that reports feature unavailability on use."""

    def __getattr__(self, name: str):
        raise RuntimeError(
            "NetworkOS is not available in this open-source snapshot. "
            f"Attempted to access method: {name}"
        )
