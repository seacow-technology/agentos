"""Lock token for tracking acquired locks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LockToken:
    """Token representing an acquired lock."""

    lock_id: str
    task_id: str
    holder: str
    expires_at: float

    def is_expired(self, current_time: float) -> bool:
        """Check if lock has expired."""
        return current_time >= self.expires_at
