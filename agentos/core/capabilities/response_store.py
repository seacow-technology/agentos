"""
Response store for capability execution

Stores the last response from each session to enable follow-up commands
like "/postman explain last_response"
"""

import logging
from typing import Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ResponseStore:
    """
    In-memory store for recent command responses

    Stores the most recent response for each session, with automatic
    size limiting to prevent memory issues.
    """

    # Maximum response size to store (1 MB)
    MAX_RESPONSE_SIZE = 1_000_000

    # Response TTL (time to live)
    DEFAULT_TTL_HOURS = 24

    def __init__(self, ttl_hours: int = DEFAULT_TTL_HOURS):
        """
        Initialize response store

        Args:
            ttl_hours: Time to live for stored responses in hours
        """
        self._store: Dict[str, Dict[str, any]] = {}
        self.ttl_hours = ttl_hours

    def save(
        self,
        session_id: str,
        response: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Save a response for a session

        Args:
            session_id: Session identifier
            response: Response content to store
            metadata: Optional metadata about the response
        """
        # Truncate if too large
        if len(response) > self.MAX_RESPONSE_SIZE:
            logger.warning(
                f"Response for session {session_id} exceeds max size "
                f"({len(response)} bytes), truncating to {self.MAX_RESPONSE_SIZE} bytes"
            )
            response = response[:self.MAX_RESPONSE_SIZE] + "\n... (truncated)"

        self._store[session_id] = {
            "response": response,
            "timestamp": datetime.now(),
            "metadata": metadata or {}
        }

        logger.debug(f"Saved response for session {session_id} ({len(response)} bytes)")

        # Clean up expired entries
        self._cleanup_expired()

    def get(self, session_id: str) -> Optional[str]:
        """
        Get the stored response for a session

        Args:
            session_id: Session identifier

        Returns:
            Stored response or None if not found or expired
        """
        entry = self._store.get(session_id)

        if not entry:
            logger.debug(f"No response found for session {session_id}")
            return None

        # Check if expired
        if self._is_expired(entry["timestamp"]):
            logger.debug(f"Response for session {session_id} has expired")
            self._store.pop(session_id, None)
            return None

        return entry["response"]

    def get_metadata(self, session_id: str) -> Optional[Dict]:
        """
        Get metadata for a stored response

        Args:
            session_id: Session identifier

        Returns:
            Metadata dictionary or None
        """
        entry = self._store.get(session_id)
        if entry and not self._is_expired(entry["timestamp"]):
            return entry["metadata"]
        return None

    def clear(self, session_id: str) -> None:
        """
        Clear the stored response for a session

        Args:
            session_id: Session identifier
        """
        if session_id in self._store:
            self._store.pop(session_id)
            logger.debug(f"Cleared response for session {session_id}")

    def clear_all(self) -> None:
        """Clear all stored responses"""
        count = len(self._store)
        self._store.clear()
        logger.info(f"Cleared all stored responses ({count} entries)")

    def _is_expired(self, timestamp: datetime) -> bool:
        """Check if a timestamp is expired"""
        age = datetime.now() - timestamp
        return age > timedelta(hours=self.ttl_hours)

    def _cleanup_expired(self) -> None:
        """Remove expired entries"""
        expired_keys = [
            session_id
            for session_id, entry in self._store.items()
            if self._is_expired(entry["timestamp"])
        ]

        for session_id in expired_keys:
            self._store.pop(session_id, None)

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired responses")

    def get_stats(self) -> Dict[str, any]:
        """
        Get statistics about stored responses

        Returns:
            Dictionary with store statistics
        """
        self._cleanup_expired()

        total_size = sum(
            len(entry["response"])
            for entry in self._store.values()
        )

        return {
            "total_entries": len(self._store),
            "total_size_bytes": total_size,
            "ttl_hours": self.ttl_hours,
            "max_response_size": self.MAX_RESPONSE_SIZE
        }


# Global response store instance
_response_store: Optional[ResponseStore] = None


def get_response_store() -> ResponseStore:
    """
    Get the global response store instance

    Returns:
        Global ResponseStore singleton
    """
    global _response_store
    if _response_store is None:
        _response_store = ResponseStore()
    return _response_store
