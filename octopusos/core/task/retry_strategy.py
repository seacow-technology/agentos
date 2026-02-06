"""
Task Retry Strategy

Provides task-level retry configuration and enforcement.
Distinct from tool-level retry (agentos/ext/tools/retry_policy.py).

Key Features:
1. Retry count limiting (prevent infinite retry)
2. Retry backoff configuration
3. Retry history tracking
4. Retry loop detection
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
import logging
from agentos.core.time import utc_now, utc_now_iso


logger = logging.getLogger(__name__)


class RetryBackoffType(str, Enum):
    """Retry backoff strategies."""
    NONE = "none"                    # No delay between retries
    FIXED = "fixed"                  # Fixed delay (e.g., 60s)
    LINEAR = "linear"                # Linear increase (60s, 120s, 180s)
    EXPONENTIAL = "exponential"      # Exponential backoff (60s, 120s, 240s)


@dataclass
class RetryConfig:
    """
    Task Retry Configuration

    Controls how many times a failed task can be retried and
    the delay between retry attempts.

    Attributes:
        max_retries: Maximum number of retries (default: 3)
        backoff_type: Retry backoff strategy
        base_delay_seconds: Base delay for backoff calculation (default: 60)
        max_delay_seconds: Maximum delay between retries (default: 3600)
    """
    max_retries: int = 3
    backoff_type: RetryBackoffType = RetryBackoffType.EXPONENTIAL
    base_delay_seconds: int = 60
    max_delay_seconds: int = 3600

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for metadata storage."""
        return {
            "max_retries": self.max_retries,
            "backoff_type": self.backoff_type.value,
            "base_delay_seconds": self.base_delay_seconds,
            "max_delay_seconds": self.max_delay_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetryConfig":
        """Create from dictionary."""
        return cls(
            max_retries=data.get("max_retries", 3),
            backoff_type=RetryBackoffType(data.get("backoff_type", "exponential")),
            base_delay_seconds=data.get("base_delay_seconds", 60),
            max_delay_seconds=data.get("max_delay_seconds", 3600),
        )


@dataclass
class RetryState:
    """
    Current retry state for a task

    Tracks retry attempts and calculates next retry time.

    Attributes:
        retry_count: Number of retry attempts so far
        last_retry_at: Timestamp of last retry attempt
        retry_history: List of retry timestamps with reasons
        next_retry_after: Calculated next retry time (ISO 8601)
    """
    retry_count: int = 0
    last_retry_at: Optional[str] = None
    retry_history: List[Dict[str, Any]] = field(default_factory=list)
    next_retry_after: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for metadata storage."""
        return {
            "retry_count": self.retry_count,
            "last_retry_at": self.last_retry_at,
            "retry_history": self.retry_history,
            "next_retry_after": self.next_retry_after,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetryState":
        """Create from dictionary."""
        return cls(
            retry_count=data.get("retry_count", 0),
            last_retry_at=data.get("last_retry_at"),
            retry_history=data.get("retry_history", []),
            next_retry_after=data.get("next_retry_after"),
        )


class RetryStrategyManager:
    """
    Retry Strategy Manager

    Enforces retry policies and prevents infinite retry loops.
    """

    def can_retry(
        self,
        retry_config: RetryConfig,
        retry_state: RetryState
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a task can be retried

        Args:
            retry_config: Retry configuration
            retry_state: Current retry state

        Returns:
            (can_retry, reason) tuple
        """
        # Check retry count limit
        if retry_state.retry_count >= retry_config.max_retries:
            return False, f"Max retries ({retry_config.max_retries}) exceeded"

        # Check for retry loops (same failure repeated 3+ times)
        if len(retry_state.retry_history) >= 3:
            recent_reasons = [
                h.get("reason", "")
                for h in retry_state.retry_history[-3:]
            ]
            if len(set(recent_reasons)) == 1:
                return False, f"Retry loop detected: same failure repeated 3 times"

        return True, None

    def calculate_next_retry_time(
        self,
        retry_config: RetryConfig,
        retry_state: RetryState
    ) -> str:
        """
        Calculate next retry time based on backoff strategy

        Args:
            retry_config: Retry configuration
            retry_state: Current retry state

        Returns:
            ISO 8601 timestamp for next retry
        """
        # Calculate delay based on backoff type
        if retry_config.backoff_type == RetryBackoffType.NONE:
            delay_seconds = 0
        elif retry_config.backoff_type == RetryBackoffType.FIXED:
            delay_seconds = retry_config.base_delay_seconds
        elif retry_config.backoff_type == RetryBackoffType.LINEAR:
            delay_seconds = retry_config.base_delay_seconds * retry_state.retry_count
        else:  # EXPONENTIAL
            # For exponential backoff, use 2^(retry_count-1) so first retry has base_delay
            # retry_count=1 -> 2^0 = 1 -> base_delay
            # retry_count=2 -> 2^1 = 2 -> base_delay * 2
            # retry_count=3 -> 2^2 = 4 -> base_delay * 4
            delay_seconds = retry_config.base_delay_seconds * (2 ** (retry_state.retry_count - 1)) if retry_state.retry_count > 0 else 0

        # Cap at max delay
        delay_seconds = min(delay_seconds, retry_config.max_delay_seconds)

        # Calculate next retry time
        now = utc_now()
        next_retry = now + timedelta(seconds=delay_seconds)

        return next_retry.isoformat()

    def record_retry_attempt(
        self,
        retry_state: RetryState,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RetryState:
        """
        Record a retry attempt

        Args:
            retry_state: Current retry state
            reason: Reason for retry
            metadata: Optional metadata

        Returns:
            Updated retry state
        """
        now = utc_now_iso()

        # Increment retry count
        retry_state.retry_count += 1
        retry_state.last_retry_at = now

        # Add to history
        retry_state.retry_history.append({
            "attempt": retry_state.retry_count,
            "timestamp": now,
            "reason": reason,
            "metadata": metadata or {},
        })

        return retry_state

    def get_retry_metrics(self, retry_state: RetryState) -> Dict[str, Any]:
        """
        Get retry metrics for observability

        Args:
            retry_state: Current retry state

        Returns:
            Dictionary with retry metrics
        """
        return {
            "retry_count": retry_state.retry_count,
            "last_retry_at": retry_state.last_retry_at,
            "retry_attempts": len(retry_state.retry_history),
            "retry_reasons": [h.get("reason") for h in retry_state.retry_history],
        }
