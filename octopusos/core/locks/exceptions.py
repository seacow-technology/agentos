"""Lock-related exceptions."""

from __future__ import annotations

from typing import Optional


class LockConflict(RuntimeError):
    """Raised when a lock conflict occurs."""

    def __init__(
        self,
        resource: str,
        owner: Optional[str] = None,
        wait: bool = True,
        message: Optional[str] = None,
    ):
        """
        Initialize lock conflict exception.

        Args:
            resource: Resource that caused the conflict
            owner: Current owner of the lock (if known)
            wait: Whether the task should wait (True) or fail immediately (False)
            message: Optional custom message
        """
        self.resource = resource
        self.owner = owner
        self.wait = wait

        if message is None:
            message = f"Lock conflict on {resource}"
            if owner:
                message += f", owner={owner}"
            message += f", wait={wait}"

        super().__init__(message)
